import { useEffect, useRef } from "react";
import type { Frames, Session } from "../types";
import { BELT, DETAIL_LABEL, PEOPLE } from "../lib";

const BONES = [[0, 2], [2, 4], [1, 3], [3, 5], [0, 1], [0, 6], [1, 7], [6, 7], [6, 8], [8, 10], [7, 9], [9, 11]];
const ZONE_STROKE: Record<string, string> = { belt: "#E39A2B", belt_reach: "rgba(227,154,43,.45)" };

type Props = {
  session: Session; frames: Frames | null; videoRef: React.RefObject<HTMLVideoElement>;
  show: { people: boolean; skeleton: boolean; zones: boolean }; onTime: (t: number) => void;
};

export default function VideoStage({ session, frames, videoRef, show, onTime }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const showRef = useRef(show);
  showRef.current = show;

  useEffect(() => {
    let raf = 0;
    let last = -1;
    const { width: W, height: H, sample_fps } = session.video;
    const draw = () => {
      const v = videoRef.current, c = canvasRef.current;
      if (v && c) {
        const rect = c.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        if (c.width !== Math.round(rect.width * dpr)) { c.width = Math.round(rect.width * dpr); c.height = Math.round(rect.height * dpr); }
        const ctx = c.getContext("2d")!;
        const k = c.width / W;
        ctx.setTransform(k, 0, 0, k, 0, 0);
        ctx.clearRect(0, 0, W, H);
        const s = showRef.current;
        if (s.zones) {
          for (const [name, z] of Object.entries(session.zones.zones)) {
            ctx.beginPath();
            z.polygon.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
            ctx.closePath();
            ctx.lineWidth = name === "belt" ? 3 : 1.5;
            ctx.setLineDash(name === "belt" ? [] : [8, 6]);
            ctx.strokeStyle = ZONE_STROKE[name] ?? "rgba(255,255,255,.6)";
            ctx.stroke();
            if (name !== "belt" && name !== "belt_reach") {
              const cx = z.polygon.reduce((a, p) => a + p[0], 0) / z.polygon.length;
              const cy = z.polygon.reduce((a, p) => a + p[1], 0) / z.polygon.length;
              ctx.setLineDash([]);
              ctx.font = "500 15px Barlow, sans-serif";
              ctx.fillStyle = "rgba(255,255,255,.85)";
              ctx.fillText(z.label, cx - 30, cy);
            }
          }
          ctx.setLineDash([]);
        }
        const people = frames?.frames[Math.round(v.currentTime * sample_fps)] ?? [];
        if (s.people) {
          for (const p of people) {
            const color = PEOPLE[p[4]].color;
            const detail = session.legend.details[p[5]];
            if (s.skeleton) {
              ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.lineCap = "round";
              for (const [a, b] of BONES) {
                const ax = p[8 + a * 2], ay = p[9 + a * 2], bx = p[8 + b * 2], by = p[9 + b * 2];
                if (ax < 0 || bx < 0) continue;
                ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
              }
            }
            ctx.strokeStyle = color; ctx.lineWidth = 2.5;
            ctx.strokeRect(p[0], p[1], p[2] - p[0], p[3] - p[1]);
            const text = detail ? DETAIL_LABEL[detail] : PEOPLE[p[4]].label;
            ctx.font = "600 15px Barlow, sans-serif";
            const tw = ctx.measureText(text).width + 12;
            ctx.fillStyle = color; ctx.fillRect(p[0] - 1, Math.max(0, p[1] - 22), tw, 22);
            ctx.fillStyle = "#fff"; ctx.fillText(text, p[0] + 5, Math.max(16, p[1] - 6));
          }
        }
        if (Math.floor(v.currentTime) !== last) { last = Math.floor(v.currentTime); onTime(v.currentTime); }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [session, frames, videoRef, onTime]);

  return (
    <div className="stage">
      <video ref={videoRef} src={session.video.src} controls playsInline muted preload="metadata" />
      <canvas ref={canvasRef} aria-hidden="true" />
    </div>
  );
}

export function NowStrip({ session, t }: { session: Session; t: number }) {
  const i = Math.min(session.video.duration - 1, Math.max(0, Math.floor(t)));
  const tl = session.timeline;
  const b = BELT[tl.belt_state[i]];
  const u = Math.round(tl.unloading[i]), o = Math.round(tl.other[i]), w = Math.round(tl.waiting[i]);
  const n = u + o + w;
  return (
    <div className="now">
      <span className={b.key === "running_empty" ? "chip dark" : "chip"} style={{ background: b.color }}>Belt: {b.label.toLowerCase()}</span>
      <span>{n} {n === 1 ? "person" : "people"} in view: {u} unloading, {o} on other activity, {w} waiting</span>
    </div>
  );
}
