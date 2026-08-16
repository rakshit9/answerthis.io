/* A live picture of the parsing algorithm.
 *
 * ~1500 particles stand in for the text lines pulled out of the PDF. Each
 * pipeline stage has its own target layout, and the particles ease toward
 * whichever stage the backend is currently running — so the animation is
 * driven by real progress, not a timer:
 *
 *   A   scattered glyphs settle into two page columns of text lines
 *   A'  figure/table blocks lift forward, out of the prose flow
 *   B   lines regroup into titled section bands
 *   C   the reference list peels off into separated entries
 *   D   each entry splits into its parsed fields (lime = parsed)
 *   E   connectors arc from body text to the entries they cite
 */
import { useEffect, useRef } from "react";
import * as THREE from "three";

const N = 1500;
const REF_FRACTION = 0.28;          // particles that belong to the reference list
const FLOAT_FRACTION = 0.1;         // particles that belong to figures/tables
const STAGES = ["A", "A'", "B", "C", "D", "E"] as const;
export type StageKey = (typeof STAGES)[number];

const INK = new THREE.Color("#14140f");
const LIME = new THREE.Color("#beff50");
const ASH = new THREE.Color("#d2d2c8");
const WARN = new THREE.Color("#8a6410");

type Slot = { body: boolean; float: boolean; ref: boolean; entry: number; field: number; unparsed: boolean };

function buildSlots(): Slot[] {
  const slots: Slot[] = [];
  const nRef = Math.floor(N * REF_FRACTION);
  const nFloat = Math.floor(N * FLOAT_FRACTION);
  const entries = 18;
  for (let i = 0; i < N; i++) {
    const isRef = i >= N - nRef;
    const isFloat = !isRef && i >= N - nRef - nFloat;
    const idx = i - (N - nRef);
    const entry = isRef ? Math.floor(idx / (nRef / entries)) : -1;
    slots.push({
      body: !isRef && !isFloat, float: isFloat, ref: isRef,
      entry, field: isRef ? idx % 4 : -1,
      // a couple of entries stay unparsed — the pipeline surfaces these
      unparsed: isRef && (entry === 4 || entry === 11),
    });
  }
  return slots;
}

/** Target position for one particle at a given stage. */
function target(stage: number, i: number, s: Slot, out: THREE.Vector3) {
  const COLS = 2, ROWS = 26;
  const col = i % COLS;
  const row = Math.floor(i / COLS) % ROWS;
  const inRow = Math.floor(i / (COLS * ROWS));
  const x0 = col === 0 ? -2.4 : 0.5;

  if (stage < 0) {                                   // pre-parse: loose cloud
    out.set((Math.random() - 0.5) * 9, (Math.random() - 0.5) * 6, (Math.random() - 0.5) * 4);
    return;
  }

  // A — glyphs settle into two page columns of text lines
  let x = x0 + (inRow % 14) * 0.135;
  let y = 2.7 - row * 0.21;
  let z = 0;

  if (stage >= 1 && s.float) {                       // A′ floats lift forward
    const fi = i % 2;
    x = (fi ? 0.6 : -2.3) + ((i * 7) % 12) * 0.13;
    y = (fi ? 0.9 : -1.1) + Math.floor(((i * 7) % 48) / 12) * 0.16;
    z = 1.1;
  } else if (stage >= 2 && s.body) {                 // B section bands
    const band = row % 5;
    y = 2.6 - band * 1.12 - Math.floor(row / 5) * 0.19;
    x = x0 + (inRow % 14) * 0.135 + (band === 0 ? -0.06 : 0);
  }

  if (stage >= 3 && s.ref) {                         // C entries peel off
    const e = Math.max(0, s.entry);
    y = 2.5 - e * 0.3;
    x = 2.9 + (i % 9) * 0.1;
    z = 0.35;
    if (stage >= 4) {                                // D split into fields
      x = 2.75 + s.field * 0.42 + ((i * 3) % 3) * 0.055;
      z = 0.5;
    }
  }

  out.set(x, y, z);
}

export function ParseScene({ stageIndex, running }: { stageIndex: number; running: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const stageRef = useRef(stageIndex);
  stageRef.current = stageIndex;
  const runRef = useRef(running);
  runRef.current = running;

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    // The canvas is inset beside the stage panel (see .parse-scene), so the
    // camera just centres on the layout; z is fitted in resize().
    camera.position.set(0, 0, 12);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    el.appendChild(renderer.domElement);

    const slots = buildSlots();
    const pos = new Float32Array(N * 3);
    const tgt = new Float32Array(N * 3);
    const col = new Float32Array(N * 3);
    // per-particle character: settle speed and drift phase differ, so a
    // stage change reads as a flock re-forming, not a lockstep morph
    const rand = Float32Array.from({ length: N }, () => Math.random());
    const v = new THREE.Vector3();

    for (let i = 0; i < N; i++) {
      target(-1, i, slots[i], v);
      pos.set([v.x, v.y, v.z], i * 3);
      tgt.set([v.x, v.y, v.z], i * 3);
      col.set([INK.r, INK.g, INK.b], i * 3);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const points = new THREE.Points(geo, new THREE.PointsMaterial({
      size: 0.062, vertexColors: true, transparent: true, opacity: 0.92,
      sizeAttenuation: true,
    }));
    // recentre: layout spans x∈[-2.4, 4.4], y∈[-3.2, 2.8]
    points.position.set(-1, 0.2, 0);
    scene.add(points);

    // E — connectors from body text to the entries it cites
    const LINKS = 46;
    const linkPos = new Float32Array(LINKS * 6);
    const linkGeo = new THREE.BufferGeometry();
    linkGeo.setAttribute("position", new THREE.BufferAttribute(linkPos, 3));
    const linkMat = new THREE.LineBasicMaterial({ color: 0x8a8a80, transparent: true, opacity: 0 });
    const links = new THREE.LineSegments(linkGeo, linkMat);
    links.position.copy(points.position);
    scene.add(links);
    const linkPairs = Array.from({ length: LINKS }, (_, k) => {
      const from = Math.floor((k * 97) % (N * (1 - REF_FRACTION)));
      const refStart = N - Math.floor(N * REF_FRACTION);
      return [from, refStart + ((k * 31) % Math.floor(N * REF_FRACTION))];
    });

    // Layout occupies roughly x∈[-2.5, 4.5], y∈[-3.2, 2.8]; frame it whole.
    const SPAN_Y = 6.6, SPAN_X = 7.4;
    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h);          // must update CSS size, not just the buffer
      camera.aspect = w / h;
      const vFov = (camera.fov * Math.PI) / 180;
      const distV = (SPAN_Y / 2) / Math.tan(vFov / 2);
      const distH = (SPAN_X / 2) / Math.tan(vFov / 2) / camera.aspect;
      camera.position.z = Math.max(distV, distH) * 1.12;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    let lastStage = -2;
    let raf = 0;
    const clock = new THREE.Clock();
    const tmp = new THREE.Color();

    const frame = () => {
      raf = requestAnimationFrame(frame);
      const st = stageRef.current;
      const t = clock.getElapsedTime();

      const p = geo.attributes.position.array as Float32Array;
      const c = geo.attributes.color.array as Float32Array;

      if (st !== lastStage) {                        // stage changed → new targets
        lastStage = st;
        for (let i = 0; i < N; i++) {
          target(st, i, slots[i], v);
          tgt.set([v.x, v.y, v.z], i * 3);
          if (!reduced) {                            // burst outward, then settle
            const o = i * 3;
            const a = rand[i] * Math.PI * 2;
            const r = 0.35 + rand[(i + 7) % N] * 0.55;
            p[o] += Math.cos(a) * r;
            p[o + 1] += Math.sin(a) * r * 0.7;
            p[o + 2] += (rand[(i + 3) % N] - 0.5) * 0.6;
          }
        }
      }

      for (let i = 0; i < N; i++) {
        const o = i * 3;
        const ease = reduced ? 1 : 0.03 + rand[i] * 0.055;
        const drift = reduced ? 0 : Math.sin(t * (1.1 + rand[i]) + i * 0.35) * 0.007;
        p[o] += (tgt[o] - p[o]) * ease;
        p[o + 1] += (tgt[o + 1] - p[o + 1]) * ease + drift;
        p[o + 2] += (tgt[o + 2] - p[o + 2]) * ease;

        const s = slots[i];
        // colour tracks what the algorithm has established so far
        let want = ASH;
        if (st >= 0) want = INK;
        if (st >= 1 && s.float) want = LIME;
        if (st >= 3 && s.ref) want = st >= 4 ? (s.unparsed ? WARN : LIME) : INK;
        tmp.setRGB(c[o], c[o + 1], c[o + 2]).lerp(want, 0.06);
        c[o] = tmp.r; c[o + 1] = tmp.g; c[o + 2] = tmp.b;
      }
      geo.attributes.position.needsUpdate = true;
      geo.attributes.color.needsUpdate = true;

      const showLinks = st >= 5 ? 0.5 : 0;
      linkMat.opacity += (showLinks - linkMat.opacity) * 0.05;
      if (linkMat.opacity > 0.01) {
        for (let k = 0; k < LINKS; k++) {
          const [a, b] = linkPairs[k];
          linkPos[k * 6] = p[a * 3]; linkPos[k * 6 + 1] = p[a * 3 + 1]; linkPos[k * 6 + 2] = p[a * 3 + 2];
          linkPos[k * 6 + 3] = p[b * 3]; linkPos[k * 6 + 4] = p[b * 3 + 1]; linkPos[k * 6 + 5] = p[b * 3 + 2];
        }
        linkGeo.attributes.position.needsUpdate = true;
      }

      if (!reduced) {
        points.rotation.y = Math.sin(t * 0.22) * 0.09;
        links.rotation.y = points.rotation.y;
      }
      renderer.render(scene, camera);
    };
    frame();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      geo.dispose(); linkGeo.dispose(); linkMat.dispose();
      (points.material as THREE.Material).dispose();
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, []);

  return <div className="parse-scene" ref={host} aria-hidden="true" />;
}

export { STAGES };
