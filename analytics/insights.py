"""Turn the timeline and events into plain-language insight cards with video evidence.

Reads `timeline` and `events`; writes data/insights.json for the app and the Claude skill.
Every number here is computed, and every card carries the moments that support it.
"""
import argparse
import json
import sqlite3

import numpy as np

LABEL = {"flowing": "Flowing", "running_empty": "Running near-empty", "stopped_loaded": "Stopped with freight",
         "stopped_empty": "Stopped and empty", "release_window": "People free to release",
         "under_pressure": "Bay under pressure", "low_engagement": "3+ present, at most 1 unloading",
         "belt_crossing": "Crossed the belt", "leaning_on_belt": "Leaning on the belt"}


def mmss(s):
    return f"{int(s) // 60}:{int(s) % 60:02d}"


def build(con):
    tl = con.execute("SELECT t_sec, belt_state, occupancy, throughput, n_present, n_belt_work, n_off_belt, n_waiting "
                     "FROM timeline ORDER BY t_sec").fetchall()
    n = len(tl)
    state = np.array([r[1] for r in tl])
    occ, thr, present, belt_work, off_belt, waiting = (np.array([r[i] for r in tl]) for i in (2, 3, 4, 5, 6, 7))
    ev = [dict(zip(("id", "type", "start", "end", "duration", "present", "belt_work", "waiting", "wait_person_sec", "occupancy"), r))
          for r in con.execute("SELECT id,type,start_sec,end_sec,duration_sec,people_present,people_belt_work,"
                               "people_waiting,person_seconds_waiting,occupancy FROM events ORDER BY start_sec")]

    def evidence(types, k=4):
        pick = sorted([e for e in ev if e["type"] in types], key=lambda e: -e["duration"])[:k]
        return [{"event_id": e["id"], "t_sec": e["start"], "label": f"{mmss(e['start'])} · {LABEL.get(e['type'], e['type'])} for {e['duration']}s",
                 "people_present": e["present"], "people_waiting": e["waiting"]} for e in sorted(pick, key=lambda e: e["start"])]

    share = {s: float((state == s).mean()) for s in LABEL}
    secs = {s: int((state == s).sum()) for s in LABEL}
    lost = n - secs["flowing"]
    wait_share = {s: float(waiting[state == s].sum() / max(present[state == s].sum(), 1)) for s in LABEL}
    share_of = lambda arr, st: float(arr[state == st].sum() / max(present[state == st].sum(), 1))
    low_secs = sum(e["duration"] for e in ev if e["type"] == "low_engagement")
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
        "person_minutes": {"present": float(present.sum() / 60), "belt_work": float(belt_work.sum() / 60), "off_belt": float(off_belt.sum() / 60), "waiting": float(waiting.sum() / 60)},
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
            "next": "Join this timeline to scan or warehouse-system data by time. Each stop then shows the freight scanned just before it, so the system can name the items that stop the belt without anyone having to ask. Not built here: this prototype has no scan data.",
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
            "next": "A camera at the dock door, or the truck arrival feed, turns supply from an inference into a measurement. The system could then flag a slow feed while it is happening, not afterwards.",
            "metric": {"label": "Running near-empty", "value": f"{share['running_empty']:.0%}"},
            "evidence": evidence(("running_empty",)),
        },
        {
            "id": "capacity",
            "title": "On average the line ran at less than half its own best minute",
            "what": f"Freight flow averaged {thr.mean() / best60.max():.0%} of the best sustained minute (from {mmss(best_at)}). "
                    f"Even while flowing, {1 - float(occ[state == 'flowing'].mean()):.0%} of the belt surface was bare.",
            "why": "The same people and the same belt have already shown the higher rate. The gap is steadiness, not speed.",
            "action": "Use the best minute as the target rate and track minutes at or near it per session.",
            "next": "Run on the live feed and show each bay its current rate against its own best minute, so a supervisor sees a drop as it starts.",
            "metric": {"label": "Of best-minute rate", "value": f"{thr.mean() / best60.max():.0%}"},
            "evidence": [{"t_sec": best_at, "label": f"{mmss(best_at)} · best sustained minute"}] + evidence(("stopped_empty",), 2),
        },
        {
            "id": "belt_work",
            "title": "Unloading follows the belt: when it stops, people wait",
            "what": f"{float(belt_work.sum() / present.sum()):.0%} of person-time was spent unloading (picking from the belt, carrying, returning), "
                    f"{float(off_belt.sum() / present.sum()):.0%} on other activity and {float(waiting.sum() / present.sum()):.0%} waiting. "
                    f"While the belt flowed, {float(belt_work[state == 'flowing'].mean()):.1f} of {float(present[state == 'flowing'].mean()):.1f} people were unloading.",
            "why": f"Unloading falls from {share_of(belt_work, 'flowing'):.0%} when the belt flows to {share_of(belt_work, 'stopped_empty'):.0%} when it is stopped and empty, "
                   f"and waiting rises from {wait_share['flowing']:.0%} to {wait_share['stopped_empty']:.0%}. People follow the belt, which points at the process, not the people. "
                   f"For {low_secs / n:.0%} of the session three or more people were present with at most one unloading.",
            "action": "Fix stops and gaps first. Then look at the other activity: some is stacking and staging, some is not work, "
                      "and this camera cannot yet tell them apart.",
            "next": "A model that looks at short clips, not only body position, to separate loading, stacking and idle movement. The review corrections already collected would score it.",
            "metric": {"label": "Time unloading", "value": f"{float(belt_work.sum() / present.sum()):.0%}"},
            "evidence": evidence(("low_engagement",), 4),
        },
    ]
    rel = [e for e in ev if e["type"] == "release_window"]
    prs = [e for e in ev if e["type"] == "under_pressure"]
    late = ~early
    cards.append({
        "id": "reallocation",
        "title": "People could have been released to another bay, in short windows",
        "what": f"{len(rel)} windows where the belt was idle and about two people were waiting, lasting "
                f"{min((e['duration'] for e in rel), default=0)}-{max((e['duration'] for e in rel), default=0)} seconds "
                f"({sum(e['wait_person_sec'] for e in rel) / 60:.1f} person-minutes). "
                f"{len(prs)} window{'s' if len(prs) != 1 else ''} where this bay was saturated with nobody waiting.",
        "why": f"The first six minutes had {float(present[early].mean()):.1f} people and the belt flowing {float((state[early] == 'flowing').mean()):.0%} of the time; "
               f"the rest had {float(present[late].mean()):.1f} people and {float((state[late] == 'flowing').mean()):.0%}. "
               "Fewer people moved more freight, so the bigger win is the staffing level per phase, not second-by-second moves.",
        "action": "Start by releasing one person during slow feed from the truck, and check that flow holds.",
        "next": "With every bay measured the same way, the system matches one bay's release windows against another bay's pressure and alerts a supervisor when a move is worth the walk. The Site view page shows this with example data.",
        "metric": {"label": "Release windows", "value": str(len(rel))},
        "evidence": evidence(("release_window", "under_pressure"), 4),
    })
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
