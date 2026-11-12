"""Privacy stage: write a copy of the video with every detected person's face blurred.

Head positions come from the pose keypoints already stored in SQLite, so no extra model is needed.
People the detector missed are not blurred; see the README limitations.

Usage: python -m pipeline.blur --video data/source.mp4 --db data/unloading.db --out app/public/video/unloading.mp4
"""
import argparse
import json
import sqlite3
import subprocess
from collections import defaultdict

import cv2
import numpy as np

HEAD = [0, 1, 2, 3, 4]          # nose, eyes, ears


def head_circle(box, kp):
    x1, y1, x2, y2 = box
    h = y2 - y1
    pts = np.array([[kp[j][0], kp[j][1]] for j in HEAD if kp[j][2] > 0.3])
    if len(pts) >= 2:
        c = pts.mean(0)
        r = max(np.linalg.norm(pts - c, axis=1).max() * 1.9, 0.10 * h)
    elif len(pts) == 1:
        c, r = pts[0], 0.11 * h
    else:
        c, r = np.array([(x1 + x2) / 2, y1 + 0.10 * h]), 0.12 * h     # no face points: assume top of the box
    return float(c[0]), float(c[1]), float(max(r, 14))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="data/source.mp4")
    ap.add_argument("--db", default="data/unloading.db")
    ap.add_argument("--out", default="app/public/video/unloading.mp4")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--crf", type=int, default=30)
    a = ap.parse_args()

    con = sqlite3.connect(a.db)
    stride = int(con.execute("SELECT value FROM video_meta WHERE key='sample_stride'").fetchone()[0])
    heads = defaultdict(list)
    for f, x1, y1, x2, y2, kp in con.execute("SELECT frame_idx, x1, y1, x2, y2, keypoints FROM detections"):
        heads[f].append(head_circle((x1, y1, x2, y2), json.loads(kp)))

    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(3)), int(cap.get(4))
    out_h = int(round(a.width * h / w / 2) * 2)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
         "-an", "-vf", f"scale={a.width}:{out_h}", "-c:v", "libx264", "-preset", "fast", "-crf", str(a.crf), "-g", "40",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    idx = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        s0 = idx // stride * stride
        # use the sampled positions either side of this frame so a moving head stays covered
        for cx, cy, r in heads.get(s0, []) + heads.get(s0 + stride, []):
            r = int(r * 1.25)
            xa, ya, xb, yb = max(0, int(cx - r)), max(0, int(cy - r)), min(w, int(cx + r)), min(h, int(cy + r))
            if xb - xa < 4 or yb - ya < 4:
                continue
            roi = frame[ya:yb, xa:xb]
            small = cv2.resize(roi, (5, 5), interpolation=cv2.INTER_AREA)
            blurred = cv2.GaussianBlur(cv2.resize(small, (xb - xa, yb - ya), interpolation=cv2.INTER_LINEAR), (0, 0), 3)
            mask = np.zeros(roi.shape[:2], np.uint8)
            cv2.ellipse(mask, ((xb - xa) // 2, (yb - ya) // 2), ((xb - xa) // 2, (yb - ya) // 2), 0, 0, 360, 255, -1)
            roi[mask > 0] = blurred[mask > 0]
        enc.stdin.write(frame.tobytes())
        if idx % 4000 == 0:
            print(idx, flush=True)
    enc.stdin.close()
    enc.wait()
    print("done", idx + 1, "frames ->", a.out)


if __name__ == "__main__":
    main()
