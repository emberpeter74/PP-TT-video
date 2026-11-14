# Check video: technical specification

Status: draft for the author's approval. Items marked **(assumption)** are the assistant's calls; the author can correct them.

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
| `check_video.py` | Reads the video, has every picture drawn, writes the check video; draws the overview picture |

Changes to existing files, kept as small as possible:

- `detect_cars.py`: `CarDetector.detect` can also return the raw boxes (before `keep_car_boxes`). The boxes it returns for detection stay exactly the same.
- `detect_events.py`: the detection pass can hand the raw boxes to a saver. The timeline it returns stays exactly the same.
- `pipeline.py` and `__main__.py`: the new option, and writing the sensor file.
- `video.py`: may get a way to write pictures to ffmpeg (now it only reads).

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
| Sliding | cornering force; turning rate; marks at catch moments | `±SLIDE_MIN_CORNERING_FORCE`, `SLIDE_MIN_TURNING_BEFORE` | `cornering_and_turning`, `find_catch_times` |
| Offtrack | shake | `OFFTRACK_MIN_SHAKE` | `shake_over_time` |

### 6.4 Overview picture

One PNG, drawn with Pillow, about 2000 pixels wide, time along the bottom:

- pace effort per second with `PACE_MIN_EFFORT` and `PACE_HARD_FORCE`, and the runs that were too short (`PACE_MIN_SECONDS`) marked,
- the session parts from `detect_session` as coloured bands,
- one row per event type: kept events as filled bars, thrown-away ones as outlines,
- one row of bars for the tracked cars.

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
| `STRIP_CHARTS` | Which charts, in which order: `"pace"`, `"sliding"`, `"offtrack"` | all three |
| `SHOW_THRESHOLDS` | Draw the threshold lines | True |
| `STRIP_SECONDS_BEFORE`, `STRIP_SECONDS_AFTER` | The time window of the strip | 8, 2 |
| `STRIP_HEIGHT` | Height of the strip in pixels | 240 |
| `WRITE_OVERVIEW` | Write the overview picture | True |

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
- the option: without `--check-video`, the events file is byte for byte the same as before.

One check with an example video, skipped when the examples are missing: a short piece of 09-41 gives a check video of the right size and length.

## 11. Order of work

Before step 9 of `TECHNICAL_SPEC.md`. One commit per step, each ends with something that runs.

- **V1.** Sensor data file, written for every video.
- **V2.** Detections file: save the raw boxes, load them again; `--check-video` runs or reuses the detection.
- **V3.** Check video with kept boxes and the event line. Measure the speed; decide on 30 or 5 pictures per second.
- **V4.** Thrown-away boxes and events, with reasons.
- **V5.** Sensor strip.
- **V6.** Overview picture.
- **V7.** Box smoothing, if the author finds the boxes too jumpy after V3.

## 12. Left to the builder

- Colours, fonts, exact layout of labels.
- How the detections file is laid out inside, as long as it can be read back exactly.
- Video quality setting for the encoder (a sensible default, file size a few hundred MB).
