import type { Ev, Sensitivity, Session } from "./types";

/** Same run-finding rule as analytics/events.py: runs of at least `min` seconds, bridging gaps of up to `gap`. */
function segments(flags: boolean[], min: number, gap = 2): [number, number][] {
  const out: [number, number][] = [];
  let start: number | null = null, miss = 0;
  flags.forEach((f, i) => {
    if (f) { if (start === null) start = i; miss = 0; }
    else if (start !== null) { miss++; if (miss > gap) { out.push([start, i - miss]); start = null; miss = 0; } }
  });
  if (start !== null) out.push([start, flags.length - 1 - miss]);
  return out.filter(([a, b]) => b - a + 1 >= min);
}

const avg = (a: number[], s: number, e: number) => { let t = 0; for (let i = s; i <= e; i++) t += a[i]; return t / (e - s + 1); };
const rollMedian = (a: number[], k: number) => a.map((_, i) => {
  const w = a.slice(Math.max(0, i - k), i + k + 1).sort((x, y) => x - y);
  return w[Math.floor(w.length / 2)];
});
const rollMean = (a: number[], k: number) => a.map((_, i) => avg(a, Math.max(0, i - k), Math.min(a.length - 1, i + k)));

export const sameAsDefault = (s: Sensitivity, d: Sensitivity) =>
  s.near_empty_pct === d.near_empty_pct && s.min_stop_seconds === d.min_stop_seconds && s.min_free_seconds === d.min_free_seconds;

/** Returns the session with belt states and belt/release events recomputed for these settings.
 *  At the default settings the stored results are returned unchanged, so the screen matches the findings exactly. */
export function applySensitivity(session: Session, s: Sensitivity): Session {
  if (sameAsDefault(s, session.sensitivity_defaults)) return session;
  const tl = session.timeline;
  const occ = rollMedian(tl.occupancy, 2);
  const keys = session.legend.belt_states;          // flowing, running_empty, stopped_loaded, stopped_empty
  const state = occ.map((o, i) => {
    const loaded = o * 100 >= s.near_empty_pct;
    return tl.moving[i] ? (loaded ? 0 : 1) : (loaded ? 2 : 3);
  });
  const make = (type: string, a: number, b: number, id: number): Ev => ({
    id, type, start: a, end: b + 1, duration: b - a + 1,
    present: +avg(tl.present, a, b).toFixed(2), unloading: +avg(tl.unloading, a, b).toFixed(2),
    waiting: +avg(tl.waiting, a, b).toFixed(2), occupancy: +avg(tl.occupancy, a, b).toFixed(3), details: {},
  });
  let id = 100000;
  const events: Ev[] = session.events.filter((e) => !["running_empty", "stopped_loaded", "stopped_empty", "release_window"].includes(e.type));
  for (const k of [1, 2, 3]) for (const [a, b] of segments(state.map((v) => v === k), s.min_stop_seconds)) events.push(make(keys[k], a, b, id++));
  const wait = rollMean(tl.waiting, 5);
  const free = state.map((v, i) => (v === 1 || v === 3) && wait[i] >= 1.5);
  for (const [a, b] of segments(free, s.min_free_seconds)) events.push(make("release_window", a, b, id++));
  events.sort((x, y) => x.start - y.start);
  return { ...session, timeline: { ...tl, belt_state: state }, events };
}

export function stateShares(session: Session) {
  const n = session.timeline.belt_state.length;
  return Object.fromEntries(session.legend.belt_states.map((k, i) => [k, session.timeline.belt_state.filter((v) => v === i).length / n]));
}
