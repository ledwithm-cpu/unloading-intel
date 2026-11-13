import { useMemo, useState } from "react";
import type { Session } from "../types";
import { EVENT_GROUP, EVENT_LABEL, clock, dur, mmss } from "../lib";

const GROUPS = ["All", "Belt", "People", "Safety"];

export default function Events({ session, onJump, panel }: { session: Session; onJump: (t: number) => void; panel?: React.ReactNode }) {
  const [group, setGroup] = useState("All");
  const [all, setAll] = useState(false);
  const rows = useMemo(() => session.events
    .filter((e) => group === "All" || EVENT_GROUP[e.type] === group)
    .filter((e) => e.type !== "leaning_on_belt" || e.duration >= 15)
    .sort((a, b) => a.start - b.start), [session, group]);
  const shown = all ? rows : [...rows].sort((a, b) => b.duration - a.duration).slice(0, 8).sort((a, b) => a.start - b.start);
  return (
    <section className="events" aria-label="Moments to review">
      <div className="events-top">
        <h2>Moments to review</h2>
        <div className="seg" role="tablist">
          {GROUPS.map((g) => <button key={g} role="tab" aria-selected={group === g} className={group === g ? "is-on" : ""} onClick={() => setGroup(g)}>{g}</button>)}
        </div>
      </div>
      {panel}
      <table>
        <thead><tr><th>Time</th><th>What happened</th><th>Lasted</th><th>People there</th><th>Waiting</th><th /></tr></thead>
        <tbody>
          {shown.map((e) => (
            <tr key={e.id} onClick={() => onJump(e.start)}>
              <td><strong>{mmss(e.start)}</strong><small>{clock(session.video.clock_start, e.start)}</small></td>
              <td>{EVENT_LABEL[e.type] ?? e.type}{e.details?.belt_moving ? <em> while the belt was moving</em> : null}</td>
              <td>{dur(e.duration)}</td>
              <td>{e.present ? e.present.toFixed(1) : ""}</td>
              <td>{EVENT_GROUP[e.type] === "Safety" ? "" : e.waiting.toFixed(1)}</td>
              <td><button className="jump" onClick={(ev) => { ev.stopPropagation(); onJump(e.start); }}>Show me</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 8 && <button className="btn ghost more" onClick={() => setAll(!all)}>{all ? "Show the 8 longest" : `Show all ${rows.length}`}</button>}
      <p className="note">The longest moments are shown first. Leaning is listed when it lasts 15 seconds or more. Belt crossings are candidates: some are a long reach across the belt.</p>
    </section>
  );
}
