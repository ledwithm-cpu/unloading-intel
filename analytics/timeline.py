"""Build the per-second timeline: belt state + how many people were working / walking / waiting.

Reads `belt_samples` and `person_activity`, writes `timeline` (one row per second of video).
"""
import json
import warnings
from collections import defaultdict

import numpy as np

SCHEMA = """
DROP TABLE IF EXISTS timeline;
CREATE TABLE timeline (
    t_sec INTEGER PRIMARY KEY,
    belt_state TEXT,          -- flowing / running_empty / stopped_loaded / stopped_empty
    occupancy REAL,           -- 0..1 share of belt surface covered by freight
    belt_moving INTEGER,
    throughput REAL,          -- freight flow index: occupancy x belt speed (0 when stopped)
    n_present REAL, n_handling REAL, n_moving REAL, n_waiting REAL,
    by_zone TEXT              -- JSON {zone: {present, handling, moving, waiting}}
);
"""
ZONES = ["dock_door", "pile_side", "floor_side", "far_end", "away"]


def _rolling_median(a, k):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return np.array([np.nanmedian(a[max(0, i - k):i + k + 1]) for i in range(len(a))])


def run(con, rules_path="config/rules.json"):
    rules = json.load(open(rules_path))["belt"]
    r = con.execute("SELECT t_sec, occupancy, speed FROM belt_samples ORDER BY t_sec").fetchall()
    t = np.array([x[0] for x in r])
    occ = np.array([x[1] for x in r])
    speed = np.array([np.nan if x[2] is None else x[2] for x in r])
    k = rules["smooth_samples"]
    speed_s = np.nan_to_num(np.abs(_rolling_median(speed, k)))
    occ_s = _rolling_median(occ, k)
    moving = speed_s >= rules["moving_min_speed"]
    loaded = occ_s >= rules["loaded_min_occupancy"]

    n_sec = int(t[-1]) + 1
    sec = t.astype(int)
    rows = {}
    for s in range(n_sec):
        m = sec == s
        if not m.any():
            continue
        mv, ld = moving[m].mean() >= 0.5, loaded[m].mean() >= 0.5
        state = ("flowing" if ld else "running_empty") if mv else ("stopped_loaded" if ld else "stopped_empty")
        o = float(occ[m].mean())
        rows[s] = [state, round(o, 3), int(mv), round(o * float(speed_s[m].mean()), 5) if mv else 0.0]

    # people: average over the sampled frames inside each second
    n_frames = defaultdict(int)
    for (ts,) in con.execute("SELECT t_sec FROM frames"):
        n_frames[int(ts)] += 1
    counts = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for ts, zone, state in con.execute("SELECT t_sec, zone, state FROM person_activity"):
        s = int(ts)
        counts[s][zone]["present"] += 1
        counts[s][zone][state] += 1

    out = []
    for s, (state, o, mv, thr) in rows.items():
        nf = max(n_frames.get(s, 1), 1)
        bz = {z: {k2: round(v / nf, 2) for k2, v in counts[s][z].items()} for z in ZONES if z in counts[s]}
        tot = lambda key: round(sum(v.get(key, 0) for v in bz.values()), 2)
        out.append((s, state, o, mv, thr, tot("present"), tot("handling"), tot("moving"), tot("waiting"), json.dumps(bz)))
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO timeline VALUES (?,?,?,?,?,?,?,?,?,?)", out)
    con.commit()
    return len(out)
