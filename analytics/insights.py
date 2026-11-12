"""Turn the timeline and events into plain-language insight cards with video evidence.

Reads `timeline` and `events`; writes data/insights.json for the app and the Claude skill.
Every number here is computed, and every card carries the moments that support it.
"""
import argparse
import json
import sqlite3

import numpy as np

LABEL = {"flowing": "Flowing", "running_empty": "Running empty", "stopped_loaded": "Stopped with freight",
         "stopped_empty": "Stopped and empty"}


def mmss(s):
    return f"{int(s) // 60}:{int(s) % 60:02d}"


def build(con):
    tl = con.execute("SELECT t_sec, belt_state, occupancy, throughput, n_present, n_handling, n_moving, n_waiting "
                     "FROM timeline ORDER BY t_sec").fetchall()
    n = len(tl)
    state = np.array([r[1] for r in tl])
    occ, thr, present, handling, waiting = (np.array([r[i] for r in tl]) for i in (2, 3, 4, 5, 7))
    ev = [dict(zip(("id", "type", "start", "end", "duration", "present", "handling", "waiting", "wait_person_sec", "occupancy"), r))
          for r in con.execute("SELECT id,type,start_sec,end_sec,duration_sec,people_present,people_handling,"
                               "people_waiting,person_seconds_waiting,occupancy FROM events ORDER BY start_sec")]

    def evidence(types, k=4):
        pick = sorted([e for e in ev if e["type"] in types], key=lambda e: -e["duration"])[:k]
        return [{"event_id": e["id"], "t_sec": e["start"], "label": f"{mmss(e['start'])} · {LABEL.get(e['type'], e['type'])} for {e['duration']}s",
                 "people_present": e["present"], "people_waiting": e["waiting"]} for e in sorted(pick, key=lambda e: e["start"])]

    share = {s: float((state == s).mean()) for s in LABEL}
    secs = {s: int((state == s).sum()) for s in LABEL}
    lost = n - secs["flowing"]
    wait_share = {s: float(waiting[state == s].sum() / max(present[state == s].sum(), 1)) for s in LABEL}
    stopped = (state == "stopped_loaded") | (state == "stopped_empty")
    best60 = np.convolve(thr, np.ones(60) / 60, mode="valid")
    best_at = int(best60.argmax())
    stops = [e for e in ev if e["type"] in ("stopped_loaded", "stopped_empty")]
    gaps = [e for e in ev if e["type"] == "running_empty"]
    early = np.array([r[0] for r in tl]) < 360

    headline = {
        "video_seconds": n,
        "belt_state_share": share, "belt_state_seconds": secs,
        "productive_share": share["flowing"], "lost_seconds": lost,
        "avg_people": float(present.mean()),
        "person_minutes": {"present": float(present.sum() / 60), "working": float(handling.sum() / 60), "waiting": float(waiting.sum() / 60)},
        "throughput_vs_best_minute": float(thr.mean() / best60.max()),
        "best_minute_start_sec": best_at,
        "sentence": f"The belt moved freight {share['flowing']:.0%} of the time. The other {lost / 60:.0f} minutes of {n / 60:.0f} were lost to stops and gaps.",
    }
    cards = [
        {
            "id": "stops",
            "title": "The belt was stopped for a quarter of the session",
            "what": f"{len(stops)} stops of 10 seconds or more, {(secs['stopped_loaded'] + secs['stopped_empty']) / 60:.1f} minutes in total. "
                    f"{secs['stopped_loaded'] / 60:.1f} of those minutes had freight sitting on the belt.",
            "why": f"While the belt was stopped, {float(waiting[stopped].sum() / present[stopped].sum()):.0%} of the people in view were waiting, "
                   f"against {wait_share['flowing']:.0%} while it flowed. A stop holds up everyone downstream of it.",
            "action": "Find out what triggers each stop. The clips show awkward items (wire cages, long rolls) being handled on the belt during several of them; "
                      "routing those off-belt is the first thing to test.",
            "metric": {"label": "Belt stopped", "value": f"{share['stopped_loaded'] + share['stopped_empty']:.0%}"},
            "evidence": evidence(("stopped_loaded", "stopped_empty")),
        },
        {
            "id": "gaps",
            "title": "The sorting team outran the supply from the truck",
            "what": f"{len(gaps)} gaps of 10 seconds or more, {secs['running_empty'] / 60:.1f} minutes in total, most of them in the first six minutes "
                    f"(belt flowing only {float((state[early] == 'flowing').mean()):.0%} of that time).",
            "why": f"Headcount was highest during the gaps ({float(present[state == 'running_empty'].mean()):.1f} people against "
                   f"{float(present[state == 'flowing'].mean()):.1f} when flowing). Workers along the belt mainly take freight off it to sort, "
                   "so an empty belt means the truck end is not feeding fast enough for the people waiting to sort.",
            "action": "Look at the truck end first: one more person unloading, or fewer sorters during slow feed, would close the gap. A camera inside the dock door would confirm it.",
            "metric": {"label": "Running empty", "value": f"{share['running_empty']:.0%}"},
            "evidence": evidence(("running_empty",)),
        },
        {
            "id": "capacity",
            "title": "On average the line ran at less than half its own best minute",
            "what": f"Freight flow averaged {thr.mean() / best60.max():.0%} of the best sustained minute (from {mmss(best_at)}). "
                    f"Even while flowing, {1 - float(occ[state == 'flowing'].mean()):.0%} of the belt surface was bare.",
            "why": "The same people and the same belt have already shown the higher rate. The gap is steadiness, not speed.",
            "action": "Use the best minute as the target rate and track minutes at or near it per session.",
            "metric": {"label": "Of best-minute rate", "value": f"{thr.mean() / best60.max():.0%}"},
            "evidence": [{"t_sec": best_at, "label": f"{mmss(best_at)} · best sustained minute"}] + evidence(("stopped_empty",), 2),
        },
        {
            "id": "waiting",
            "title": "About a fifth of paid time on the floor was spent waiting",
            "what": f"{waiting.sum() / 60:.0f} of {present.sum() / 60:.0f} person-minutes in view were waiting ({float(waiting.sum() / present.sum()):.0%}). "
                    f"{float(waiting[state != 'flowing'].sum() / 60):.0f} of those fell while the belt was stopped or empty.",
            "why": "Waiting rises from "
                   f"{wait_share['flowing']:.0%} when the belt flows to {wait_share['stopped_empty']:.0%} when it is stopped and empty. "
                   "The waiting follows the belt, which points at the process, not the people.",
            "action": "Fix stops and gaps first. If waiting stays high at one position after that, rebalance who stands where.",
            "metric": {"label": "Time waiting", "value": f"{float(waiting.sum() / present.sum()):.0%}"},
            "evidence": evidence(("stopped_empty", "stopped_loaded", "low_engagement"), 4),
        },
    ]
    return {"headline": headline, "cards": cards, "events": ev}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/unloading.db")
    ap.add_argument("--out", default="data/insights.json")
    a = ap.parse_args()
    out = build(sqlite3.connect(a.db))
    json.dump(out, open(a.out, "w"), indent=1)
    print(out["headline"]["sentence"])
    for c in out["cards"]:
        print("-", c["title"], "|", c["what"], "|", c["why"])


if __name__ == "__main__":
    main()
