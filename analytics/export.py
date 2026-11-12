"""Export everything the React app needs as static JSON. No server required.

Usage: python -m analytics.export            (writes app/public/data/session.json and frames.json)
"""
import argparse
import json
import sqlite3
from collections import defaultdict

STATES = ["belt_work", "off_belt", "waiting"]
DETAILS = [None, "leaning", "crossing"]
ZONES = ["dock_door", "pile_side", "floor_side", "far_end", "away"]
BELT_STATES = ["flowing", "running_empty", "stopped_loaded", "stopped_empty"]
BODY = list(range(5, 17))        # shoulders to ankles: enough to draw a skeleton


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/unloading.db")
    ap.add_argument("--out", default="app/public/data")
    a = ap.parse_args()
    con = sqlite3.connect(a.db)
    meta = dict(con.execute("SELECT key, value FROM video_meta"))
    stride = int(meta["sample_stride"])
    src_fps = float(meta["src_fps"])

    tl = con.execute("SELECT t_sec, belt_state, occupancy, throughput, n_present, n_belt_work, n_off_belt, n_waiting "
                     "FROM timeline ORDER BY t_sec").fetchall()
    session = {
        "video": {"src": "video/unloading.mp4", "width": int(meta["width"]), "height": int(meta["height"]),
                  "duration": len(tl), "clock_start": "06:04:57", "date": "Saturday 10 October 2026",
                  "sample_fps": src_fps / stride},
        "legend": {"states": STATES, "details": DETAILS, "zones": ZONES, "belt_states": BELT_STATES},
        "zones": json.load(open("config/zones.json")),
        "timeline": {
            "belt_state": [BELT_STATES.index(r[1]) for r in tl],
            "occupancy": [round(r[2], 2) for r in tl],
            "throughput": [round(r[3] * 1000, 1) for r in tl],
            "present": [r[4] for r in tl], "unloading": [r[5] for r in tl],
            "other": [r[6] for r in tl], "waiting": [r[7] for r in tl],
        },
        "events": [dict(zip(("id", "type", "start", "end", "duration", "present", "unloading", "waiting", "occupancy", "details"),
                            (*r[:9], json.loads(r[9]))))
                   for r in con.execute("SELECT id,type,start_sec,end_sec,duration_sec,people_present,people_belt_work,"
                                        "people_waiting,occupancy,details FROM events ORDER BY start_sec")],
        "insights": json.load(open("data/insights.json")),
        "review": json.load(open("data/review_results.json")),
    }
    from . import evaluate
    ok, total = evaluate.score(con, verbose=False)
    session["review"]["corrections"] = {"satisfied": ok, "total": total}
    for k in ("events",):
        session["insights"].pop(k, None)
    json.dump(session, open(f"{a.out}/session.json", "w"), separators=(",", ":"))

    frames = defaultdict(list)
    q = ("SELECT d.frame_idx, d.x1, d.y1, d.x2, d.y2, d.keypoints, a.state, a.detail, a.zone, d.track_id "
         "FROM detections d JOIN person_activity a ON a.frame_idx=d.frame_idx AND a.track_id=d.track_id")
    for f, x1, y1, x2, y2, kp, state, detail, zone, tid in con.execute(q):
        kp = json.loads(kp)
        pts = []
        for j in BODY:
            pts += [round(kp[j][0]), round(kp[j][1])] if kp[j][2] > 0.3 else [-1, -1]
        frames[f // stride].append([round(x1), round(y1), round(x2), round(y2), STATES.index(state),
                                    DETAILS.index(detail), ZONES.index(zone), tid, *pts])
    n = max(frames) + 1
    json.dump({"stride": stride, "frames": [frames.get(i, []) for i in range(n)]},
              open(f"{a.out}/frames.json", "w"), separators=(",", ":"))
    import os
    import subprocess
    blurred = "app/public/video/unloading.mp4"      # take the zone-editor still from the face-blurred copy
    if os.path.exists(blurred):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1695", "-i", blurred, "-frames:v", "1", "-vf", "scale=1280:720",
                        "-q:v", "4", f"{a.out}/frame.jpg"], check=False)
    print("session.json and frames.json written:", len(tl), "seconds,", n, "overlay frames")


if __name__ == "__main__":
    main()
