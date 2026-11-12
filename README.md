# Unloading Efficiency Intelligence

Prototype that turns CCTV footage of a parcel unloading line into operational insight:
when the conveyor was flowing, starved or stopped, what the team was doing at the time, and where the lost minutes went.

**Status: work in progress.** Pipeline, analytics and the React app are in place; the Claude skill and full README follow.

## Layout

| Folder | What it does |
|---|---|
| `pipeline/` | Computer vision. `detect.py` finds, tracks and pose-estimates people; `belt.py` measures conveyor occupancy and movement. Writes to SQLite. |
| `analytics/` | Turns stored detections into worker activity, a per-second timeline, events and insight cards. Never touches the video. |
| `config/` | `zones.json` (editable zone polygons) and `rules.json` (every threshold, in one place). |
| `data/` | `unloading.db` (all detections, pose and belt samples) and `insights.json`. The source video is not committed. |
| `app/` | React application: session review with video overlays and timeline, an accuracy explainer, a zone editor and an illustrative site view. Reads static JSON, no server. |
| `skill/` | Claude skill for querying the data (to come). |

## Run

```bash
pip install -r requirements.txt
# place the source video at data/source.mp4, then:
python -m pipeline.detect --video data/source.mp4 --db data/unloading.db   # ~13 min on 2 CPU cores
python -m pipeline.belt   --video data/source.mp4 --db data/unloading.db   # ~2 min
python -m analytics.run                                                   # seconds; rerun after changing config/
```

The committed `data/unloading.db` already holds the processed results, so the analytics, app and skill work without the video.

## Run the app

```bash
python -m analytics.export                 # writes app/public/data/*.json
# put a web copy of the video at app/public/video/unloading.mp4, for example:
ffmpeg -i data/source.mp4 -an -vf scale=960:540 -c:v libx264 -crf 30 -g 40 -movflags +faststart app/public/video/unloading.mp4
cd app && npm install && npm run dev       # http://localhost:5173
```

## Check the rules against human review

```bash
python -m analytics.evaluate               # scores the labels against data/review_labels.json
python -m analytics.review                 # regenerates the labelled review reel
```
