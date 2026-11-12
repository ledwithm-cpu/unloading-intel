"""Make a human review reel: N short clips with the system's labels drawn on, so a person can mark them right or wrong.

Usage: python -m analytics.review --db data/unloading.db --video data/source.mp4 --out data/review_reel.mp4
"""
import argparse
import json
import random
import sqlite3
import subprocess

import cv2

from . import annotate

NICE = {"flowing": "FLOWING", "running_empty": "RUNNING NEAR-EMPTY", "stopped_loaded": "STOPPED WITH FREIGHT",
        "stopped_empty": "STOPPED AND EMPTY"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/unloading.db")
    ap.add_argument("--video", default="data/source.mp4")
    ap.add_argument("--out", default="data/review_reel.mp4")
    ap.add_argument("--per-state", type=int, default=5)
    ap.add_argument("--clip-seconds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    con = sqlite3.connect(a.db)
    tl = dict(con.execute("SELECT t_sec, belt_state FROM timeline"))
    rng = random.Random(a.seed)
    moments = []
    for state in NICE:
        stable = [s for s in tl if all(tl.get(s + d) == state for d in range(-1, a.clip_seconds + 1))]
        picked = []
        for s in rng.sample(stable, len(stable)):
            if all(abs(s - p) > 20 for p in picked):
                picked.append(s)
            if len(picked) == a.per_state:
                break
        moments += [(s, state) for s in picked]
    moments.sort()
    zones = json.load(open("config/zones.json"))["zones"]
    cap = cv2.VideoCapture(a.video)
    tmp = "/tmp/review_raw.avi"
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"MJPG"), 5, (1280, 760))
    sheet = []
    for n, (s, state) in enumerate(moments, 1):
        sheet.append({"moment": n, "video_time": f"{s // 60}:{s % 60:02d}", "t_sec": s, "belt_state": state})
        for i in range(a.clip_seconds * 5):
            im = annotate.draw(con, cap, s + i / 5, {"belt": zones["belt"]})
            canvas = cv2.copyMakeBorder(im, 40, 0, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
            cv2.putText(canvas, f"Moment {n}/{len(moments)}   video {s // 60}:{s % 60:02d}   Belt: {NICE[state]}",
                        (12, 27), 0, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(canvas, "green = working the belt   orange = active off belt   red = waiting", (720, 27), 0, 0.55,
                        (200, 200, 200), 1, cv2.LINE_AA)
            vw.write(canvas)
    vw.release()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", a.out], check=True)
    json.dump(sheet, open(a.out.replace(".mp4", ".json"), "w"), indent=1)
    for m in sheet:
        print(m)


if __name__ == "__main__":
    main()
