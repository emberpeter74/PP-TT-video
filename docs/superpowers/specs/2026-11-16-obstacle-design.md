# Step 9: `obstacle` (knocked-over cones) and a place for later kinds of event

Status: approved by the author on 2026-11-16, **built** on the same day in tasks O0 to O4. Deviations from this design: the picture rate is 5 per second, not 2 (fixed by the count); the "row of cones" test only counts a clearly smaller inner box (less than half the width), so a second box around the same cone does not hide it; the model is loaded only when pictures are really searched; the run reports the cone search as its own progress line. The count of O0 was done on the three examples only (16 reports, 15 real, 1 false; see the technical spec); the author then decided to build the recognition as it is and to improve it in a later phase, so the five videos in `input video files/` were not counted. The plan is in `docs/superpowers/plans/2026-11-16-obstacle.md`.

## 1. What the author wants, and why

- **`obstacle`.** The most common thing on the track is a cone (bólya). Cones mark the edge of the track, also where they stand on tarmac to close off parts that are not in today's layout. A cone becomes an obstacle when a car knocks it onto the track. Other things can be obstacles too (car parts, a person, a stopped car), but cones come first.
- **`other event`.** Not a detector for "anything unusual". The author wants the software arranged so that a new kind of event can be added later in one clear place.
- **A false alarm is worse than a missed event** (business spec). This decides every cut-off below.

## 2. What was tried (throwaway trials on the 12-17 example, 00:30 to 05:00, two pictures per second, 540 pictures)

| Trial | Result |
|---|---|
| A ready-made model that takes words (OWLv2, given "a traffic cone") | Finds cones from about 8 pixels wide, in orange, white and black. Near cones score 0.5 to 0.7, far ones 0.2 to 0.3. About 0.27 s per picture on the graphics card. Steady from lap to lap. |
| The same model with "a person", "a car part on the road", "debris on the road" | Not usable as it is: finds the driver in the mirror, arms, things in the cockpit. |
| Compare laps: more cones at this spot than on the last lap | Failed. The 750 m track is lined with markers (up to 28 sure sightings per 25 m), and the count at one spot jumps between laps (for example 6, 8, 5, 2, 3, 6, 3) without any change. |
| Tarmac all around the cone, not part of a row | Failed. 13 reports, all upright markers standing on tarmac; none of the author's obstacles, which lie at the white line or on the kerb. |
| **The cone's box is wider than tall (it lies on its side)** | **Works.** See below. |

The lying-cone rule on those 540 pictures, judged by the assistant from cut-outs and confirmed by the author for the kinds of cone shown:

| Values | Real moments | False moments |
|---|---|---|
| score from 0.30, at least 1.2 times as wide as tall, at least 10 pixels wide | 9 | 4 |
| score from 0.30, at least **1.5** times as wide as tall, wide boxes holding other cones dropped | **9** | **1** (01:42.5: a standing cone half hidden behind the driver's hand) |
| the same with score from 0.35 | 7 (02:27 is lost) | 0 |

- The 9 real moments: 02:08.5, 02:26.5, 02:43.0, 02:50.0, 03:01.5, 03:27.0, 03:38.0, 04:04.5, 04:14.0. They are five fallen cones or groups, seen again on later laps (a lap takes 34 to 37 seconds).
- The author's hand-made file marks 02:09, 02:27 and 02:42. All three are found.
- The group at 02:50 (again at 03:27 and 04:03) lies on the kerb and the grass patch inside a corner. The author: not important, it is not in the intended path; 02:51 is the better time. It is accepted in the first version (assumption of the assistant, see section 8).
- Weak point: real lying cones score only 0.30 to 0.44, close to the cut-off.
- Most lying cones are caught in one picture only at two pictures per second. At one picture per second, 3 of the 9 moments are missed.

Not shown by the trials: anything about the other seven videos; blue cones; how often a false report appears on footage with another camera view.

## 3. Goals, non-goals, anti-goals

Goals of this step:

- The module writes `obstacle` for a knocked-over cone, on every lap on which it is seen (decided by the author: "every lap").
- The cone boxes are saved per video, so that only the first run is slow and the rule can be tuned from the saved copy.
- A new kind of object, or a new rule on the objects found, has one clear place.
- The check video shows the cone boxes and which of them the rule took for an obstacle.

Non-goals (left for later, each could be a later kind):

- An upright cone standing in the way; car parts; a person; a stopped car.
- Judging whether a lying cone is on the tarmac or in the driver's intended path.
- Reporting a cone once only, when it first appears (needs a memory of earlier laps).
- Any use of the GPS or of laps. "Every lap" needs neither.
- A detector for "anything unusual".

Anti-goals (would make the step a failure even if it runs):

- False `obstacle` lines on videos without fallen cones. A marker cone standing in its place must never be reported.
- A run that becomes much slower without the author having chosen it.
- A change to the saved car detections (`name-detections.json`) that makes the existing files unusable.

## 4. Approaches considered

Finding the object:

| Way | Trade-off | Verdict |
|---|---|---|
| A model that takes words | Any colour; a new kind of object is a new line of words; one new library | **Chosen.** Tried and works for cones. |
| Train our own cone finder | Could be more exact, but cones only, and hours of marking pictures | Dropped for now |
| "Something that is not tarmac" | No library, but lines, patches, shadows and kerbs all differ from tarmac | Dropped |

Deciding that it is an obstacle:

| Way | Trade-off | Verdict |
|---|---|---|
| Lying on its side (box wider than tall) | Simple; misses upright cones and other objects; does not judge where it lies | **Chosen** for the first version |
| Tarmac around it, not in a row | Tried: reports markers, misses the real ones | Dropped |
| New at this spot compared with earlier laps | Tried in its simple form: does not work on a track lined with cones | Dropped |

## 5. The design

### 5.1 Parts (new files in `pp_tt_video/`)

| File | Job |
|---|---|
| `find_objects.py` | `ObjectDetector`: loads the model once, takes pictures, returns boxes with the kind of object and a score. `transformers` is imported inside the class, as `detect_cars.py` does with torch, so everything else runs without it. |
| `objects_file.py` | Saves and loads the boxes of one video as `name-objects.json`, with the settings they were made with, and checks whether a saved file still fits today's settings. Separate from `name-detections.json`, which stays as it is. |
| `object_events.py` | The rules on the objects found. Holds the list of rules and the first rule, `lying_cones`. |

Changed: `settings.py` (new block), `detect_events.py` (the object search and its stretches join the others), `pipeline.py` (save and reuse the objects file, as for the car detections), the check video (`explain.py`, `draw.py`, `check_video_settings.py`), `requirements.txt`, the specs.

### 5.2 The place for later kinds of event

Two small tables, and nothing else needs to change for a new kind:

- **What to look for**, in `settings.py`: `OBJECT_WORDS = {"cone": "a traffic cone"}`. The key is the kind, the value is the words given to the model. A new kind of object is a new line.
- **What to make of it**, in `object_events.py`: `OBJECT_RULES = [lying_cones]`. Each rule is a function that takes the saved objects and returns stretches with a label. A new rule is a new function added to the list. Its label must be in `event_types.csv`, as for every event.

A newly named event (business spec, section 5) is therefore: a line in `event_types.csv`, perhaps a line of words, and one rule function.

### 5.3 The object search

- Runs on the same reduced pictures as the car search (1280 wide), but at its own rate: `OBJECT_FRAMES_PER_SECOND`. Value **5**, fixed by the count of O0: half of the lying cones are seen in one picture only, and at 2.5 per second a third or more would be missed. (The first proposal was 2.)
- Saves every box the model gives from score `OBJECT_MIN_CONFIDENCE` (first value 0.15), so the rule's cut-offs can be tuned later without a new search.
- Cost: about 0.27 s per picture plus a second reading of the video, so about 1.25 times the video's length is added to the first run at 5 pictures per second (measured in O0). Later runs read the saved file.
- The model's files (several hundred MB) are downloaded once, on first use, as the car model's were.
- A video whose objects file is missing or does not fit the settings gets a new search. A run with `--gps-only` does none.

### 5.4 The rule `lying_cones`

A box counts as a lying cone when all of these hold (values in `settings.py`, read at run time):

| Setting | First value | Meaning |
|---|---|---|
| `OBSTACLE_MIN_CONFIDENCE` | 0.30 | how sure the model must be |
| `OBSTACLE_MIN_WIDTH_RATIO` | 1.5 | the box is at least this many times as wide as tall |
| `OBSTACLE_MIN_WIDTH_FRACTION` | 10 / 1280 | the box is at least this wide, as a part of the picture's width |

and the box does not hold the centre of another cone box (a far row taken for one wide object).

From sightings to an event:

- Sightings at most `OBSTACLE_MERGE_SECONDS` (first value 3) apart are one event.
- It starts at the first sighting and ends `OBSTACLE_TAIL_SECONDS` (first value 2) after the last: the cone is seen, then passed. (Assistant's call. The hand-made file has 3 s, 1 s and 7 s for its three.)
- The stretches go through `combine_stretches` with all other events, so cones in the paddock and outside the part at pace are dropped.

### 5.5 Check video

- Cone boxes are drawn thin; a box the rule took for a lying cone is drawn thick, in its own colour, with its score. Switched in `check_video_settings.py`.
- `obstacle` appears in the event line and in the overview picture like every other event.

### 5.6 Library

- `transformers` (installed for the trial, version 5.23.0) becomes a dependency. `requirements.txt` points at PyTorch's own server, so it gets an extra line for the normal package server and the pinned version.
- No check in `tests/` needs the model or the library: the detector is tested with a stand-in, the file and the rule with made-up boxes. One check on the real examples is skipped when their files are missing, as now.

## 6. Order of work (each step ends with something that runs and one commit)

0. **O0: the count, before any module code.** With throwaway scripts, save the cone boxes of all eight videos (at 5 pictures per second, so the rate can be chosen from data) and count what the rule of section 5.4 would report in each. **This count is the go/no-go for everything after it**: the author looks at the cut-outs of every report. The five videos in `input video files/` (four of the practice driver, one of the stronger driver) need the author's yes before they are run (slow).
1. **O1: search and save.** `find_objects.py`, `objects_file.py`, the settings. No rule yet.
2. **O2: the rule.** `object_events.py`, wiring in `detect_events.py` and `pipeline.py`, values from the count of O0. `obstacle` appears in the events files.
3. **O3: check video.** The boxes and the rule's choice are drawn.
4. **O4: the specs** are brought up to date (can be folded into O2 and O3 where it fits).

## 7. How the result is judged

- On 12-17 the module should report the three marked obstacles, and will report about six more for the same cones on later laps and the kerb group. Against the hand-made file these count as extra; they are listed, not hidden. The hand-made file is not changed.
- On the other seven videos no hand-made obstacles exist. Every report is shown to the author as a cut-out and judged.
- The step is good when the author accepts the reports of all eight videos.

## 8. Decisions and assumptions to confirm

Decided by the author:

- Cones first; other objects later. Colour must not matter.
- `other event` means a clear place to add later kinds, not a detector.
- The lying cones of the trial sheet are what is meant by an obstacle.
- A cone that stays is reported on every lap.

Changes this makes to the business spec (to be written in when the design is approved):

- Section 5 ("flags segments that look unusual") is replaced by: new kinds are added as described in 5.2; `other event` stays a fixed label that no rule writes yet.
- `obstacle`: the first version finds knocked-over cones only.

Assumptions of the assistant:

- A lying cone on the kerb or at the grass edge is reported too, although it is not in the intended path. Leaving it out would need the "is it on the track" judgement that two trials could not make.
- The first values in 5.3 and 5.4.
- Drawing the cone boxes in the check video belongs to this step.

## 9. Known risks

- The real cones score close to the cut-off. On other footage the choice may be between missing them and false reports; then missing wins.
- A standing cone half hidden behind a hand or the wiper can look wide (one case in the trial). A cone must touch nothing of the cockpit to be sure, and the rule cannot see the cockpit.
- The practice driver's camera view differs. Untested.
- One track, one day, orange cones on the ground. Fallen cones of another colour are untested.
