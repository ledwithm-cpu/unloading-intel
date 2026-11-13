export type Zone = { label: string; kind: string; polygon: number[][]; note?: string };
export type Ev = {
  id: number; type: string; start: number; end: number; duration: number;
  present: number; unloading: number; waiting: number; occupancy: number; details: Record<string, any>;
};
export type Evidence = { t_sec: number; label: string; event_id?: number };
export type Card = { id: string; title: string; what: string; why: string; action: string; next?: string; metric: { label: string; value: string }; evidence: Evidence[] };
export type Session = {
  video: { src: string; width: number; height: number; duration: number; clock_start: string; date: string; sample_fps: number };
  legend: { states: string[]; details: (string | null)[]; zones: string[]; belt_states: string[] };
  zones: { zones: Record<string, Zone>; zone_priority: string[] };
  timeline: { belt_state: number[]; occupancy: number[]; throughput: number[]; present: number[]; unloading: number[]; other: number[]; waiting: number[] };
  events: Ev[];
  insights: { headline: any; cards: Card[] };
  review: any;
};
/** [x1,y1,x2,y2,state,detail,zone,track, 12 body points as x,y pairs (-1 = not visible)] */
export type Person = number[];
export type Frames = { stride: number; frames: Person[][] };
