import type { Session } from "../types";
import { BELT, pct } from "../lib";

const EXAMPLE = [
  { name: "Bay BN2", state: 3, people: 5, unloading: 1, note: "Belt stopped, near-empty, for 70 seconds" },
  { name: "Bay BN3", state: 0, people: 4, unloading: 4, note: "Flowing steadily" },
  { name: "Bay BN4", state: 2, people: 3, unloading: 3, note: "Belt full and stopped twice in five minutes" },
];

export default function Site({ session }: { session: Session }) {
  const h = session.insights.headline;
  const rel = session.events.filter((e) => e.type === "release_window");
  return (
    <article className="page">
      <h1>Site view</h1>
      <p className="banner">This page is an illustration. Bay BN1 shows measured figures from this session. Bays BN2 to BN4 are example data, to show how bays would be compared once each has a camera.</p>
      <div className="bays">
        <div className="bay real">
          <h2>Bay BN1 <span className="tag">Measured</span></h2>
          <p className="big">{pct(h.productive_share)}</p><p>of the session the belt moved freight</p>
          <p>{h.avg_people.toFixed(1)} people on average. {rel.length} windows where about two people could have been released.</p>
        </div>
        {EXAMPLE.map((b) => (
          <div className="bay" key={b.name}>
            <h2>{b.name} <span className="tag ex">Example</span></h2>
            <p><span className={b.state === 1 ? "chip dark" : "chip"} style={{ background: BELT[b.state].color }}>{BELT[b.state].label}</span></p>
            <p>{b.people} people, {b.unloading} unloading</p>
            <p className="dim">{b.note}</p>
          </div>
        ))}
      </div>
      <div className="alert">
        <h2>Example alert</h2>
        <p><strong>Move two people from BN2 to BN4.</strong> BN2 has four people waiting at an empty belt. BN4 is saturated with everyone unloading. The walk is about 40 seconds and BN2’s next truck is not at the door.</p>
        <p className="dim">An alert like this needs three things the single-camera session already produces for one bay: belt state, people waiting, and how long the gap has lasted. It also needs a rule for when a move is worth the walk. In this session most gaps lasted under a minute, so the stronger finding was the staffing level per phase, not minute-by-minute moves.</p>
      </div>
    </article>
  );
}
