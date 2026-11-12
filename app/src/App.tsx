import { useCallback, useEffect, useRef, useState } from "react";
import type { Frames, Session } from "./types";
import SessionPage from "./pages/SessionPage";
import Accuracy from "./pages/Accuracy";
import Zones from "./pages/Zones";
import Site from "./pages/Site";

const PAGES = [
  { id: "session", label: "Session" },
  { id: "accuracy", label: "How accurate is this?" },
  { id: "zones", label: "Zones" },
  { id: "site", label: "Site view" },
];

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [frames, setFrames] = useState<Frames | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState("session");
  const pendingSeek = useRef<number | null>(null);
  const [seekTick, setSeekTick] = useState(0);

  useEffect(() => {
    fetch("data/session.json").then((r) => r.json()).then(setSession)
      .catch(() => setError("The session data did not load. Run “python -m analytics.export” and reload."));
    fetch("data/frames.json").then((r) => r.json()).then(setFrames).catch(() => {});
  }, []);

  const jumpTo = useCallback((t: number) => {
    pendingSeek.current = Math.max(0, t);
    setPage("session");
    setSeekTick((n) => n + 1);
  }, []);

  if (error) return <p className="load-msg">{error}</p>;
  if (!session) return <p className="load-msg">Loading the session…</p>;

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <strong>Unloading review</strong>
            <span className="brand-sub">Bay BN1, {session.video.date}, from 06:05</span>
          </div>
        </div>
        <nav aria-label="Pages">
          {PAGES.map((p) => (
            <button key={p.id} className={page === p.id ? "nav-btn is-on" : "nav-btn"} onClick={() => setPage(p.id)}
              aria-current={page === p.id ? "page" : undefined}>{p.label}</button>
          ))}
        </nav>
      </header>
      <main>
        <div hidden={page !== "session"}>
          <SessionPage session={session} frames={frames} pendingSeek={pendingSeek} seekTick={seekTick} active={page === "session"} />
        </div>
        {page === "accuracy" && <Accuracy session={session} jumpTo={jumpTo} />}
        {page === "zones" && <Zones session={session} frames={frames} />}
        {page === "site" && <Site session={session} />}
      </main>
      <footer className="foot">
        Prototype built on 28.5 minutes of footage from one camera. Figures are measured by computer vision and checked by hand on a sample;
        see “How accurate is this?” for what that means.
      </footer>
    </div>
  );
}
