"""Find the moments worth an operations manager's attention. Reads `timeline`, writes `events`.

Event types
  running_empty   belt moving with almost nothing on it (supply gap)
  stopped_loaded  belt stopped with freight on it (blockage / manual stop)
  stopped_empty   belt stopped and bare (full idle)
  low_engagement  several people present, at most one working the belt
  release_window  belt idle and people waiting long enough that they could help another bay
  under_pressure  belt saturated or blocked with everyone busy: this bay could use help
"""
import json

SCHEMA = """
DROP TABLE IF EXISTS events;
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    type TEXT, start_sec INTEGER, end_sec INTEGER, duration_sec INTEGER,
    people_present REAL, people_belt_work REAL, people_waiting REAL,
    person_seconds_waiting REAL,
    occupancy REAL,
    details TEXT               -- JSON: per-zone averages
);
"""
ZONES = ["dock_door", "pile_side", "floor_side", "far_end", "away"]


def _segments(flags, min_len, max_gap):
    """Runs of True at least min_len long, bridging gaps up to max_gap."""
    segs, start, gap = [], None, 0
    for i, f in enumerate(flags):
        if f:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap > max_gap:
                segs.append((start, i - gap))
                start, gap = None, 0
    if start is not None:
        segs.append((start, len(flags) - 1 - gap))
    return [(a, b) for a, b in segs if b - a + 1 >= min_len]


def run(con, rules_path="config/rules.json"):
    rules = json.load(open(rules_path))["events"]
    tl = con.execute("SELECT t_sec, belt_state, occupancy, n_present, n_belt_work, n_waiting, by_zone "
                     "FROM timeline ORDER BY t_sec").fetchall()
    secs = [r[0] for r in tl]

    def summarise(kind, a, b):
        rows = tl[a:b + 1]
        n = len(rows)
        zone_tot = {z: {"present": 0.0, "belt_work": 0.0, "waiting": 0.0} for z in ZONES}
        for r in rows:
            for z, v in json.loads(r[6]).items():
                for key in zone_tot[z]:
                    zone_tot[z][key] += v.get(key, 0)
        zones = {z: {k: round(v / n, 2) for k, v in d.items()} for z, d in zone_tot.items() if d["present"] / n >= 0.1}
        return (kind, secs[a], secs[b] + 1, n,
                round(sum(r[3] for r in rows) / n, 2), round(sum(r[4] for r in rows) / n, 2),
                round(sum(r[5] for r in rows) / n, 2), round(sum(r[5] for r in rows), 1),
                round(sum(r[2] for r in rows) / n, 3), json.dumps({"zones": zones}))

    events = []
    for kind in ("running_empty", "stopped_loaded", "stopped_empty"):
        flags = [r[1] == kind for r in tl]
        for a, b in _segments(flags, rules["belt_min_seconds"], rules["bridge_gap_seconds"]):
            events.append(summarise(kind, a, b))
    flags = [r[3] >= rules["low_engagement_min_present"] and r[4] <= rules["low_engagement_max_belt_work"] for r in tl]
    for a, b in _segments(flags, rules["low_engagement_min_seconds"], rules["bridge_gap_seconds"]):
        events.append(summarise("low_engagement", a, b))

    # --- reallocation signals: the two halves of a cross-bay alert ---
    ra = json.load(open(rules_path))["reallocation"]
    k = ra["smooth_seconds"]
    def smooth(col):
        v = [r[col] for r in tl]
        return [sum(v[max(0, i - k // 2):i + k // 2 + 1]) / len(v[max(0, i - k // 2):i + k // 2 + 1]) for i in range(len(v))]
    wait_s, occ_s = smooth(5), smooth(2)
    flags = [tl[i][1] in ra["release_belt_states"] and wait_s[i] >= ra["release_min_waiting"] for i in range(len(tl))]
    for a, b in _segments(flags, ra["release_min_seconds"], rules["bridge_gap_seconds"]):
        events.append(summarise("release_window", a, b))
    flags = [(occ_s[i] >= ra["pressure_min_occupancy"] or tl[i][1] == "stopped_loaded") and wait_s[i] <= ra["pressure_max_waiting"]
             for i in range(len(tl))]
    for a, b in _segments(flags, ra["pressure_min_seconds"], rules["bridge_gap_seconds"]):
        events.append(summarise("under_pressure", a, b))

    events.sort(key=lambda e: e[1])
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO events (type,start_sec,end_sec,duration_sec,people_present,people_belt_work,"
                    "people_waiting,person_seconds_waiting,occupancy,details) VALUES (?,?,?,?,?,?,?,?,?,?)", events)
    con.commit()
    return len(events)
