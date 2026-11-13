export const BELT = [
  { key: "flowing", label: "Moving freight", color: "#1E8E7E" },
  { key: "running_empty", label: "Running near-empty", color: "#E2B93B" },
  { key: "stopped_loaded", label: "Stopped with freight on it", color: "#C8463E" },
  { key: "stopped_empty", label: "Stopped, near-empty", color: "#8A97A0" },
];
export const PEOPLE = [
  { key: "unloading", label: "Unloading", color: "#1E8E7E" },
  { key: "other", label: "Other activity", color: "#6C8EAD" },
  { key: "waiting", label: "Waiting", color: "#C8463E" },
];
export const DETAIL_LABEL: Record<string, string> = { leaning: "Leaning on belt", crossing: "Crossing the belt" };
export const EVENT_LABEL: Record<string, string> = {
  stopped_loaded: "Belt stopped with freight on it",
  stopped_empty: "Belt stopped, near-empty",
  running_empty: "Belt running near-empty",
  low_engagement: "Three or more present, at most one unloading",
  release_window: "People free to help another bay",
  under_pressure: "Bay under pressure",
  belt_crossing: "Someone crossed the belt",
  leaning_on_belt: "Someone leaning on the belt",
};
export const EVENT_GROUP: Record<string, string> = {
  stopped_loaded: "Belt", stopped_empty: "Belt", running_empty: "Belt",
  low_engagement: "People", release_window: "People", under_pressure: "People",
  belt_crossing: "Safety", leaning_on_belt: "Safety",
};
export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
export function clock(start: string, s: number) {
  const [h, m, sec] = start.split(":").map(Number);
  const t = h * 3600 + m * 60 + sec + Math.floor(s);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(Math.floor(t / 3600))}:${p(Math.floor((t % 3600) / 60))}:${p(t % 60)}`;
}
export const pct = (x: number) => `${Math.round(x * 100)}%`;
export const dur = (s: number) => (s >= 60 ? `${Math.floor(s / 60)} min ${Math.round(s % 60)} s` : `${Math.round(s)} s`);
