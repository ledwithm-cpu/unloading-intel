import { useMemo, useRef, useState } from "react";
import type { Frames, Session } from "../types";

type Polys = Record<string, number[][]>;
const COLORS: Record<string, string> = { belt: "#E39A2B", belt_reach: "#E3C48A", dock_door: "#C8463E", far_end: "#8E5BB5", pile_side: "#1E8E7E", floor_side: "#3C7DC4" };

function inside(p: number[], poly: number[][]) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}

function tally(frames: Frames | null, polys: Polys, order: string[]) {
  const out: Record<string, { n: number; u: number; w: number }> = {};
  [...order, "away"].forEach((z) => (out[z] = { n: 0, u: 0, w: 0 }));
  if (!frames) return out;
  for (let f = 0; f < frames.frames.length; f += 5) {
    for (const p of frames.frames[f]) {
      const hip = p[20] >= 0 && p[22] >= 0 ? [(p[20] + p[22]) / 2, (p[21] + p[23]) / 2] : [(p[0] + p[2]) / 2, (p[1] + p[3]) / 2];
      const z = order.find((name) => inside(hip, polys[name])) ?? "away";
      out[z].n++; if (p[4] === 0) out[z].u++; if (p[4] === 2) out[z].w++;
    }
  }
  return out;
}

export default function Zones({ session, frames }: { session: Session; frames: Frames | null }) {
  const saved = useMemo(() => Object.fromEntries(Object.entries(session.zones.zones).map(([k, z]) => [k, z.polygon])) as Polys, [session]);
  const [polys, setPolys] = useState<Polys>(() => JSON.parse(JSON.stringify(saved)));
  const [sel, setSel] = useState("far_end");
  const [drawing, setDrawing] = useState<number[][] | null>(null);
  const [newName, setNewName] = useState("");
  const [order, setOrder] = useState(session.zones.zone_priority);
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ zone: string; i: number } | null>(null);
  const { width: W, height: H } = session.video;

  const pt = (e: React.PointerEvent | React.MouseEvent) => {
    const r = svg.current!.getBoundingClientRect();
    return [Math.round(((e.clientX - r.left) / r.width) * W), Math.round(((e.clientY - r.top) / r.height) * H)];
  };
  const before = useMemo(() => tally(frames, saved, session.zones.zone_priority), [frames, saved, session]);
  const after = useMemo(() => tally(frames, polys, order), [frames, polys, order]);
  const beltChanged = JSON.stringify(polys.belt) !== JSON.stringify(saved.belt);
  const perMin = (n: number) => ((n * 5) / session.video.sample_fps / 60).toFixed(1);
  const label = (z: string) => session.zones.zones[z]?.label ?? (z === "away" ? "Outside all zones" : z.replace(/_/g, " "));

  const download = () => {
    const cfg = JSON.parse(JSON.stringify(session.zones));
    for (const [k, poly] of Object.entries(polys)) cfg.zones[k] = { ...(cfg.zones[k] ?? { label: label(k), kind: "work" }), polygon: poly };
    cfg.zone_priority = order;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(cfg, null, 2)], { type: "application/json" }));
    a.download = "zones.json"; a.click();
  };
  const finishDrawing = () => {
    if (!drawing || drawing.length < 3) return;
    const key = (newName.trim() || "new zone").toLowerCase().replace(/\s+/g, "_");
    session.zones.zones[key] = { label: newName.trim() || "New zone", kind: "work", polygon: drawing };
    setPolys({ ...polys, [key]: drawing }); setOrder([key, ...order]); setSel(key); setDrawing(null); setNewName("");
  };

  return (
    <article className="page">
      <h1>Zones</h1>
      <p className="lede">Zones tell the system where the belt is and where people work. Drag a corner to reshape one, or draw a new one. The table updates straight away from the stored data, with no need to process the video again.</p>
      <div className="zones">
        <div className="zone-canvas">
          <svg ref={svg} viewBox={`0 0 ${W} ${H}`}
            onPointerMove={(e) => { if (drag.current) { const p = pt(e); const d = drag.current; setPolys((s) => ({ ...s, [d.zone]: s[d.zone].map((q, i) => (i === d.i ? p : q)) })); } }}
            onPointerUp={() => (drag.current = null)} onPointerLeave={() => (drag.current = null)}
            onClick={(e) => { if (drawing) setDrawing([...drawing, pt(e)]); }}
            style={{ cursor: drawing ? "crosshair" : "default" }}>
            <image href="data/frame.jpg" width={W} height={H} />
            {Object.entries(polys).map(([k, poly]) => (
              <polygon key={k} points={poly.map((p) => p.join(",")).join(" ")} fill={COLORS[k] ?? "#D9822B"} fillOpacity={k === sel ? 0.28 : 0.1}
                stroke={COLORS[k] ?? "#D9822B"} strokeWidth={k === sel ? 4 : 2} strokeDasharray={k === "belt_reach" ? "10 8" : undefined}
                onClick={() => !drawing && setSel(k)} style={{ cursor: "pointer" }} />
            ))}
            {!drawing && polys[sel]?.map((p, i) => (
              <circle key={i} cx={p[0]} cy={p[1]} r={11} fill="#fff" stroke={COLORS[sel] ?? "#D9822B"} strokeWidth={4} style={{ cursor: "grab" }}
                onPointerDown={(e) => { (e.target as Element).setPointerCapture(e.pointerId); drag.current = { zone: sel, i }; }} />
            ))}
            {drawing && <polyline points={drawing.map((p) => p.join(",")).join(" ")} fill="none" stroke="#fff" strokeWidth={3} />}
            {drawing?.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={7} fill="#fff" />)}
          </svg>
        </div>
        <div className="zone-side">
          <div className="zone-pick">
            {Object.keys(polys).map((k) => (
              <button key={k} className={k === sel ? "is-on" : ""} onClick={() => setSel(k)}><i style={{ background: COLORS[k] ?? "#D9822B" }} />{label(k)}</button>
            ))}
          </div>
          {session.zones.zones[sel]?.note && <p className="note">{session.zones.zones[sel].note}</p>}
          <div className="zone-actions">
            {drawing ? (
              <>
                <input placeholder="Name the new zone" value={newName} onChange={(e) => setNewName(e.target.value)} />
                <button className="btn" onClick={finishDrawing} disabled={drawing.length < 3}>Finish zone ({drawing.length} points)</button>
                <button className="btn ghost" onClick={() => setDrawing(null)}>Cancel</button>
              </>
            ) : (
              <>
                <button className="btn" onClick={() => setDrawing([])}>Draw a new zone</button>
                <button className="btn ghost" onClick={() => setPolys(JSON.parse(JSON.stringify(saved)))}>Reset</button>
                <button className="btn ghost" onClick={download}>Download zones.json</button>
              </>
            )}
          </div>
          {drawing && <p className="note">Click on the picture to place each corner, then finish.</p>}
          <table className="plain compact">
            <thead><tr><th>Working area</th><th>People-minutes</th><th>Was</th><th>Unloading</th><th>Waiting</th></tr></thead>
            <tbody>
              {[...order, "away"].map((z) => {
                const a = after[z], b = before[z] ?? { n: 0, u: 0, w: 0 };
                return (
                  <tr key={z} className={a.n !== b.n ? "changed" : ""}>
                    <td>{label(z)}</td><td><strong>{perMin(a.n)}</strong></td><td className="dim">{perMin(b.n)}</td>
                    <td>{a.n ? Math.round((a.u / a.n) * 100) + "%" : ""}</td><td>{a.n ? Math.round((a.w / a.n) * 100) + "%" : ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {beltChanged && <p className="banner">You moved the belt zone. Belt coverage is measured from the picture inside it, so this one needs a two-minute re-run: save the file to config/zones.json and run “python -m pipeline.belt”.</p>}
          <p className="note">To keep changes, download the file and replace config/zones.json, then run “python -m analytics.run”.</p>
        </div>
      </div>
    </article>
  );
}
