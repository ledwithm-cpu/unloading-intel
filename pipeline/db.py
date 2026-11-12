"""SQLite storage for the pipeline. One file, queryable without touching the video again."""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS video_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
-- One row per person per sampled frame.
CREATE TABLE IF NOT EXISTS detections (
    frame_idx INTEGER NOT NULL,      -- frame number in the source video
    t_sec     REAL    NOT NULL,      -- seconds from video start
    track_id  INTEGER,               -- anonymous tracker id (NULL if untracked)
    x1 REAL, y1 REAL, x2 REAL, y2 REAL,
    conf      REAL,
    keypoints TEXT                   -- JSON: 17 COCO keypoints [[x, y, conf], ...]
);
CREATE INDEX IF NOT EXISTS idx_det_t ON detections (t_sec);
CREATE INDEX IF NOT EXISTS idx_det_track ON detections (track_id);
-- One row per sampled frame, even when nobody is detected.
CREATE TABLE IF NOT EXISTS frames (
    frame_idx INTEGER PRIMARY KEY,
    t_sec     REAL NOT NULL,
    n_people  INTEGER NOT NULL
);
-- Belt state samples.
CREATE TABLE IF NOT EXISTS belt_samples (
    t_sec      REAL PRIMARY KEY,
    occupancy  REAL,                 -- 0..1 share of belt surface covered by freight
    speed      REAL,                 -- signed movement along belt axis, belt-lengths per second (NULL if too little freight to measure)
    surface_tex REAL,                -- texture of the bare belt surface: low = moving (blurred), high = stopped
    bins       TEXT                  -- JSON: occupancy in N bins from infeed (dock door) to discharge (far end)
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.executescript(SCHEMA)
    return con
