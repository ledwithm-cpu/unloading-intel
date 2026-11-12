"""Safety signals from the same stored data: people crossing the belt, and people leaning on it.

Runs after activity and events. Relabels crossing frames in `person_activity` (a jump over the belt is not
unloading) and appends `belt_crossing` and `leaning_on_belt` events.
"""
import json
from collections import defaultdict

import cv2
import numpy as np


def _iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-6)


def find_crossings(con, belt, rules):
    """One continuous track whose feet go from the floor side, through the belt, to the far side (or back)."""
    far_lo, far_up, near_up, near_lo = belt
    a0, b0 = (near_up + near_lo) / 2, (far_up + far_lo) / 2
    axis = b0 - a0
    length = np.linalg.norm(axis)
    axis = axis / length
    normal = np.array([-axis[1], axis[0]])
    w_near, w_far = np.linalg.norm(near_up - near_lo), np.linalg.norm(far_up - far_lo)

    tracks = defaultdict(list)
    for r in con.execute("SELECT d.track_id, d.t_sec, d.x1, d.y1, d.x2, d.y2 FROM detections d "
                         "JOIN person_activity a ON a.frame_idx=d.frame_idx AND a.track_id=d.track_id ORDER BY d.track_id, d.frame_idx"):
        tracks[r[0]].append(r[1:])
    hits = []
    for tid, recs in tracks.items():
        t = np.array([r[0] for r in recs])
        box = np.array([r[1:] for r in recs])
        feet = np.stack([(box[:, 0] + box[:, 2]) / 2, box[:, 3]], 1)
        d = (feet - a0) @ normal
        s = ((feet - a0) @ axis) / length
        half = (w_near * (1 - s) + w_far * s) / 2
        floor, far = d < -half - 8, d > -half * 0.2
        for i in range(len(t) - 1):
            if not 0.1 < s[i] < 0.9:
                continue
            j = min(len(t) - 1, int(np.searchsorted(t, t[i] + rules["crossing_max_seconds"])))
            if j - i < 3 or not ((floor[i] and far[j]) or (far[i] and floor[j])):
                continue
            if any(_iou(box[k], box[k + 1]) < 0.35 or t[k + 1] - t[k] > 0.45 for k in range(i, j)):
                continue                                  # identity may have switched: not one person
            h = box[i:j + 1, 3] - box[i:j + 1, 1]
            if h.min() < 0.6 * h.max():
                continue                                  # box collapsing = occlusion, not a crossing
            if max(cv2.pointPolygonTest(belt, (float(feet[k, 0]), float(feet[k, 1])), True) for k in range(i, j + 1)) > 4:
                hits.append((float(t[i]), float(t[j]), tid))
    merged = []
    for a, b, tid in sorted(hits):
        if merged and merged[-1][2] == tid and a - merged[-1][1] <= 3:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b, tid])
    return merged


def run(con, zones_path="config/zones.json", rules_path="config/rules.json"):
    rules = json.load(open(rules_path))["safety"]
    belt = np.array(json.load(open(zones_path))["zones"]["belt"]["polygon"], np.float32)
    tl = {r[0]: r for r in con.execute("SELECT t_sec, belt_state, belt_moving, occupancy, n_present FROM timeline")}
    events = []

    for a, b, tid in find_crossings(con, belt, rules):
        con.execute("UPDATE person_activity SET state='off_belt', detail='crossing' WHERE track_id=? AND t_sec>=? AND t_sec<=?",
                    (tid, a - 1, b + 1))
        row = tl.get(int(a), (0, "", 0, 0, 0))
        events.append(("belt_crossing", int(a), int(b) + 1, max(1, int(b - a) + 1), row[4], 0, 0, 0, row[3],
                       json.dumps({"track_id": tid, "belt_moving": bool(row[2]),
                                   "note": "Person crossed or reached fully across the belt. Candidates need a human look: deep reaches are also caught."})))

    # leaning: a still hand on the belt, sustained
    lean = defaultdict(list)
    for tid, t in con.execute("SELECT track_id, t_sec FROM person_activity WHERE detail='leaning' ORDER BY track_id, t_sec"):
        lean[tid].append(t)
    for tid, ts in lean.items():
        start = prev = ts[0]
        for t in ts[1:] + [None]:
            if t is None or t - prev > 1.0:
                if prev - start >= rules["leaning_min_seconds"]:
                    row = tl.get(int(start), (0, "", 0, 0, 0))
                    events.append(("leaning_on_belt", int(start), int(prev) + 1, int(prev - start) + 1, row[4], 0, 1, prev - start, row[3],
                                   json.dumps({"track_id": tid, "belt_moving": bool(row[2])})))
                start = t
            prev = t
    con.executemany("INSERT INTO events (type,start_sec,end_sec,duration_sec,people_present,people_belt_work,people_waiting,"
                    "person_seconds_waiting,occupancy,details) VALUES (?,?,?,?,?,?,?,?,?,?)", events)
    con.commit()
    return len(events)
