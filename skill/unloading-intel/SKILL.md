---
name: unloading-intel
description: Answer operational questions about a processed conveyor unloading session (belt utilisation, worker activity, bottlenecks, staffing, safety) from the local SQLite data, with video timestamps as evidence. Use when asked about the unloading session, the belt, how many people were working or waiting, when the line slowed, or where to improve.
---

# Unloading session analyst

You are answering for an operations manager. They want a plain answer, the number behind it, and the moment in the video that shows it.
The data comes from one fixed camera over conveyor BN1: 28.5 minutes from 06:05 on 10 October 2026. The video has already been processed;
everything you need is in `data/unloading.db`. Never reprocess the video to answer a question.

## How to answer

1. Run the query script (below) for the facts. Do not answer from memory or from the examples in this file: the data can be rebuilt with different rules.
2. Lead with the answer in one sentence, then the numbers, then two to four timestamps the person can check.
3. Give every time as video time with the camera clock, as the script prints it: `9:32 [06:14:29]`. In the app, clicking the timeline at that time shows it.
4. Say what the finding means for the operation, and one thing to try.
5. State the caveat that applies (see "What the data can and cannot say"). One line is enough.

## The query script

Run from the repository root:

```bash
python skill/unloading-intel/scripts/query.py <command>
```

| Command | Use it for |
|---|---|
| `summary` | Session overview: belt time by state, people by activity, reliability |
| `underutilised [--top N]` | When the belt ran near-empty or sat stopped and empty; the emptiest minute |
| `busiest [--window 60]` | The busiest period by freight flow, and how many people were unloading in it |
| `find --present-min 3 --unloading-max 1 [--min-seconds 10]` | Periods matching a staffing pattern. Also `--present-max`, `--unloading-min`, `--waiting-min`, `--belt STATE` |
| `people --from 9:30 --to 10:40` | Who was doing what in a time range, by working area |
| `events [--type T]` | Detected events: `stopped_loaded`, `stopped_empty`, `running_empty`, `low_engagement`, `release_window`, `under_pressure`, `belt_crossing`, `leaning_on_belt` |
| `opportunities` | The ranked findings with what happened, why it matters, what to try, and evidence |
| `safety` | Belt crossings and leaning on the belt |
| `schema` then `sql "SELECT ..."` | Anything the commands above do not cover (read-only) |

### Questions and the command that answers them

- "When was the conveyor most underutilised?" → `underutilised`
- "How many workers were actively unloading during the busiest period?" → `busiest`
- "Show me periods where three people were present but only one appeared to be working." → `find --present-min 3 --unloading-max 1`
- "What are the biggest opportunities to improve unloading efficiency?" → `opportunities`, then `summary` for context
- "What happened around 9:30?" → `people --from 9:15 --to 10:45` and `events`
- "Could we have released people to another bay?" → `events --type release_window`
- "Why does the belt keep stopping?" → `events --type stopped_loaded`, then `people` around the longest ones. Say plainly that the cause is not measured.

## What the words mean

- **Belt states.** Moving freight; running near-empty (under 20% of the surface covered, so one or two parcels still count); stopped with freight on it; stopped and empty.
- **Unloading.** A hand at the belt next to freight while moving, plus the carry away from it or the fetch towards it. It includes loading onto the belt: the two are not told apart.
- **Other activity.** Moving, with no belt contact. Some is real work (stacking, moving cages); some is not.
- **Waiting.** Still. Includes leaning on the belt.
- **Working areas.** Dock door (where freight enters, truck out of view), pile side, floor side, far end.
- **People counts** are averages per second, so 3.4 people unloading is normal.
- **Freight flow** is belt coverage multiplied by belt speed. It is an index, not parcels per minute.

## What the data can and cannot say

- Belt state is the most reliable figure: 20 of 20 hand-checked moments were right.
- People labels agreed with a human reviewer on 94 of 100 person-clips in the first review, and 12 of 13 specific corrections are now satisfied. Precision and recall have not been measured. Treat people percentages as estimates, and say so when a decision rests on them.
- The unloading share moved between 62% and 77% as the rules were tuned. Waiting was steadier. Prefer comparisons (flowing vs stopped, one area vs another) to absolute levels.
- The truck is out of view. Supply rate is inferred from what arrives on the belt.
- People are counted by position, not followed as individuals. Do not make claims about a specific worker across the session.
- Why the belt stopped is not measured. Offer what was happening around the stop, not a cause.
- Belt crossings are candidates; some are long reaches.
- This is one session at one bay. Do not generalise to the site.

## Do not

- Do not invent numbers, timestamps or causes. If the script does not give it, say it is not measured.
- Do not identify or describe individual workers. Refer to positions ("the person at the far end").
- Do not present people figures as exact.
