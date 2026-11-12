import { useMemo, useRef, useState } from "react";
import type { Session } from "../types";
import { BELT, EVENT_LABEL, PEOPLE, clock, mmss } from "../lib";

function runs(a: number[]) {
  const out: { v: number; s: number; e: number }[] = [];
  a.forEach((v, i) => { const l = out[out.length - 1]; if (l && l.v === v) l.e = i + 1; else out.push({ v, s: i, e: i + 1 }); });
  return out;
}
const smooth = (a: number[], k: number) => a.map((_, i) => { let s = 0, n = 0; for (let j = Math.max(0, i - k); j <= Math.min(a.length - 1, i + k); j++) { s += a[j]; n++; } return s / n; });

const MARKS = [
  { type: "release_window", label: "People free", color: "#6C8EAD" },
  { type: "belt_crossing", label: "Belt crossed", color: "#18242C" },
];

export default function Timeline({ session, t, onSeek }: { session: Session; t: number; onSeek: (t: number) => void }) {
  const N = session.video.duration;
  const tl = session.timeline;
  const box = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const beltRuns = useMemo(() => runs(tl.belt_state), [tl]);
  const areas = useMemo(() => {
    const u = smooth(tl.unloading, 4), o = smooth(tl.other, 4), w = smooth(tl.waiting, 4);
    const max = 8, H = 60;
    const y = (v: number) => H - (Math.min(v, max) / max) * H;
    const band = (lo: number[], hi: number[]) =>
      "M" + hi.map((v, i) => `${i},${y(v).toFixed(1)}`).join("L") + "L" + lo.map((v, i) => `${i},${y(v).toFixed(1)}`).reverse().join("L") + "Z";
    const zero = u.map(() => 0), a = u, b = u.map((v, i) => v + o[i]), c = b.map((v, i) => v + w[i]);
    return [band(zero, a), band(a, b), band(b, c)];
  }, [tl]);

  const at = (e: React.MouseEvent) => {
    const r = box.current!.getBoundingClientRect();
    return Math.max(0, Math.min(N - 1, ((e.clientX - r.left) / r.width) * N));
  };
  const i = hover === null ? null : Math.floor(hover);

  return (
    <div className="tl">
      <div className="tl-labels" aria-hidden="true">
        <span style={{ height: 30 }}>Belt</span>
        <span style={{ height: 64 }}>People</span>
        <span style={{ height: 22 }}>Moments</span>
      </div>
      <div className="tl-main">
        <div className="tl-box" ref={box} onMouseMove={(e) => setHover(at(e))} onMouseLeave={() => setHover(null)}
          onClick={(e) => onSeek(at(e))} role="slider" tabIndex={0} aria-label="Session timeline" aria-valuemin={0} aria-valuemax={N} aria-valuenow={Math.floor(t)}
          onKeyDown={(e) => { if (e.key === "ArrowRight") onSeek(Math.min(N - 1, t + 5)); if (e.key === "ArrowLeft") onSeek(Math.max(0, t - 5)); }}>
          <svg viewBox={`0 0 ${N} 30`} preserveAspectRatio="none" style={{ height: 30 }}>
            {beltRuns.map((r) => <rect key={r.s} x={r.s} y={2} width={r.e - r.s} height={26} fill={BELT[r.v].color} />)}
          </svg>
          <svg viewBox={`0 0 ${N} 60`} preserveAspectRatio="none" style={{ height: 64 }}>
            {areas.map((d, k) => <path key={k} d={d} fill={PEOPLE[k].color} />)}
          </svg>
          <svg viewBox={`0 0 ${N} 22`} preserveAspectRatio="none" style={{ height: 22 }}>
            {session.events.filter((e) => MARKS.some((m) => m.type === e.type)).map((e) => {
              const m = MARKS.find((x) => x.type === e.type)!;
              return <rect key={e.id} x={e.start} y={m.type === "belt_crossing" ? 12 : 2} width={Math.max(6, e.duration)} height={8} fill={m.color}><title>{EVENT_LABEL[e.type]} at {mmss(e.start)}</title></rect>;
            })}
          </svg>
          <div className="tl-head" style={{ left: `${(t / N) * 100}%` }} />
          {hover !== null && i !== null && (
            <>
              <div className="tl-hover" style={{ left: `${(hover / N) * 100}%` }} />
              <div className="tl-tip" style={{ left: `${Math.min(82, Math.max(0, (hover / N) * 100))}%` }}>
                <strong>{mmss(hover)}</strong> <span className="dim">camera clock {clock(session.video.clock_start, hover)}</span><br />
                {BELT[tl.belt_state[i]].label}, {Math.round(tl.occupancy[i] * 100)}% of belt covered<br />
                {Math.round(tl.unloading[i])} unloading, {Math.round(tl.other[i])} other, {Math.round(tl.waiting[i])} waiting
              </div>
            </>
          )}
        </div>
        <div className="tl-axis" aria-hidden="true">
          {Array.from({ length: Math.floor(N / 300) + 1 }, (_, k) => <span key={k} style={{ left: `${((k * 300) / N) * 100}%` }}>{k * 5} min</span>)}
        </div>
        <ul className="legend">
          {BELT.map((b) => <li key={b.key}><i style={{ background: b.color }} />{b.label}</li>)}
          <li className="gap" />
          {PEOPLE.map((p) => <li key={p.key}><i style={{ background: p.color }} />{p.label}</li>)}
          <li className="gap" />
          {MARKS.map((m) => <li key={m.type}><i style={{ background: m.color }} />{m.label}</li>)}
        </ul>
      </div>
    </div>
  );
}
