import { useCallback, useEffect, useRef, useState } from "react";
import type { Frames, Session } from "../types";
import { BELT, pct } from "../lib";
import VideoStage, { NowStrip } from "../components/VideoStage";
import Timeline from "../components/Timeline";
import Insights from "../components/Insights";
import Events from "../components/Events";

type Props = { session: Session; frames: Frames | null; pendingSeek: React.MutableRefObject<number | null>; seekTick: number; active: boolean };

export default function SessionPage({ session, frames, pendingSeek, seekTick, active }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [t, setT] = useState(0);
  const [show, setShow] = useState({ people: true, skeleton: true, zones: false });
  const h = session.insights.headline;

  const seek = useCallback((time: number, play = false) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = time;
    setT(time);
    if (play) v.play().catch(() => {});
  }, []);
  const jump = useCallback((time: number) => {
    seek(Math.max(0, time - 2), true);
    videoRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [seek]);

  useEffect(() => {
    if (pendingSeek.current !== null) { jump(pendingSeek.current); pendingSeek.current = null; }
  }, [seekTick, jump, pendingSeek]);
  useEffect(() => { if (!active) videoRef.current?.pause(); }, [active]);

  const lostMin = Math.round(h.lost_seconds / 60), totalMin = Math.round(h.video_seconds / 60);
  return (
    <div className="session">
      <section className="lead">
        <h1>The belt moved freight {pct(h.productive_share)} of the time. The other {lostMin} of {totalMin} minutes went to stops and gaps.</h1>
        <div className="where" role="img" aria-label="Where the session time went">
          {BELT.map((b) => {
            const share = h.belt_state_share[b.key];
            return (
              <div key={b.key} style={{ flex: share }}>
                <div className="where-bar" style={{ background: b.color }} />
                <strong>{pct(share)}</strong>
                <span>{b.label}</span>
              </div>
            );
          })}
        </div>
      </section>

      <div className="work">
        <section className="watch" aria-label="Video">
          <VideoStage session={session} frames={frames} videoRef={videoRef} show={show} onTime={setT} />
          <NowStrip session={session} t={t} />
          <Timeline session={session} t={t} onSeek={(x) => seek(x)} />
          <div className="toggles">
            <span>Show on video</span>
            {([["people", "People"], ["skeleton", "Body outline"], ["zones", "Zones"]] as const).map(([k, label]) => (
              <label key={k}><input type="checkbox" checked={show[k]} onChange={(e) => setShow({ ...show, [k]: e.target.checked })} />{label}</label>
            ))}
          </div>
        </section>
        <Insights cards={session.insights.cards} onJump={jump} />
      </div>
      <Events session={session} onJump={jump} />
    </div>
  );
}
