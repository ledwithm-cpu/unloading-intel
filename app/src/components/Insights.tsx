import { useState } from "react";
import type { Card } from "../types";

export default function Insights({ cards, onJump }: { cards: Card[]; onJump: (t: number) => void }) {
  const [open, setOpen] = useState(cards[0]?.id);
  return (
    <section className="insights" aria-label="What we found">
      <div className="ins-ev" style={{ marginBottom: 16 }}>
        <span>Walkthrough moments</span>
        {[
          [2, "0:00 · Busy belt, people loading"],
          [572, "9:32 · Stopped with freight on it"],
          [270, "4:30 · Belt near-empty, full team"],
          [1336, "22:16 · The line's best minute"],
          [164, "2:44 · Crossing the belt"],
          [810, "13:30 · Smoking among the parcels"],
        ].map(([t, label]) => (
          <button key={label as string} className="jump" onClick={() => onJump(t as number)}>{label}</button>
        ))}
      </div>
      <h2>What we found</h2>
      {cards.map((c) => {
        const on = open === c.id;
        return (
          <article key={c.id} className={on ? "ins is-open" : "ins"}>
            <button className="ins-head" onClick={() => setOpen(on ? "" : c.id)} aria-expanded={on}>
              <span className="ins-num">{c.metric.value}</span>
              <span className="ins-title">{c.title}<small>{c.metric.label}</small></span>
            </button>
            {on && (
              <div className="ins-body">
                <dl>
                  <dt>What happened</dt><dd>{c.what}</dd>
                  <dt>Why it matters</dt><dd>{c.why}</dd>
                  <dt>What to try now</dt><dd>{c.action}</dd>
                  {c.next && (<><dt>Where the system goes next</dt><dd>{c.next}</dd></>)}
                </dl>
                <div className="ins-ev">
                  <span>See it in the video</span>
                  {c.evidence.map((e, i) => <button key={i} className="jump" onClick={() => onJump(e.t_sec)}>{e.label}</button>)}
                </div>
              </div>
            )}
          </article>
        );
      })}
    </section>
  );
}
