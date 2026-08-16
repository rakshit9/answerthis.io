import { Config } from "@remotion/cli/config";

/** Frames are captured as PNG rather than JPEG. JPEG frames make ffmpeg pick
 *  `yuvj420p` — the full-range variant — which QuickTime, Preview and Safari
 *  either refuse outright or play with shifted colours. PNG frames plus an
 *  explicit `yuv420p` give the limited-range 4:2:0 that every player expects.
 *  It costs render time, not file size: the encode is the same either way. */
Config.setVideoImageFormat("png");
Config.setPixelFormat("yuv420p");
Config.setCodec("h264");

/** Constant-rate-factor: 23 is visually clean for flat UI colour and roughly
 *  halves the file against the default. */
Config.setCrf(23);

Config.setOverwriteOutput(true);
Config.setConcurrency(4);
