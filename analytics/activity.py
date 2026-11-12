"""Turn raw detections into per-person activity: which zone, and working the belt / active away from it / waiting.

Reads `detections`, writes `person_activity`. No video needed.
All thresholds live in config/rules.json so they can be tuned and defended in one place.
"""
import json
from collections import defaultdict

import bisect

import cv2
import numpy as np

from pipeline.belt import N_BINS, W as STRIP_W, homography

L_WRIST, R_WRIST, L_HIP, R_HIP = 9, 10, 11, 12

SCHEMA = """
DROP TABLE IF EXISTS person_activity;
CREATE TABLE person_activity (
    frame_idx INTEGER, t_sec REAL, track_id INTEGER,
    zone TEXT,                -- dock_door / far_end / pile_side / floor_side / away
    hands_on_belt INTEGER,    -- 1 if a wrist is over the belt zone
    wrist_speed REAL,         -- body-heights per second
    body_speed REAL,          -- body-heights per second
    state TEXT                -- belt_work / off_belt / waiting
);
CREATE INDEX idx_pa_t ON person_activity (t_sec);
"""


def load_zones(path):
    z = json.load(open(path))
    polys = {k: np.array(v["polygon"], np.float32) for k, v in z["zones"].items()}
    return polys, z["zone_priority"]


def zone_of(pt, polys, priority):
    for name in priority:
        if cv2.pointPolygonTest(polys[name], pt, False) >= 0:
            return name
    belt = polys["belt"]
    if cv2.pointPolygonTest(belt, pt, False) >= 0:
        # leaning over the belt: assign to the side of the centreline they are on
        far_lo, far_up, near_up, near_lo = belt
        a, b = (near_up + near_lo) / 2, (far_up + far_lo) / 2
        side = (b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0])
        return "floor_side" if side < 0 else "pile_side"
    return "away"


def run(con, zones_path="config/zones.json", rules_path="config/rules.json"):
    rules = json.load(open(rules_path))["activity"]
    polys, priority = load_zones(zones_path)
    belt = polys["belt"]
    reach = polys.get("belt_reach", belt)      # hands-at-belt area, perspective-corrected

    # freight along the belt over time, so a touch only counts where there is something to pick up
    H = homography(json.load(open(zones_path))["zones"]["belt"]["polygon"])
    belt_t, belt_bins = [], []
    for bt, bins in con.execute("SELECT t_sec, bins FROM belt_samples ORDER BY t_sec"):
        belt_t.append(bt)
        belt_bins.append(json.loads(bins))

    def freight_near(t_sec, x, y):
        j = min(max(bisect.bisect_left(belt_t, t_sec), 0), len(belt_t) - 1)
        sx = cv2.perspectiveTransform(np.float32([[[x, y]]]), H)[0, 0, 0]
        b = int(np.clip(sx / STRIP_W * N_BINS, 0, N_BINS - 1))
        # look further upstream (towards the dock door): that is the freight about to arrive at the hand,
        # and at the far end the last stretch of belt is hidden behind the people standing there
        lo, hi = max(0, b - rules["freight_reach_bins_upstream"]), min(N_BINS, b + rules["freight_reach_bins"] + 1)
        return max(max(belt_bins[k][lo:hi]) for k in range(max(0, j - 2), min(len(belt_t), j + 3)))

    rows = con.execute(
        "SELECT frame_idx, t_sec, track_id, x1, y1, x2, y2, conf, keypoints FROM detections "
        "WHERE track_id IS NOT NULL ORDER BY track_id, frame_idx").fetchall()
    tracks = defaultdict(list)
    for r in rows:
        tracks[r[2]].append(r)

    out, dropped = [], []
    for tid, recs in tracks.items():
        kp = np.array([json.loads(r[8]) for r in recs], np.float32)       # T x 17 x 3
        t = np.array([r[1] for r in recs])
        box = np.array([r[3:7] for r in recs], np.float32)
        conf = np.array([r[7] for r in recs])
        centre = (box[:, :2] + box[:, 2:]) / 2
        # a "person" that never moves and is never confidently a person is freight (e.g. a printed sack)
        if len(recs) > 50 and conf.mean() < rules["ghost_max_conf"] and centre.std(0).max() < rules["ghost_max_std_px"]:
            dropped.append(tid)
            continue
        hips_ok = (kp[:, [L_HIP, R_HIP], 2] > 0.3).all(1)
        ref = np.where(hips_ok[:, None], kp[:, [L_HIP, R_HIP], :2].mean(1), centre)
        bh = np.maximum(box[:, 3] - box[:, 1], 60.0)

        wr = kp[:, [L_WRIST, R_WRIST], :]
        on_belt = np.zeros(len(recs), bool)
        at_freight = np.zeros(len(recs), bool)
        for i in range(len(recs)):
            for w in wr[i]:
                if w[2] > 0.3 and cv2.pointPolygonTest(reach, (float(w[0]), float(w[1])), True) >= -rules["belt_reach_px"]:
                    on_belt[i] = True
                    if freight_near(float(t[i]), float(w[0]), float(w[1])) >= rules["freight_min_occupancy"]:
                        at_freight[i] = True

        dt = np.diff(t, prepend=t[0])
        ok = (dt > 0) & (dt <= 0.45)
        body = np.zeros(len(recs)); wrist = np.zeros(len(recs))
        d_ref = np.linalg.norm(np.diff(ref, axis=0, prepend=ref[:1]), axis=1)
        body[ok] = d_ref[ok] / dt[ok] / bh[ok]
        d_w = np.linalg.norm(np.diff(wr[:, :, :2], axis=0, prepend=wr[:1, :, :2]), axis=2)       # T x 2
        vis = (wr[:, :, 2] > 0.3) & (np.roll(wr[:, :, 2], 1, axis=0) > 0.3)
        d_w = np.where(vis, d_w, 0).max(1)
        wrist[ok] = d_w[ok] / dt[ok] / bh[ok]

        k = rules["smooth_samples"]
        def roll(a, f):
            return np.array([f(a[max(0, i - k):i + k + 1]) for i in range(len(a))])
        wrist_s, body_s, belt_s = roll(wrist, np.median), roll(body, np.median), roll(on_belt.astype(float), np.mean)

        # A belt touch = a hand at the belt, next to freight, while the hands are moving.
        # Resting a hand on the belt, or touching a bare stretch of it, does not count.
        # Someone is "working the belt" for a few seconds either side of each touch: the pick, the turn to
        # drop, and the return. Movement with no touch nearby is activity away from the belt.
        touch_t = t[at_freight & (np.maximum(wrist_s, body_s) >= rules["touch_min_speed"])]
        states, last_touch = [], None
        for i in range(len(recs)):
            moving = max(wrist_s[i], body_s[i]) >= rules["active_speed"]
            if len(touch_t) and np.abs(touch_t - t[i]).min() <= rules["cycle_window_seconds"]:
                state = "belt_work"
                past = touch_t[touch_t <= t[i]]
                last_touch = past.max() if len(past) else last_touch
            elif (states and states[-1] == "belt_work" and moving and t[i] - t[i - 1] <= 0.45
                  and last_touch is not None and t[i] - last_touch <= rules["carry_max_seconds"]):
                state = "belt_work"          # still carrying what they picked: the cycle runs until they stop
            elif moving:
                state = "off_belt"
            else:
                state = "waiting"
            states.append(state)
        for i, r in enumerate(recs):
            state = states[i]
            zone = zone_of((float(ref[i, 0]), float(ref[i, 1])), polys, priority)
            out.append((r[0], r[1], tid, zone, int(on_belt[i]), round(float(wrist_s[i]), 3),
                        round(float(body_s[i]), 3), state))

    con.executescript(SCHEMA)
    con.executemany("INSERT INTO person_activity VALUES (?,?,?,?,?,?,?,?)", out)
    con.execute("INSERT OR REPLACE INTO video_meta VALUES ('ghost_tracks_dropped', ?)", (json.dumps(dropped),))
    con.commit()
    return len(out), dropped
