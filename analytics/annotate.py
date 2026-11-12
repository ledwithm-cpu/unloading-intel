"""Draw zones, people and their activity state on a video frame (for checks, review sheets and the app overlay export)."""
import json

import cv2
import numpy as np

COL = {"belt_work": (80, 200, 60), "off_belt": (40, 160, 240), "waiting": (60, 60, 230)}
SKELETON = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)]


def frame_at(cap, t_sec):
    cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000)
    ok, f = cap.read()
    return f


def draw(con, cap, t_sec, zones=None, label=True):
    fidx = con.execute("SELECT frame_idx FROM frames ORDER BY ABS(t_sec - ?) LIMIT 1", (t_sec,)).fetchone()[0]
    fps = float(con.execute("SELECT value FROM video_meta WHERE key='src_fps'").fetchone()[0])
    im = frame_at(cap, fidx / fps)
    if zones:
        for name, z in zones.items():
            cv2.polylines(im, [np.array(z["polygon"], np.int32)], True, (0, 255, 255) if name == "belt" else (200, 200, 200), 1)
    rows = con.execute(
        "SELECT d.x1,d.y1,d.x2,d.y2,d.keypoints,a.state,a.zone,a.wrist_speed,a.body_speed,d.track_id,a.detail FROM detections d "
        "JOIN person_activity a ON a.frame_idx=d.frame_idx AND a.track_id=d.track_id WHERE d.frame_idx=?", (fidx,)).fetchall()
    for x1, y1, x2, y2, kp, state, zone, ws, bs, tid, detail in rows:
        c = COL[state]
        kp = json.loads(kp)
        for a, b in SKELETON:
            if kp[a][2] > 0.3 and kp[b][2] > 0.3:
                cv2.line(im, (int(kp[a][0]), int(kp[a][1])), (int(kp[b][0]), int(kp[b][1])), c, 2)
        cv2.rectangle(im, (int(x1), int(y1)), (int(x2), int(y2)), c, 2)
        if label:
            txt = detail or {"belt_work": "unloading", "off_belt": "other", "waiting": "waiting"}[state]
            cv2.rectangle(im, (int(x1), int(y1) - 16), (int(x1) + 9 * len(txt), int(y1)), c, -1)
            cv2.putText(im, txt, (int(x1) + 2, int(y1) - 4), 0, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return im
