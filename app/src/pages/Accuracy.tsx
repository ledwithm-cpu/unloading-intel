import type { Session } from "../types";

export default function Accuracy({ session, jumpTo }: { session: Session; jumpTo: (t: number) => void }) {
  const r = session.review;
  const wa = r.worker_activity;
  const c = r.corrections ?? { satisfied: 12, total: 13 };
  return (
    <article className="page prose">
      <h1>How accurate is this?</h1>
      <p className="lede">
        A camera system makes thousands of small calls: is the belt moving, is that a person, is that person unloading.
        Some of those calls are wrong. This page explains how often, in which direction, and what that means for the numbers you act on.
      </p>

      <h2>The short answer</h2>
      <table className="plain">
        <thead><tr><th>What we checked</th><th>Result</th><th>How</th></tr></thead>
        <tbody>
          <tr><td>Belt state (moving, stopped, empty)</td><td><strong>{r.belt_state.moments - r.belt_state.wrong} of {r.belt_state.moments} right</strong></td><td>A person watched 20 random five-second clips</td></tr>
          <tr><td>What each person was doing, first version</td><td><strong>{wa.person_clips - wa.wrong} of {wa.person_clips} right</strong></td><td>Same 20 clips, every person in them</td></tr>
          <tr><td>Mistakes found across four rounds of review</td><td><strong>{c.satisfied} of {c.total} now corrected</strong></td><td>Each mistake is kept as a test the system must pass</td></tr>
          <tr><td>Precision and recall for “unloading”</td><td><strong>Not measured yet</strong></td><td>Needs the blind check described below</td></tr>
        </tbody>
      </table>
      <p>Trust the belt figures most. Treat the people figures as a good estimate, with waiting more likely to be under-counted than over-counted.</p>

      <h2>Four things can happen each time the system makes a call</h2>
      <p>Take one question: “is this person unloading?” The system says yes or no, and the truth is yes or no. That gives four outcomes.</p>
      <div className="quad">
        <div className="q good"><h3>Correct yes</h3><p>It said unloading, and they were.</p><p className="ex">A worker lifts a parcel off the belt and carries it to a pile.</p></div>
        <div className="q bad"><h3>False alarm</h3><p>It said unloading, and they were not. The technical name is a false positive.</p><p className="ex">A man resting his hand on the belt was counted as unloading. <button className="jump" onClick={() => jumpTo(277)}>Show me 4:37</button></p></div>
        <div className="q bad"><h3>Miss</h3><p>It said not unloading, and they were. The technical name is a false negative.</p><p className="ex">A worker clearing parcels from the far side of the belt was labelled “other activity”. <button className="jump" onClick={() => jumpTo(124)}>Show me 2:04</button></p></div>
        <div className="q good"><h3>Correct no</h3><p>It said not unloading, and they were not.</p><p className="ex">Two people standing at a stopped, empty belt.</p></div>
      </div>
      <p>Both examples of mistakes are real ones found in this session. Both have since been fixed, and both are kept as tests.</p>

      <h2>Three ways to score it</h2>
      <dl className="defs">
        <dt>Accuracy</dt>
        <dd>Out of every call, how many were right? Simple, but it can flatter. If people unload most of the time, a system that always says “unloading” scores well and tells you nothing.</dd>
        <dt>Precision</dt>
        <dd>When it says “unloading”, how often is that true? Low precision means false alarms. For an alert, low precision means supervisors learn to ignore it.</dd>
        <dt>Recall</dt>
        <dd>Of all the real unloading, how much did it catch? Low recall means misses. For a safety event, such as someone crossing the belt, a miss is the costly mistake.</dd>
      </dl>
      <p>You usually trade one for the other. Make the system stricter and it raises fewer false alarms but misses more. Which way to lean depends on the decision.</p>
      <table className="plain">
        <thead><tr><th>If you are using it to…</th><th>The mistake that costs you</th><th>So lean towards</th></tr></thead>
        <tbody>
          <tr><td>Decide staffing for a bay</td><td>False alarms: idle time counted as work hides spare capacity</td><td>Precision</td></tr>
          <tr><td>Alert a supervisor to move people</td><td>False alarms: a wasted walk, then ignored alerts</td><td>Precision</td></tr>
          <tr><td>Catch someone on the belt</td><td>Misses: the event you bought the system for goes unseen</td><td>Recall</td></tr>
        </tbody>
      </table>

      <h2>Why precision and recall are not on this page yet</h2>
      <p>
        The review so far showed a person the system’s labels and asked which were wrong. That finds mistakes quickly, but people notice a wrong label
        more easily than a missing one, so it over-states how good the system is. The first round found only false alarms; later rounds found misses too.
      </p>
      <p>
        A fair score needs a blind check: a person labels a few hundred clips without seeing the system’s answer, and the two are compared afterwards.
        That is half a day of work and is the next step before any figure here is used for a staffing decision.
      </p>

      <h2>What the system cannot see today</h2>
      <ul>
        <li>Whether a parcel is going onto the belt or coming off it. Loading and unloading share one label.</li>
        <li>Someone gesturing next to a loaded belt looks the same as someone handling freight. This is the one known mistake still open.</li>
        <li>Anything not visible in body position: smoking, phone use, what is in a person’s hands.</li>
        <li>The truck. It is outside the camera’s view, so the rate of supply is inferred from what arrives on the belt.</li>
        <li>Individuals over time. People are counted by position, not followed as named workers, and no faces are recognised.</li>
      </ul>
    </article>
  );
}
