# Unloading Efficiency Intelligence

A prototype that turns CCTV footage of a parcel unloading line into answers an operations manager can act on: when the conveyor
was moving freight, when it was starved or stopped, what the team was doing at the time, and where the lost minutes went.

Built for the Protex AI Forward Deployed Engineer take-home, on the supplied 28.5-minute video.

## What it found

- **The belt moved freight 62% of the time.** The other 11 of 29 minutes went to stops (25%) and gaps in supply (14%).
- **The belt was stopped for a quarter of the session**, 4.5 minutes of it with freight sitting on it.
- **The sorting team outran the supply from the truck** in the first six minutes: most people in view, belt flowing 39% of the time.
- **The line averaged 46% of its own best minute.** The same people and belt showed the higher rate; the gap is steadiness.
- **Unloading follows the belt.** People unload about 74% of the time when it flows and 27% when it is stopped and empty.
- **Safety, from the same data:** seven candidate belt crossings, three while it was moving, and 52 periods of leaning on the belt.

People figures are estimates; belt figures are the reliable ones. See [Accuracy](#accuracy).

## Designed to be deployable: privacy first

Cameras that measure how people work meet resistance from the people being filmed, and from works councils and unions. The
design choices below are there so the system can be put in front of a workforce.

- **It reports by working area, not by person.** The questions an operations manager asked (is the belt used, are there enough
  people at each position, where does the line stall) are answered per area and per minute. Nobody is ranked or named.
- **No identities.** People are anonymous numbers that do not persist. There is no face recognition.
- **Faces are blurred by default**, using the head position the pose model already produces, so privacy costs no extra model
  or compute.
- **Processing is local.** No footage or images leave the machine. The whole video processes in about 13 minutes on two CPU cores.
- **Footage stays out of the repository.** The source video, review reel and stills are excluded.

One honest note: reporting by area was also forced by the data. The tracker did not hold identities well enough to follow
individuals (see Limitations), so per-person figures would not have been reliable even if they were wanted.

## Quick start

Requirements: Python 3.10+, Node 18+, ffmpeg.

```bash
pip install -r requirements.txt

# 1. See the results without the video (the processed database is committed)
python -m analytics.run          # rebuild activity, timeline, events, insights (seconds)
python -m analytics.evaluate     # score the rules against the human review
python skill/unloading-intel/scripts/query.py summary

# 2. Run the app (needs the video for playback)
#    Download the source video to data/source.mp4, then:
python -m pipeline.blur          # writes app/public/video/unloading.mp4 with faces blurred (~8 min)
python -m analytics.export       # writes app/public/data/*.json
cd app && npm install && npm run dev      # http://localhost:5173

# 3. Reprocess from scratch (optional, ~15 min on 2 CPU cores)
python -m pipeline.detect --video data/source.mp4 --db data/unloading.db
python -m pipeline.belt   --video data/source.mp4 --db data/unloading.db
python -m analytics.run && python -m analytics.export
```

The source video is not in the repository because it shows identifiable workers.

## Architecture

```
 video ──► pipeline/ ──► data/unloading.db ──► analytics/ ──► app/public/data/*.json ──► app/  (React)
           detect.py     detections, pose,     activity.py     session.json               Session, Accuracy,
           belt.py       tracks, belt samples  timeline.py     frames.json                Zones, Site view
           blur.py                             events.py
                                 ▲             safety.py   ──► data/insights.json
                                 │             insights.py
           config/zones.json ────┤             export.py
           config/rules.json ────┘             evaluate.py ◄── data/review_labels.json (human corrections)
                                 │
                                 └──────────► skill/unloading-intel/  (Claude skill: SKILL.md + query.py)
```

| Layer | Folder | What it does | Touches the video? |
|---|---|---|---|
| Computer vision | `pipeline/` | Detect, track and pose-estimate people; measure belt coverage and movement; blur faces | Yes |
| Storage | `data/unloading.db` | One SQLite file: every detection, 17 pose keypoints, track ids, belt samples | |
| Configuration | `config/` | `zones.json` (polygons) and `rules.json` (every threshold) | |
| Analytics | `analytics/` | Worker activity, per-second timeline, events, safety, insight cards, export, evaluation | No |
| Application | `app/` | React + TypeScript + Vite. Reads static JSON; no server | Playback only |
| Claude skill | `skill/unloading-intel/` | Instructions plus a query script over the database | No |

The split that matters: **anything that needs pixels happens once, in `pipeline/`. Everything else runs from the database in seconds.**
Changing a rule, a working-area zone or an insight never reprocesses video. The one exception is the belt zone itself, because belt
coverage is measured from the pixels inside it (a two-minute pass).

### Data model

| Table | One row per | Key columns |
|---|---|---|
| `detections` | person per sampled frame (5 fps) | `t_sec`, `track_id`, box, `conf`, `keypoints` (JSON, 17 COCO points) |
| `frames` | sampled frame | `n_people` |
| `belt_samples` | half-second | `occupancy`, `speed`, `surface_tex`, `bins` (coverage along the belt) |
| `person_activity` | person per sampled frame | `zone`, `hands_on_belt`, `state`, `detail` |
| `timeline` | second | `belt_state`, `occupancy`, `throughput`, people by state, `by_zone` |
| `events` | detected moment | `type`, start, duration, people present / unloading / waiting |

## Technical decisions

| Decision | Choice | Why |
|---|---|---|
| People and pose | YOLO11s-pose with ByteTrack, run through OpenVINO | Off-the-shelf, as the brief asks. OpenVINO made it 5x faster on CPU, so the whole video processes in about 13 minutes on two CPU cores |
| Sampling | 5 frames per second | Enough to see a pick or a step; a quarter of the compute |
| Belt coverage | Classical image processing, no model | The belt is a fixed dark surface. Learn its empty appearance per pixel, then measure what differs. Robust and explainable |
| Belt movement | Phase correlation along the rectified belt | Gives stopped vs moving and a relative speed without tracking parcels |
| Worker activity | Rules on pose, zones and belt coverage | Transparent and tunable in one file. See limits below |
| Storage | SQLite | One file, no setup, queryable by the app export, the skill and a person |
| App data | Static JSON | No backend to deploy or secure; the app can be hosted anywhere |
| Faces | Blurred from the stored pose keypoints | Privacy by default, with no extra model |

Two things I learned the hard way, both caught by checking output against the video:

- A stopped belt shows scuff texture that a moving belt blurs away. The first belt measure read a stopped, empty belt as 60 to 80% full.
- From this camera angle, hands held above the far side of the belt appear 30 to 50 pixels above it. The first hands-at-belt rule
  missed most of the work on that side. The fix is a separate `belt_reach` zone.

## How "unloading" is decided

Each person, five times a second, is in one of three states:

- **Unloading:** a hand in the belt-reach zone, next to freight, while moving; plus up to ten seconds of continuous movement either
  side (the carry away, or the fetch towards). Includes loading onto the belt.
- **Other activity:** moving, with no belt contact.
- **Waiting:** still. A still hand on the belt is marked `leaning`.

A track that passes from one side of the belt to the other is marked `crossing` and is not counted as unloading.

## Accuracy

Checked by a person watching 20 random five-second moments (five per belt state) with the system's labels drawn on
(`python -m analytics.review` builds the reel).

| What | Result |
|---|---|
| Belt state | 20 of 20 moments correct |
| Person labels, first rule | 94 of 100 person-clips correct |
| Corrections across four review rounds | 12 of 13 now satisfied (`python -m analytics.evaluate`) |
| Precision and recall | Not measured |

Every correction from review is stored in `data/review_labels.json` and scored automatically, so a rule change that fixes one case
and breaks another is caught. The review method shows the reviewer the system's answer first, which flatters the system; a blind
labelling pass is the next step before these figures support a staffing decision. The app's "How accurate is this?" page explains
this for a non-technical reader.

Sensitivity: as the rules were tuned, the unloading share moved between 62% and 77%. Waiting was steadier. Comparisons (flowing vs
stopped, far end vs pile side) held in every version; absolute levels should be read as approximate.

## Assumptions

- Freight enters on the belt from a truck at the dock door (out of view, bottom right) and travels to the far end (top left).
- Workers along the belt mainly take freight off it to sort; some load onto it from cages.
- The camera is fixed. Measured drift across the session was under one pixel.
- The camera clock is correct; video 0:00 is 06:04:57.
- "Bay BN1" is taken from the video title.

## Limitations

- **Intent is not visible in pose.** Someone gesturing beside a loaded belt looks like someone handling freight. This is the one open
  review correction.
- **Loading and unloading share a label.** Telling them apart needs to know which way the parcel moved.
- **No parcel detection.** Throughput is a flow index (coverage x speed), not parcels per minute. A test of an open-vocabulary
  detector found parcels on the belt reliably but not parcels in hands.
- **The truck is off camera.** Supply rate is inferred.
- **Why the belt stops is not measured.** The data shows what people were doing around each stop, not the cause.
- **Tracking does not hold identities.** It produced 249 ids for about eight people, so nothing here follows one person across
  the session. Results are by position and working area, which is also the privacy-preserving choice (see above).
- **Belt crossings are candidates.** The rule also catches long reaches across the belt.
- **Face blur covers detected people only.** Anyone the detector misses in a frame is not blurred in that frame.
- **One session, one bay, one camera.** Nothing here generalises to the site without more footage.

## Extending it

- **More bays.** A bay is a video plus a `zones.json`. The pipeline and analytics are unchanged; the timeline schema is the same per
  bay, which is what a cross-bay reallocation alert needs (the Site view page shows the idea with example data).
- **Parcel counting.** Add a stage that writes a `parcels` table; `timeline.throughput` becomes parcels per minute.
- **Richer activity labels.** Replace or supplement `analytics/activity.py` with a vision-language model over short person clips
  (loading, carrying, leaning, smoking). The review label set already exists to score it. This sends worker images to a model, so
  it is a privacy decision as well as a technical one.
- **Process data.** Join `timeline` to scans or a WMS feed on time, so each stop shows the freight scanned just before it. This is
  the step that lets the system suggest a cause for a stop; today it can only show what people were doing around it.
- **Live operation.** The stages are already separate; run `detect` and `belt` on a stream and append to the same tables.
- **A second camera at the dock door** would turn the largest inference (supply from the truck) into a measurement.

## The Claude skill

`skill/unloading-intel/` holds `SKILL.md` and `scripts/query.py`. It is linked into `.claude/skills/`, so opening this repository in
Claude Code makes it available. Ask, for example:

- When was the conveyor most underutilised?
- How many workers were actively unloading during the busiest period?
- Show me periods where three people were present but only one appeared to be working.
- What are the biggest opportunities to improve unloading efficiency?

The skill tells Claude to run the query script for facts, cite video timestamps, and state the caveat that applies.

## How this was built

I am not a career software engineer. I directed Claude as the engineering team and made the product, computer-vision and
architecture decisions: what to measure, what counts as unloading, what to store, and what to say about accuracy. The activity rules
in particular went through four rounds where I reviewed labelled clips, found the errors, and decided how the definition should
change. Those rounds are recorded in `data/review_results.json` and in the commit history.
