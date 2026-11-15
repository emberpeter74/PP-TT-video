# Check video: technical specification

Status: approved by the author; steps V1 to V6 are built (see section 11). Items marked **(assumption)** are the assistant's calls; the author can correct them.

What the check video must do is in `CHECK_VIDEO_BUSINESS_SPEC.md`. This document says how it is built. It builds on the module described in `TECHNICAL_SPEC.md`.

## 1. Approaches considered

| Approach | For | Against |
|---|---|---|
| A. A page in the web browser, run by a small Python program | Best video player, easy charts, could follow the analysis live | A second language (HTML and JavaScript) |
| B. A desktop window in Python (PySide6) | One language | Large install, hard to keep boxes in step with the video |
| **C. The command line tool writes a video with everything drawn in** | Simplest, no new install, no second language, plays in any player | No buttons, no watching during the analysis, no clicking on an event |

**Chosen by the author: C.** A and B remain possible later; the files C writes (detections, sensor data) would serve them too.

## 2. Measured before writing this

- **Drawing:** Pillow (a Python drawing library, already installed as part of torchvision) draws five boxes with labels and two charts on a 1280x920 picture in about 5 milliseconds. For a 13-minute video at 30 pictures per second that is about 2 minutes of drawing. So 30 pictures per second is realistic. **To be confirmed** on a real video in step V3, including reading and writing the video.
- **Writing the video:** the ffmpeg in `executables/` has `h264_nvenc` (H.264 on the Nvidia card) and `libx264` (H.264 on the processor). H.264 plays in every player.

## 3. The main idea: detect once, draw from saved data

Detection is slow (about a third of the video's length); everything else is fast. So the work is split:

1. **Detection** (slow) writes the cars found in every analysed picture to `name-detections.json`. This is the raw output of the model, before tracking.
2. **Drawing** (fast) reads that file and the sensor data, runs the tracker and all rules again (seconds), and draws the check video.

When the detections file already exists, drawing starts from it and the detection is skipped. So after changing a setting (what is drawn, or a rule threshold in `settings.py`), the check video can be redrawn in minutes. This also follows the existing advice in `CLAUDE.md`: save detections once, tune from the saved copy.

The detections hold boxes **before** `keep_car_boxes` and the tracker's `drop_double_boxes`, so the thrown-away boxes can be drawn too. Only the model's own lower limit (`MIN_DETECTION_CONFIDENCE`, 0.5) is applied; boxes below it are never seen. **(Assumption: showing boxes below 0.5 is left for later; it would mean changing the model's setting, which could affect the detection itself.)**

## 4. Command line

- New option: `--check-video`. Without it, nothing changes.
- With it, for every video, after the GPX and events files:
  1. If `name-detections.json` is missing (or `--overwrite`): run the detection and save it. When the events file is also being written in the same run, both come from the same detection pass; the detection is never run twice.
  2. Draw `name-check.mp4` and `name-overview.png`, unless they exist and `--overwrite` is not given.
- An existing events file is still skipped and never changed. The check video shows what the current rules decide, which can differ from an older or hand-corrected events file (business spec 3.2).
- `--check-video` together with `--gps-only` is refused with a message.

## 5. Parts and files

New files in `pp_tt_video/`, each small:

| File | What it does |
|---|---|
| `check_video_settings.py` | The settings of the check video, every one with a comment (section 7) |
| `sensor_file.py` | Writes `name-sensors.csv` |
| `detections_file.py` | Saves and loads `name-detections.json` |
| `explain.py` | Runs the tracker and the rules on saved data and collects what the drawing needs: kept and thrown-away boxes with reasons, tracks, kept and thrown-away events with reasons, and the chart values |
| `draw.py` | Draws one picture: boxes, labels, the event line and the sensor strip |
| `charts.py` | The values and thresholds of each sensor rule, for the strip and the overview |
| `check_video.py` | Reads the video, has every picture drawn, writes the check video |
| `overview.py` | Draws and writes the overview picture |

Changes to existing files, kept as small as possible:

- `detect_cars.py`: `CarDetector.detect` can also return the raw boxes (before `keep_car_boxes`). The boxes it returns for detection stay exactly the same.
- `detect_events.py`: the detection pass can hand the raw boxes to a saver. The timeline it returns stays exactly the same.
- `pipeline.py` and `__main__.py`: the new option, and writing the sensor file.
- `video.py`: may get a way to write pictures to ffmpeg (now it only reads).

**The profile is applied around the drawing.** The pipeline runs the drawing inside the same `with using_profile(...)` block as the detection (see "Driver and car profiles" in `TECHNICAL_SPEC.md`). Everything below that reads a threshold from `settings` therefore gets the profile's value without knowing about profiles. `draw.py` gets the profile's name to write in the top corner of every picture and on the overview.

**The rules are not copied.** `explain.py` calls the same functions the detection uses (`forward_force_per_second`, `effort_per_second`, `find_pace_part`, `cornering_and_turning`, `find_catch_times`, `shake_over_time`, `Tracker`, `events_of_track`, `detect_session`, `combine_stretches`), and the threshold lines come from the same names in `settings.py`. If a rule needs to hand out a value it now keeps to itself (for example why a track was skipped), the rule gets a small helper for that, and the rule's result stays the same.

## 6. What is drawn, and where it comes from

### 6.1 Boxes

| Shown | Source |
|---|---|
| Kept box: track number, confidence, height as part of the picture | Tracker sightings; height as in `events_of_track` (box height / picture height) |
| Colour: far / close / passing | height against `CLOSE_CAR_HEIGHT` and `PASSING_CAR_HEIGHT` |
| Thrown away, "too wide" | boxes removed by `keep_car_boxes` (`MAX_CAR_WIDTH_FRACTION`) |
| Thrown away, "double" | boxes removed by `drop_double_boxes` |
| Thrown away, "never sure enough" | tracks with `best_confidence` below `CAR_MIN_CONFIDENCE` |

Boxes are in the coordinates of the analysed pictures (1280 wide), which is also the size of the check video, so no conversion is needed.

Between two analysed pictures (5 per second) the box is held (`BOX_SMOOTHING = "hold"`) or moved evenly from one to the next (`"slide"`). Default: hold, as the author wants to see it first.

### 6.2 Events

- The event line shows the labels of the timeline that `build_timeline` would make from the current rules.
- Thrown-away events: every stretch that `combine_stretches` removes because `outside_pace` is true, with the reason "outside the part at pace". On the four new videos that came out as one long `warm up`, this is probably every event.

### 6.3 Sensor strip

A window of `STRIP_SECONDS_BEFORE` and `STRIP_SECONDS_AFTER` around the current moment, a vertical line at "now". One chart per row:

| Chart | Values | Threshold lines | Source |
|---|---|---|---|
| Pace | forward force per second; pace effort | `PACE_MIN_EFFORT`, `PACE_HARD_FORCE` | `forward_force_per_second`, `effort_per_second` |
| Sliding | cornering force; marks at catch moments | `±SLIDE_MIN_CORNERING_FORCE` | `cornering_and_turning`, `find_catch_times` |
| Turning | turning rate; the same marks | `±SLIDE_MIN_TURNING_BEFORE` | `cornering_and_turning`, `find_catch_times` |
| Offtrack | shake up and down (the rule's); shake sideways and forward (information only) | `OFFTRACK_MIN_SHAKE` | `shake_over_time` |

As built (step V5, `charts.py`):

- **Turning is a chart of its own.** It is measured in radians per second (about ±0.5), the cornering force in m/s² (about ±11): on one scale the turning line would be flat.
- **The offtrack chart has two extra lines, for information only:** the shake sideways and forward. The rule does not use them. Added after step P2: the false offtracks on the son's footage shake up and down only, the real ones in every direction, and the rework of the rule needs to see that.
- **Each chart has one fixed scale for the whole video**, so a value has the same height at every moment: up to twice its largest threshold, or the level only 0.5% of its values exceed, whichever is more. Values beyond the scale are drawn at the edge. The largest value is not used: one jolt would flatten everything else.
- The charts are made inside `explain`, so inside `using_profile`: their thresholds are the profile's.

### 6.4 Overview picture

One PNG, drawn with Pillow, about 2000 pixels wide, time along the bottom:

- pace effort per second with `PACE_MIN_EFFORT` and `PACE_HARD_FORCE`, and the runs that were too short (`PACE_MIN_SECONDS`) marked,
- the session parts from `detect_session` as coloured bands,
- one row per event type: kept events as filled bars, thrown-away ones as outlines,
- one row of bars for the tracked cars.

As built (step V6, `overview.py`):

- 2000 pixels wide; the height grows with the number of event rows (about 550 pixels). Written as `name-overview.png`, about 45 KB, in 1 to 2 seconds.
- **The pace part** uses the pace chart of the strip (`charts.py`): the force per second as a thin line, the effort as a thick one, the two thresholds named at the right edge. Behind them the bands: every session part in its colour, and what no session part covers as "at pace". Without sensor data it only says so.
- **"Too brief"**, a row of marks under the pace part: where the effort was above `PACE_MIN_EFFORT` for less than `PACE_MIN_SECONDS`, so it did not count as at pace.
- **Event rows:** one per label that occurs, in the order of `event_types.csv`. Kept events are filled bars, thrown-away ones outlines. A bar is at least 3 pixels wide, so an event of one second can be seen.
- **Cars:** one bar per car that was followed, with the number of cars in the row's name. A car the model was never sure of (skipped by the car rules) is an outline.
- **Time line:** a tick per minute; the times are written every 1, 2, 5, ... minutes, so that they never run into each other.
- It is made by `make_check_video`, inside the same `using_profile` block. The check video and the overview are each made unless they exist: an overview missing next to an older check video is added from the saved detections without drawing the video again (without a detections file it needs a detection pass). `WRITE_OVERVIEW = False` switches it off.

## 7. The settings file

`pp_tt_video/check_video_settings.py`, a Python file like `settings.py`, but only for the check video. **(Assumption: a Python file rather than another format, because the author already knows `settings.py`; every setting gets a comment line saying what it does and what values it takes.)**

A first list:

| Setting | Meaning | Default |
|---|---|---|
| `FRAMES_PER_SECOND` | Pictures per second in the check video | 30 |
| `KEEP_SOUND` | Copy the sound from the original video | True |
| `SHOW_KEPT_BOXES` | Draw the cars the module kept | True |
| `SHOW_BOX_DETAILS` | Write track number, confidence, height next to each box | True |
| `SHOW_DROPPED_BOXES` | Draw the boxes that were thrown away, with the reason | True |
| `BOX_SMOOTHING` | `"hold"` or `"slide"` | `"hold"` |
| `SHOW_EVENTS` | Write the current labels across the top | True |
| `SHOW_DROPPED_EVENTS` | Also write the events that were thrown away | True |
| `SHOW_STRIP` | Draw the sensor strip | True |
| `STRIP_CHARTS` | Which charts, in which order: `"pace"`, `"sliding"`, `"turning"`, `"offtrack"` | all four |
| `SHOW_THRESHOLDS` | Draw the threshold lines | True |
| `STRIP_SECONDS_BEFORE`, `STRIP_SECONDS_AFTER` | The time window of the strip | 8, 2 |
| `STRIP_HEIGHT` | Height of the strip in pixels | 320 |
| `VIDEO_QUALITY` | How strongly the video is compressed; lower is better and larger | 28 |
| `WRITE_OVERVIEW` | Write the overview picture | True |

`BOX_SMOOTHING` is not built: it belongs to step V7, which the author skipped (section 11).

Colours and fonts stay in the code at first; they can move to the file if the author wants to change them.

`CLAUDE.md` says values that may need tuning live in `settings.py`. A line will be added there: the check video's own settings live in `check_video_settings.py`.

## 8. The sensor data file

`name-sensors.csv`, written by `sensor_file.py` from what `read_sensors` returns:

- Columns: `time_seconds, acceleration_x, acceleration_y, acceleration_z, rotation_x, rotation_y, rotation_z`. Units m/s² and radians per second. The axes are the camera's own, unchanged; which one is forward is written in `settings.py`.
- One row per measurement. The time of a measurement is spread evenly over its block: `block start + n × block length / number of measurements`, where the block length is the distance to the next block (1 second for the last).
- GPS speed is left out **(assumption)**: it is rarely there and the GPX file already holds the GPS data.
- About 150,000 rows and 10 MB for a 13-minute video.

## 9. Speed and the graphics card

- Reading the video for drawing: `read_frames` as now, at 1280 wide and `FRAMES_PER_SECOND`, on the graphics card.
- Writing: a second ffmpeg that takes the drawn pictures and writes H.264, with `h264_nvenc` when `USE_GRAPHICS_CARD` is on, `libx264` otherwise. The sound is copied from the original video in the same step.
- Target **(assumption)**: drawing a check video takes no longer than the video itself. Measured in step V3. If 30 per second is too slow, `FRAMES_PER_SECOND = 5` draws only the pictures the detector saw, which is the fallback.

## 10. Checks

Every new piece gets a check in `tests/`, without the example videos:

- the sensor file: times spread correctly, columns and values as given,
- the detections file: saving and loading gives the same boxes,
- `explain.py`: on made-up boxes and sensor values, the right boxes and events are marked as thrown away, with the right reason; the kept events are the same as the normal detection gives,
- `draw.py`: drawing a made-up picture does not fail and gives a picture of the right size,
- the profile: inside `using_profile`, the threshold values handed to the drawing are the profile's, and the profile's name is handed on,
- the option: without `--check-video`, the events file is byte for byte the same as before.

One check with an example video, skipped when the examples are missing: a short piece of 09-41 gives a check video of the right size and length.

## 11. Order of work

Before step 9 of `TECHNICAL_SPEC.md`, after the profile steps P1 and P2. One commit per step, each ends with something that runs.

- **V1.** Sensor data file, written for every video.
- **V2.** Detections file: save the raw boxes, load them again; `--check-video` runs or reuses the detection.
- **V3.** Check video with kept boxes and the event line. Measure the speed; decide on 30 or 5 pictures per second.
- **V4.** Thrown-away boxes and events, with reasons.
- **V5.** Sensor strip.
- **V6.** Overview picture.
- **V7.** Box smoothing, if the author finds the boxes too jumpy after V3.

**State: V1 to V6 are built. V7 is skipped:** the author watched the check video and found the boxes fine as they are (held between two analysed pictures).

Measured with everything drawn (boxes, events, the strip of four charts), at 30 pictures per second, 1280 pixels wide:

| Video | Length | Time to make | Size |
|---|---|---|---|
| 12-17, from saved detections | 6:27 | 181 s (117 s without the strip) | 195 MB, 1280x1040 |
| GX010183, with its detection pass | 17:08 | 777 s | 500 MB |

So drawing takes under half of the video's length, and a first run with detection about three quarters. The target of section 9 (no longer than the video itself) is met.

## 12. Left to the builder

- Colours, fonts, exact layout of labels.
- How the detections file is laid out inside, as long as it can be read back exactly.
- Video quality setting for the encoder (a sensible default, file size a few hundred MB).
