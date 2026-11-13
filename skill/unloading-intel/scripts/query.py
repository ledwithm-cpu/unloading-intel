#!/usr/bin/env python3
"""Query the processed unloading session. Standard library only; reads data/unloading.db (never the video).

  query.py summary
  query.py underutilised [--top 5]
  query.py busiest [--window 60]
  query.py find [--present-min 3] [--unloading-max 1] [--waiting-min N] [--belt STATE] [--min-seconds 10]
  query.py people --from 9:30 --to 10:40
  query.py events [--type stopped_loaded]
  query.py opportunities
  query.py safety
  query.py schema
  query.py sql "SELECT ..."          (read-only)

Times are video time (m:ss) with the camera clock in brackets. Every answer should quote them.
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

CLOCK_START = 6 * 3600 + 4 * 60 + 57            # camera clock at video 0:00
BELT_LABEL = {"flowing": "moving freight", "running_empty": "running near-empty (under 20% covered)",
              "stopped_loaded": "stopped with freight on it", "stopped_empty": "stopped, near-empty (under 20% covered)"}


def find_db():
    if os.environ.get("UNLOADING_DB"):
        return os.environ["UNLOADING_DB"]
    for base in [Path.cwd(), *Path(__file__).resolve().parents]:
        if (base / "data" / "unloading.db").exists():
            return str(base / "data" / "unloading.db")
    sys.exit("Could not find data/unloading.db. Run from the repository root or set UNLOADING_DB.")


def ts(sec):
    sec = int(sec)
    c = CLOCK_START + sec
    return f"{sec // 60}:{sec % 60:02d} [{c // 3600:02d}:{c % 3600 // 60:02d}:{c % 60:02d}]"


def parse_t(s):
    if ":" in str(s):
        m, sec = str(s).split(":")
        return int(m) * 60 + int(sec)
    return int(float(s))


def out(obj):
    print(json.dumps(obj, indent=1, ensure_ascii=False))


def timeline(con):
    cols = ["t", "belt", "occupancy", "throughput", "present", "unloading", "other", "waiting", "by_zone"]
    return [dict(zip(cols, r)) for r in con.execute(
        "SELECT t_sec, belt_state, occupancy, throughput, n_present, n_belt_work, n_off_belt, n_waiting, by_zone FROM timeline ORDER BY t_sec")]


def avg(rows, key):
    return round(sum(r[key] for r in rows) / max(len(rows), 1), 2)


def describe(rows):
    return {"from": ts(rows[0]["t"]), "to": ts(rows[-1]["t"] + 1), "seconds": len(rows), "jump_to_sec": rows[0]["t"],
            "belt_covered": avg(rows, "occupancy"), "people_present": avg(rows, "present"), "unloading": avg(rows, "unloading"),
            "other_activity": avg(rows, "other"), "waiting": avg(rows, "waiting")}


def runs(tl, flags, min_seconds, gap=2):
    segs, start, miss = [], None, 0
    for i, f in enumerate(flags):
        if f:
            start = i if start is None else start
            miss = 0
        elif start is not None:
            miss += 1
            if miss > gap:
                segs.append((start, i - miss))
                start, miss = None, 0
    if start is not None:
        segs.append((start, len(flags) - 1 - miss))
    return [tl[a:b + 1] for a, b in segs if b - a + 1 >= min_seconds]


def cmd_summary(con, a):
    tl = timeline(con)
    n = len(tl)
    P = sum(r["present"] for r in tl)
    review = json.load(open(Path(find_db()).parent / "review_results.json"))
    out({
        "session": {"length": f"{n // 60} min {n % 60} s", "starts": ts(0), "camera": "one fixed camera over conveyor BN1"},
        "belt_time_share": {BELT_LABEL[s]: f"{sum(r['belt'] == s for r in tl) / n:.0%}" for s in BELT_LABEL},
        "people": {"average_in_view": round(P / n, 1), "unloading": f"{sum(r['unloading'] for r in tl) / P:.0%}",
                   "other_activity": f"{sum(r['other'] for r in tl) / P:.0%}", "waiting": f"{sum(r['waiting'] for r in tl) / P:.0%}"},
        "how_reliable": {"belt_state": "20 of 20 reviewed moments correct",
                         "people_labels": f"{review['worker_activity']['person_clips'] - review['worker_activity']['wrong']} of "
                                          f"{review['worker_activity']['person_clips']} correct in the first human review; rules changed since",
                         "caveat": "People figures are estimates. Precision and recall are not yet measured. 'Unloading' covers loading too."},
    })


def cmd_underutilised(con, a):
    tl = timeline(con)
    idle = runs(tl, [r["belt"] in ("running_empty", "stopped_empty") for r in tl], 10)
    idle.sort(key=len, reverse=True)
    w = 60
    best = min(range(len(tl) - w), key=lambda i: sum(r["occupancy"] for r in tl[i:i + w]))
    out({"definition": "Belt running near-empty or stopped near-empty for 10 s or more, longest first.",
         "total_seconds": sum(len(s) for s in idle), "periods": [dict(describe(s), belt=BELT_LABEL[max(set(r['belt'] for r in s), key=[r['belt'] for r in s].count)]) for s in idle[:a.top]],
         "emptiest_minute": describe(tl[best:best + w])})


def cmd_busiest(con, a):
    tl = timeline(con)
    w = a.window
    best = max(range(len(tl) - w), key=lambda i: sum(r["throughput"] for r in tl[i:i + w]))
    full = max(range(len(tl) - w), key=lambda i: sum(r["occupancy"] for r in tl[i:i + w]))
    mean = sum(r["throughput"] for r in tl) / len(tl)
    d = describe(tl[best:best + w])
    d["freight_flow_vs_session_average"] = f"{sum(r['throughput'] for r in tl[best:best + w]) / w / mean:.1f}x"
    out({"definition": f"The {w}-second window with the most freight flow (belt coverage x belt speed).",
         "busiest_by_flow": d, "fullest_belt": describe(tl[full:full + w])})


def cmd_find(con, a):
    tl = timeline(con)
    def ok(r):
        return ((a.present_min is None or r["present"] >= a.present_min) and (a.present_max is None or r["present"] <= a.present_max)
                and (a.unloading_max is None or r["unloading"] <= a.unloading_max) and (a.unloading_min is None or r["unloading"] >= a.unloading_min)
                and (a.waiting_min is None or r["waiting"] >= a.waiting_min) and (a.belt is None or r["belt"] == a.belt))
    segs = runs(tl, [ok(r) for r in tl], a.min_seconds)
    out({"filter": {k: v for k, v in vars(a).items() if v is not None and k not in ("cmd", "func")},
         "note": "People counts are per-second averages over five samples, so 'at most 1' means 1.0 or fewer on average.",
         "periods_found": len(segs), "total_seconds": sum(len(s) for s in segs), "share_of_session": f"{sum(len(s) for s in segs) / len(tl):.0%}",
         "periods": [describe(s) for s in sorted(segs, key=len, reverse=True)[:a.top]]})


def cmd_people(con, a):
    tl = timeline(con)
    rows = [r for r in tl if parse_t(a.start) <= r["t"] < parse_t(a.end)]
    if not rows:
        sys.exit("No data in that range. The session runs from 0:00 to 28:32.")
    zones = {}
    for r in rows:
        for z, v in json.loads(r["by_zone"]).items():
            d = zones.setdefault(z, {"present": 0, "belt_work": 0, "off_belt": 0, "waiting": 0})
            for k in d:
                d[k] += v.get(k, 0)
    n = len(rows)
    d = describe(rows)
    d["belt_states"] = {BELT_LABEL[s]: f"{sum(r['belt'] == s for r in rows) / n:.0%}" for s in BELT_LABEL if any(r["belt"] == s for r in rows)}
    d["by_working_area"] = {z: {"present": round(v["present"] / n, 1), "unloading": round(v["belt_work"] / n, 1),
                                "other_activity": round(v["off_belt"] / n, 1), "waiting": round(v["waiting"] / n, 1)} for z, v in zones.items()}
    out(d)


def cmd_events(con, a):
    q = "SELECT type,start_sec,duration_sec,people_present,people_belt_work,people_waiting,occupancy,details FROM events"
    rows = con.execute(q + (" WHERE type=?" if a.type else "") + " ORDER BY start_sec", (a.type,) if a.type else ()).fetchall()
    out({"types": dict(con.execute("SELECT type, COUNT(*) FROM events GROUP BY 1").fetchall()),
         "events": [{"type": r[0], "at": ts(r[1]), "jump_to_sec": r[1], "seconds": r[2], "people_present": r[3], "unloading": r[4],
                     "waiting": r[5], "belt_covered": r[6], "details": json.loads(r[7])} for r in rows[:a.top]]})


def cmd_opportunities(con, a):
    ins = json.load(open(Path(find_db()).parent / "insights.json"))
    out({"headline": ins["headline"]["sentence"],
         "opportunities": [{"finding": c["title"], "what_happened": c["what"], "why_it_matters": c["why"], "what_to_try": c["action"], "where_the_system_goes_next": c.get("next"),
                            "evidence": [{"at": ts(e["t_sec"]), "jump_to_sec": e["t_sec"], "what": e["label"]} for e in c["evidence"]]}
                           for c in ins["cards"]]})


def cmd_safety(con, a):
    cross = con.execute("SELECT start_sec,duration_sec,details FROM events WHERE type='belt_crossing' ORDER BY start_sec").fetchall()
    lean = con.execute("SELECT start_sec,duration_sec,details FROM events WHERE type='leaning_on_belt' ORDER BY duration_sec DESC").fetchall()
    out({"belt_crossings": {"count": len(cross), "caveat": "Candidates: some are a long reach across the belt, not a crossing.",
                            "events": [{"at": ts(s), "jump_to_sec": s, "seconds": d, "belt_moving": json.loads(x)["belt_moving"]} for s, d, x in cross]},
         "leaning_on_belt": {"count_5s_or_more": len(lean), "total_seconds": sum(d for _, d, _ in lean),
                             "seconds_while_belt_moving": sum(d for _, d, x in lean if json.loads(x)["belt_moving"]),
                             "longest": [{"at": ts(s), "jump_to_sec": s, "seconds": d, "belt_moving": json.loads(x)["belt_moving"]} for s, d, x in lean[:5]]},
         "not_detectable": "Smoking, phone use and footwear cannot be seen from body position. A reviewer reported a man smoking among the parcels at about 19:27."})


def cmd_schema(con, a):
    for name, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"):
        print(sql.strip(), f"\n-- rows: {con.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]}\n")


def cmd_sql(con, a):
    if not a.query.lstrip().lower().startswith(("select", "with")):
        sys.exit("Read-only: the query must start with SELECT or WITH.")
    cur = con.execute(a.query)
    cols = [c[0] for c in cur.description]
    out([dict(zip(cols, r)) for r in cur.fetchmany(a.limit)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("summary").set_defaults(func=cmd_summary)
    p = sub.add_parser("underutilised"); p.add_argument("--top", type=int, default=5); p.set_defaults(func=cmd_underutilised)
    p = sub.add_parser("busiest"); p.add_argument("--window", type=int, default=60); p.set_defaults(func=cmd_busiest)
    p = sub.add_parser("find")
    for flag in ("present-min", "present-max", "unloading-min", "unloading-max", "waiting-min"):
        p.add_argument(f"--{flag}", type=float)
    p.add_argument("--belt", choices=list(BELT_LABEL)); p.add_argument("--min-seconds", type=int, default=10)
    p.add_argument("--top", type=int, default=10); p.set_defaults(func=cmd_find)
    p = sub.add_parser("people"); p.add_argument("--from", dest="start", required=True); p.add_argument("--to", dest="end", required=True); p.set_defaults(func=cmd_people)
    p = sub.add_parser("events"); p.add_argument("--type"); p.add_argument("--top", type=int, default=100); p.set_defaults(func=cmd_events)
    sub.add_parser("opportunities").set_defaults(func=cmd_opportunities)
    sub.add_parser("safety").set_defaults(func=cmd_safety)
    sub.add_parser("schema").set_defaults(func=cmd_schema)
    p = sub.add_parser("sql"); p.add_argument("query"); p.add_argument("--limit", type=int, default=200); p.set_defaults(func=cmd_sql)
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{find_db()}?mode=ro", uri=True)
    a.func(con, a)


if __name__ == "__main__":
    main()
