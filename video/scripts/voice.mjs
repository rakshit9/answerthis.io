/**
 * Render the voice-over with macOS `say`, then write the measured duration of
 * each clip so the scenes can be timed from the audio rather than guessed.
 *
 *   node scripts/voice.mjs [voice]
 *
 * `say` is offline and free, which is the point — no key, no upload of the
 * script to a third party. Swap in a better TTS by dropping WAVs with the same
 * names into public/vo/ and rerunning the durations step.
 */
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import path from "node:path";

const VOICE = process.argv[2] ?? "Samantha";
// Human narration sits around 150–160 wpm. The earlier 178 was the reason it
// sounded like a screen reader rather than a voice-over.
const RATE = 158;
const OUT = path.resolve("public/vo");

/** Words the synthesiser gets wrong, respelled for the ear only. The on-screen
 *  script in narration.ts stays correct — this map is applied to the audio. */
const SAY_AS = [
  [/\bLaTeX\b/g, "Lay-Tech"],
  [/\barXiv\b/g, "archive"],
  [/\bCSL-JSON\b/g, "C S L JSON"],
  [/\bCSL\b/g, "C S L"],
  [/\bciteproc\b/g, "cite-prock"],
  [/\bAPIs\b/g, "A P Eyes"],
  [/\bAPI\b/g, "A P I"],
  [/\bPDF\b/g, "P D F"],
  [/\bDOI\b/g, "D O I"],
  [/\bOpenAlex\b/g, "Open Alex"],
  [/\bmain dot tex\b/g, "main dot tech"],
];

/** Real speech breathes at punctuation. `say` takes embedded pause commands,
 *  and inserting them is most of the difference between "read aloud" and
 *  "narrated". */
const withPauses = (text) =>
  text
    .replace(/([.!?])\s+/g, "$1 [[slnc 380]] ")
    .replace(/([,;:])\s+/g, "$1 [[slnc 140]] ")
    .replace(/\s+—\s+/g, " [[slnc 220]] ");

const forSpeech = (text) =>
  withPauses(SAY_AS.reduce((s, [re, to]) => s.replace(re, to), text));
mkdirSync(OUT, { recursive: true });

// Read the script straight out of the TS module so the two cannot drift.
const src = readFileSync(path.resolve("src/narration.ts"), "utf8");
const body = src.slice(src.indexOf("export const NARRATION"), src.indexOf("export const SCENE_ORDER"));
const NARRATION = {};
for (const m of body.matchAll(/^\s{2}(\w+):\s*\n?\s*"((?:[^"\\]|\\.)*)",\s*$/gm)) {
  NARRATION[m[1]] = m[2].replace(/\\"/g, '"');
}

const durations = {};
for (const [id, text] of Object.entries(NARRATION)) {
  const aiff = path.join(OUT, `${id}.aiff`);
  const wav = path.join(OUT, `${id}.wav`);
  execFileSync("say", ["-v", VOICE, "-r", String(RATE), "-o", aiff, forSpeech(text)]);
  // Remotion wants a web-playable container; afconvert ships with macOS.
  execFileSync("afconvert", ["-f", "WAVE", "-d", "LEI16@44100", aiff, wav]);
  const info = execFileSync("afinfo", [wav]).toString();
  const secs = Number(/estimated duration: ([\d.]+)/.exec(info)?.[1] ?? 0);
  durations[id] = secs;
  execFileSync("rm", [aiff]);
  console.log(`${id.padEnd(16)} ${secs.toFixed(2)}s`);
}

writeFileSync(path.join(OUT, "durations.json"), JSON.stringify(durations, null, 2));
const total = Object.values(durations).reduce((a, b) => a + b, 0);
console.log(`\ntotal narration ${total.toFixed(1)}s (${(total / 60).toFixed(1)} min) · voice ${VOICE}`);
