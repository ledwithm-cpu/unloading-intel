"""Stage 2: measure conveyor state. Writes belt_samples to SQLite.

Method (no trained model needed):
  1. Rectify the belt polygon into a flat strip (infeed/dock door at x=0, discharge/far end at x=W).
  2. Learn what the empty belt looks like per pixel: the most common brightness over the whole video.
  3. Freight = pixels that differ from the empty belt in colour, or carry texture the plain belt lacks.
  4. People leaning over the belt are masked out using the person detections from stage 1.
  5. Belt movement = horizontal shift of the strip over 0.1 s (phase correlation) when freight is on it;
     when bare, a moving belt is motion-blurred smooth and a stopped belt shows its scuff texture.

Usage: python -m pipeline.belt --video data/source.mp4 --db data/unloading.db
"""
import argparse
import bisect
import json

import cv2
import numpy as np

from .db import connect

W, H = 400, 40          # rectified strip size
N_BINS = 40             # position bins along the belt
PAIR_GAP = 2            # frames between the two images used for the speed estimate
MARGIN_TOP = 8          # strip rows ignored on the far side (floor piles overhang the belt lip)
MARGIN_BOTTOM = 3       # strip rows ignored on the rail side
MARGIN_INFEED = 20      # strip columns ignored at the dock door (doorway shadow, half-visible worker)


def homography(poly):
    far_lo, far_up, near_up, near_lo = [np.float32(p) for p in poly]
    src = np.float32([near_up, far_up, far_lo, near_lo])
    dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    return cv2.getPerspectiveTransform(src, dst)


def empty_belt_reference(strips_lab):
    """Per-pixel mode of lightness -> mean Lab of the samples in that mode."""
    L = strips_lab[..., 0]
    q = (L // 8).astype(np.int16)                       # 32 brightness bins
    counts = np.stack([(q == b).sum(0) for b in range(32)])
    mode = counts.argmax(0)
    sel = (q == mode[None])[..., None]
    ref = (strips_lab * sel).sum(0) / np.maximum(sel.sum(0), 1)
    return ref.astype(np.float32)


def freight_mask(lab, ref, color_thr, tex_thr):
    d = lab.astype(np.float32) - ref
    d[..., 0] *= 0.7                                     # be a little tolerant to lighting
    delta = np.sqrt((d ** 2).sum(-1))
    tex = np.abs(cv2.Laplacian(lab[..., 0], cv2.CV_32F, ksize=3))
    tex = cv2.blur(tex, (7, 7))
    m = ((delta > color_thr) | (tex > tex_thr)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 11), np.uint8))
    return m, tex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--zones", default="config/zones.json")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--color-thr", type=float, default=14.0)
    ap.add_argument("--tex-thr", type=float, default=40.0,
                    help="high on purpose: a stopped belt shows scuff texture that a moving (blurred) belt hides")
    ap.add_argument("--dump", default=None, help="optional .npz path for debugging/visual checks")
    args = ap.parse_args()

    poly = json.load(open(args.zones))["zones"]["belt"]["polygon"]
    M = homography(poly)
    con = connect(args.db)

    # person boxes per sampled frame, for masking
    det_frames, boxes = [], {}
    for f, x1, y1, x2, y2 in con.execute("SELECT frame_idx,x1,y1,x2,y2 FROM detections ORDER BY frame_idx"):
        boxes.setdefault(f, []).append((x1, y1, x2, y2))
    det_frames = sorted(boxes)

    cap = cv2.VideoCapture(args.video)
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    fw, fh = int(cap.get(3)), int(cap.get(4))
    stride = max(1, round(src_fps / args.fps))

    times, strips, strips2, pmasks = [], [], [], []
    idx = -1
    while cap.grab():
        idx += 1
        ph = idx % stride
        if ph not in (0, PAIR_GAP):
            continue
        ok, frame = cap.retrieve()
        if not ok:
            break
        strip = cv2.warpPerspective(frame, M, (W, H), flags=cv2.INTER_AREA)
        if ph == 0:
            times.append(idx / src_fps)
            strips.append(cv2.cvtColor(strip, cv2.COLOR_BGR2LAB))
            pm = np.zeros((fh, fw), np.uint8)
            if det_frames:
                j = bisect.bisect_left(det_frames, idx)
                near = min([det_frames[k] for k in (j - 1, j) if 0 <= k < len(det_frames)],
                           key=lambda f: abs(f - idx))
                if abs(near - idx) <= stride:
                    for x1, y1, x2, y2 in boxes[near]:
                        cv2.rectangle(pm, (int(x1), int(y1)), (int(x2), int(y2)), 1, -1)
            pmasks.append(cv2.warpPerspective(pm, M, (W, H), flags=cv2.INTER_NEAREST))
        else:
            strips2.append(cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY))
    n = min(len(strips), len(strips2))
    times, strips, strips2, pmasks = times[:n], np.array(strips[:n]), np.array(strips2[:n]), np.array(pmasks[:n])

    ref = empty_belt_reference(strips)
    dt = PAIR_GAP / src_fps
    win = cv2.createHanningWindow((W, H), cv2.CV_32F)
    rows, masks = [], []
    for t, lab, g2, pm in zip(times, strips, strips2, pmasks):
        m, tex = freight_mask(lab, ref, args.color_thr, args.tex_thr)
        valid = pm == 0
        valid[:MARGIN_TOP] = False
        valid[-MARGIN_BOTTOM:] = False
        valid[:, :MARGIN_INFEED] = False
        m = m * valid
        masks.append(m)
        occ = float(m.sum() / max(valid.sum(), 1))
        bare = valid & (m == 0)
        surface_tex = float(np.median(tex[bare])) if bare.sum() > 200 else None
        col_valid = valid.reshape(H, N_BINS, W // N_BINS).sum((0, 2))
        col_occ = m.reshape(H, N_BINS, W // N_BINS).sum((0, 2)) / np.maximum(col_valid, 1)
        speed = None
        if occ > 0.03:
            g1 = lab[..., 0].astype(np.float32)
            (dx, _), resp = cv2.phaseCorrelate(g1, g2.astype(np.float32), win)
            if resp > 0.05:
                speed = round(float(dx) / W / dt, 4)     # belt-lengths per second, + = toward far end
        rows.append((round(t, 3), round(occ, 4), speed, surface_tex, json.dumps([round(float(v), 3) for v in col_occ])))

    con.execute("DROP TABLE belt_samples")
    con.close()
    con = connect(args.db)
    con.executemany("INSERT INTO belt_samples VALUES (?,?,?,?,?)", rows)
    con.executemany("INSERT OR REPLACE INTO video_meta VALUES (?,?)",
                    [("belt_sample_fps", str(src_fps / stride)), ("belt_bins", str(N_BINS)),
                     ("belt_polygon", json.dumps(poly))])
    con.commit()
    if args.dump:
        np.savez_compressed(args.dump, times=np.array(times), strips=strips, masks=np.array(masks), ref=ref)
    print("belt samples:", len(rows))


if __name__ == "__main__":
    main()
