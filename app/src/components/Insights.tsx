import { useState } from "react";
import type { Card } from "../types";

export default function Insights({ cards, onJump }: { cards: Card[]; onJump: (t: number) => void }) {
  const [open, setOpen] = useState(cards[0]?.id);
  return (
    <section className="insights" aria-label="What we found">
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
                  <dt>What to try</dt><dd>{c.action}</dd>
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
