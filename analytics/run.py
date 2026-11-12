"""Rebuild all analytics from stored detections. Takes seconds; never touches the video.

Usage: python -m analytics.run --db data/unloading.db
"""
import argparse
import json
import sqlite3

from . import activity, events, insights, safety, timeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/unloading.db")
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    n, ghosts = activity.run(con)
    print(f"activity: {n} person-frames ({len(ghosts)} false tracks dropped)")
    timeline.run(con)                      # first pass, so safety can read belt state
    events.run(con)
    print(f"safety:   {safety.run(con)} events (crossings relabelled)")
    print(f"timeline: {timeline.run(con)} seconds")       # rebuilt with crossings no longer counted as unloading
    n_ev = events.run(con)
    print(f"events:   {n_ev + safety.run(con)}")
    out = insights.build(con)
    json.dump(out, open("data/insights.json", "w"), indent=1)
    print("insights:", out["headline"]["sentence"])


if __name__ == "__main__":
    main()
