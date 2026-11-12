"""Stage 1: detect, track and pose-estimate people. Writes to SQLite.

Usage: python -m pipeline.detect --video data/source.mp4 --db data/unloading.db
"""
import argparse
import json
import time

import cv2
from ultralytics import YOLO

from .db import connect

TRACKER_YAML = """\
tracker_type: bytetrack
track_high_thresh: 0.35
track_low_thresh: 0.1
new_track_thresh: 0.45
track_buffer: 60
match_thresh: 0.85
fuse_score: True
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--model", default="models/yolo11s-pose_openvino_model")
    ap.add_argument("--fps", type=float, default=5.0, help="sampling rate")
    ap.add_argument("--imgsz", type=int, nargs=2, default=[544, 960])
    ap.add_argument("--conf", type=float, default=0.25)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(3)), int(cap.get(4))
    stride = max(1, round(src_fps / args.fps))

    con = connect(args.db)
    con.execute("DELETE FROM detections")
    con.execute("DELETE FROM frames")
    meta = {
        "source": args.video, "src_fps": src_fps, "n_frames": n_frames,
        "width": w, "height": h, "sample_stride": stride,
        "sample_fps": src_fps / stride, "model": args.model,
        "tracker": "bytetrack",
    }
    con.executemany("INSERT OR REPLACE INTO video_meta VALUES (?, ?)",
                    [(k, str(v)) for k, v in meta.items()])

    with open("/tmp/tracker.yaml", "w") as f:
        f.write(TRACKER_YAML)
    model = YOLO(args.model, task="pose")

    t0 = time.time()
    idx = -1
    while True:
        if not cap.grab():
            break
        idx += 1
        if idx % stride:
            continue
        ok, frame = cap.retrieve()
        if not ok:
            break
        r = model.track(frame, persist=True, tracker="/tmp/tracker.yaml",
                        imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
        t_sec = idx / src_fps
        rows = []
        if r.boxes is not None and len(r.boxes):
            ids = r.boxes.id.int().tolist() if r.boxes.id is not None else [None] * len(r.boxes)
            kps = r.keypoints.data.tolist()
            for box, c, tid, kp in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), ids, kps):
                kp = [[round(x, 1), round(y, 1), round(s, 2)] for x, y, s in kp]
                rows.append((idx, t_sec, tid, *[round(v, 1) for v in box], round(c, 3), json.dumps(kp)))
        con.executemany("INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?)", rows)
        con.execute("INSERT INTO frames VALUES (?,?,?)", (idx, t_sec, len(rows)))
        if (idx // stride) % 250 == 0:
            con.commit()
            el = time.time() - t0
            print(f"{idx}/{n_frames} frames  {t_sec:6.0f}s video  {el:5.0f}s elapsed", flush=True)
    con.commit()
    con.close()
    print("done", time.time() - t0, flush=True)


if __name__ == "__main__":
    main()
