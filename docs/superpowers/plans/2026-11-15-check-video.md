# Check video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `--check-video` option that writes, per video, a reduced copy with the module's work drawn in: car boxes, the events, a sensor strip with the rules' thresholds, the profile used, plus one overview picture. It is the tool for seeing why the rules decide what they decide.

**Architecture:** Detect once, draw from saved data. The slow detection saves the raw car boxes to `name-detections.json`. A fast second part (`explain.py`) replays the tracker and all rules on those boxes and the sensor data and collects what was kept, what was thrown away and why, and the chart values. `draw.py` draws one picture from that with Pillow, and `check_video.py` pipes the drawn pictures into ffmpeg. The rules are called, never copied, so the pictures show what the rules use, with the profile's values.

**Tech Stack:** Python 3.13 in `.venv`; Pillow (already installed with torchvision) for drawing; ffmpeg from `executables/` for reading and writing video (`h264_nvenc`, or `libx264` without an Nvidia card); `json`, `csv`, `unittest`, `unittest.mock` from the standard library. Nothing is installed.

**Spec:** `CHECK_VIDEO_BUSINESS_SPEC.md` and `CHECK_VIDEO_TECHNICAL_SPEC.md` (steps V1 to V7). Profiles: `TECHNICAL_SPEC.md` section 8, "Driver and car profiles".

## Global Constraints

- Run the checks with `.venv\Scripts\python.exe -m unittest` (`unittest`, not pytest). Test files are `tests/test_<name>.py`.
- **The author runs Git.** Each task ends by giving the author the `git add` and `git commit` commands with a line on what each does. Do not commit or push. Stop after each task.
- The author is learning Python: plain names, small files, comments that say why; explain anything new in one sentence in a comment.
- **Without `--check-video`, the events file and the GPX file must be exactly as before**, and nothing extra is done except writing `name-sensors.csv`.
- **With `--check-video`, the events file must be byte for byte the same as without it.**
- An existing events file is never changed by making a check video.
- **The rules are not copied.** Chart values and thresholds come from the rules' own functions and from `settings`, read at the moment of drawing (so the profile's values apply). Never `from pp_tt_video.settings import NAME`.
- The check video's own settings live in `pp_tt_video/check_video_settings.py`, every one with a comment. Rule thresholds stay in `settings.py` and the profile.
- Output files are named `name-sensors.csv`, `name-detections.json`, `name-check.mp4`, `name-overview.png`, written next to the other outputs (or to `--output-folder`), skipped when they exist unless `--overwrite`.
- The repository is public: no absolute paths from this PC in code, tests or docs.
- Checks must not need the example videos, except where a task says "skipped when the examples are missing".
- Real runs always write to a scratch folder with `--output-folder`, never next to the videos. On `input video files/practice driver` in particular, never run with `--overwrite` in place: its offtrack false alarms would be written into the events files there. A run into a scratch folder touches nothing in that folder and is allowed; ask the author first when it needs a detection pass (about a third of the video's length).

## Review Focus

1. **A run that is interrupted** (Ctrl+C, power, a crash in ffmpeg) leaves a half-written `name-check.mp4` or `name-detections.json`. The next run must not skip it as "already exists". Write to a temporary name and rename only when complete. Tests in Tasks 2 and 4.
2. **A detections file made with other analysis settings** (width, pictures per second, minimum confidence) must not be reused silently; the detection is run again. Test in Task 2.
3. **A video without motion sensor data** (not a GoPro file, or ExifTool fails): no sensor file, which is not a failure; the check video is still made, and its strip says "no sensor data". Tests in Tasks 1 and 6.
4. **A video with another shape** (4:3, or a strip height that makes the total height odd): the encoder needs even sizes. The total height is made even. Test in Task 4.
5. **A video with no other car at all, and moments past the end of the sensor data:** drawing must not fail; the strip shows what there is. Tests in Tasks 3 and 6.

---

### Task 1: The sensor data file (V1)

**Files:**
- Create: `pp_tt_video/sensor_file.py`
- Modify: `pp_tt_video/pipeline.py` (`process_video`), its module docstring
- Test: `tests/test_sensor_file.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `SensorSecond`, `read_sensors`, `SensorError` from `sensors.py`.
- Produces:
  - `sensors_path_for(video_path, output_folder=None) -> Path`: `"x.mp4"` gives `"x-sensors.csv"`, like `events_path_for`.
  - `sensor_rows(sensor_seconds) -> list[tuple]`: one tuple `(time, ax, ay, az, rx, ry, rz)` per measurement. Time of measurement *n* of a block = block start + *n* × block length / number of acceleration measurements; block length = start of the next block − this start, and 1.0 for the last block. Rotation *n* is paired with acceleration *n*; if a block has fewer rotation values, the missing ones are left empty.
  - `write_sensor_file(path, sensor_seconds)`: writes the header `time_seconds,acceleration_x,acceleration_y,acceleration_z,rotation_x,rotation_y,rotation_z` and the rows; times with 4 decimals, values as read.
  - `make_sensor_file(video, output_folder, overwrite, read=read_sensors) -> tuple[bool, str]` in `pipeline.py`: checks for an existing file **before** reading (reading takes 5 seconds); messages `"sensor data written to <name>"`, `"sensor file already exists, skipped"`, `"no motion sensor data in this video"` (ok is True), or the `SensorError` text (ok is False).
  - `process_video` calls it after the GPX step, also when `with_events` is False, and adds its message.

- [ ] **Step 1: Write the failing tests**
  - `tests/test_sensor_file.py`:
    - `test_path`: `sensors_path_for("a/b/x.MP4")` → `a/b/x-sensors.csv`; with `output_folder="out"` → `out/x-sensors.csv`.
    - `test_times_are_spread_over_the_block`: two blocks starting at 0.0 and 1.0, each with 4 measurements → times `0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75`.
    - `test_block_length_follows_the_next_block`: blocks at 0.0 and 2.0 with 4 measurements → first block's times `0.0, 0.5, 1.0, 1.5`.
    - `test_values_are_kept_as_read`: one measurement `(-9.8, 1.5, 0.25)` / `(0.1, -0.2, 0.3)` → the row holds exactly those six numbers.
    - `test_written_file_reads_back`: write, read with `csv.reader` → header as above, row count = number of measurements.
  - `tests/test_pipeline.py`, class `SensorFileInPipelineTest`, using `make_sensor_file` with a stand-in `read`:
    - `test_writes_the_file`, `test_existing_file_is_skipped_without_reading` (the stand-in raises if called), `test_video_without_sensor_data_is_not_a_failure` (stand-in returns `[]` → ok True, no file), `test_sensor_error_is_a_failure`.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_sensor_file tests.test_pipeline -v`
Expected: `No module named 'pp_tt_video.sensor_file'`.

- [ ] **Step 3: Write `sensor_file.py` and the pipeline change.** Write the CSV to `<name>.part` and rename it when complete.

- [ ] **Step 4: Run all checks, then try it for real**

Run: `.venv\Scripts\python.exe -m unittest` — Expected: all pass.
Run: `.venv\Scripts\python.exe -m pp_tt_video "input video files\stronger driver" --gps-only --output-folder "<a scratch folder>"` — Expected: `GX010181-sensors.csv` of about 8 MB with about 120,000 rows; show the author its first lines.

- [ ] **Step 5: Update `BUSINESS_SPEC.md` section 6** with a short "6.3 Sensor data file" (what it holds, that it is always written), **and give the author the commit commands**

```bash
git add pp_tt_video/sensor_file.py pp_tt_video/pipeline.py tests/test_sensor_file.py tests/test_pipeline.py BUSINESS_SPEC.md
git commit -m "Write the motion sensor data to a CSV file per video (step V1)"
```

---

### Task 2: Save the detections and reuse them (V2)

**Files:**
- Create: `pp_tt_video/detections_file.py`
- Modify: `pp_tt_video/detect_cars.py` (`CarDetector`), `pp_tt_video/detect_events.py`, `pp_tt_video/pipeline.py`, `pp_tt_video/__main__.py`
- Test: `tests/test_detections_file.py`, `tests/test_detect_events.py` (new), `tests/test_pipeline.py`

**Interfaces:**
- Produces:
  - `detections_file.py`:
    - `@dataclass class Detections: analysis_width: int; picture_height: int; frames_per_second: float; min_confidence: float; pictures: list` where `pictures` is a list of `(time_seconds, [CarBox, ...])` with the **raw** vehicle boxes of each analysed picture (before `keep_car_boxes`).
    - `detections_path_for(video_path, output_folder=None) -> Path` (`x-detections.json`).
    - `save_detections(path, detections)`: writes to `<name>.part`, then renames.
    - `load_detections(path) -> Detections`; raises `DetectionsError` for a file that cannot be read.
    - `fits_settings(detections) -> bool`: True when `analysis_width`, `frames_per_second` and `min_confidence` equal the current `settings.ANALYSIS_WIDTH`, `ANALYSIS_FRAMES_PER_SECOND`, `MIN_DETECTION_CONFIDENCE`.
  - `detect_cars.py`: `CarDetector.detect_raw(frames) -> list[list[CarBox]]` (vehicle boxes, not filtered). `detect(frames)` becomes `[keep_car_boxes(boxes, frame.width) for ...]` over `detect_raw` and returns exactly what it returned before.
  - `detect_events.py`:
    - `detect_boxes(video_path, detector, on_progress=None) -> Detections`: the slow pass.
    - `tracks_from_detections(detections) -> tuple[list, int]`: applies `keep_car_boxes(boxes, detections.analysis_width)` per picture, feeds a `Tracker`, returns `(tracks, picture_height)`.
    - `sensor_stretches(sensor_seconds, duration_seconds) -> tuple[list, list]`: what `detect_from_sensors` does after reading; `detect_from_sensors` calls it.
    - `timeline_from_detections(video_path, detections) -> list[Event]`.
    - `track_cars` and `detect_timeline` stay, built from the new functions, with unchanged results.
  - `pipeline.py`:
    - `EventsMaker.detections_for(video, output_folder, overwrite, on_progress, keep_file) -> Detections`: with `keep_file`, loads `name-detections.json` when it exists, fits the settings and `overwrite` is False; otherwise runs `detect_boxes` and, with `keep_file`, saves it. It remembers the detections of the last video, so the events step and the check video step of one video share one detection pass.
    - `make_events_file(..., profile=BUILT_IN, keep_detections=False)` uses `detections_for` and `timeline_from_detections`.
    - `process_video(..., check_video=False)`, `process_videos(..., check_video=False)`.
  - `__main__.py`: `--check-video`, help `"also write a check video that shows what the module saw and decided"`. Together with `--gps-only` the parser stops with an error (`parser.error(...)`).
  - In this task `--check-video` only saves and reuses the detections; the video comes in Task 4. When the events file exists and is skipped, the detections are still made if their file is missing.

- [ ] **Step 0: Make the baseline, before changing any code.** Run the module on the 12-17 example into a scratch folder `baseline` (about 2 minutes): `.venv\Scripts\python.exe -m pp_tt_video "example video  and output file\RaceBox Track Sessionon 30-05-2026 12-17.MP4" --output-folder "<scratch>\baseline"`. Keep its events file: Step 4 compares against it. This is the only proof that splitting `detect` into `detect_raw` and the filter changed nothing.

- [ ] **Step 1: Write the failing tests**
  - `tests/test_detections_file.py`: `test_path`; `test_save_and_load_give_the_same_boxes` (two pictures, one with two boxes with awkward floats such as `0.1 + 0.2`, one empty → equal after loading, floats exactly equal); `test_fits_settings` (true as made; false after patching `settings.ANALYSIS_WIDTH`); `test_broken_file_is_refused`; `test_no_part_file_is_left_behind`.
  - `tests/test_detect_events.py`:
    - `test_tracks_from_detections_match_feeding_the_tracker`: hand-made detections of one car growing over 10 pictures plus one too-wide box → the tracks equal those of a `Tracker` fed with the same boxes after `keep_car_boxes`.
    - `test_no_cars_gives_no_tracks`: pictures without boxes → `([], picture_height)`.
  - `tests/test_pipeline.py`: update `ProfileInPipelineTest` to patch `detect_boxes` and `timeline_from_detections` instead of `detect_timeline` (the fake `timeline_from_detections` records the pace value). New class `DetectionsInPipelineTest` with a fake `detect_boxes` that counts its calls and returns small real `Detections`:
    - `test_without_the_option_nothing_is_saved`: no `-detections.json`.
    - `test_with_the_option_the_detections_are_saved`.
    - `test_saved_detections_are_reused`: second run with `--overwrite` off and the events file removed → `detect_boxes` not called again.
    - `test_detections_from_other_settings_are_not_reused`: save, patch `ANALYSIS_WIDTH`, run → `detect_boxes` called.
    - `test_overwrite_detects_again`.
    - `test_events_file_is_the_same_with_and_without_the_option`: let the real `timeline_from_detections` run on the fake detections with `read_video_info` and `read_sensors` patched; compare the two events files' bytes.
  - `tests/test_detect_cars.py` (skipped without libraries and example): `detect` and `keep_car_boxes` over `detect_raw` give the same boxes on one example picture.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_detections_file tests.test_detect_events tests.test_pipeline -v`
Expected: `No module named 'pp_tt_video.detections_file'`.

- [ ] **Step 3: Write the code.** JSON layout: `{"analysis_width", "picture_height", "frames_per_second", "min_confidence", "pictures": [{"time": t, "boxes": [[left, top, right, bottom, confidence], ...]}]}`. Python's `json` writes floats so that they read back exactly.

- [ ] **Step 4: Run all checks, then prove the results did not change**

Run: `.venv\Scripts\python.exe -m unittest` — Expected: all pass.
Run the module on the 12-17 example twice more into two further scratch folders, once without and once with `--check-video`. Compare both events files with the baseline of Step 0, using `fc`. Expected: all three identical; `...-detections.json` exists in the `--check-video` folder and is about 1 MB.

- [ ] **Step 5: Give the author the commit commands**

```bash
git add pp_tt_video/detections_file.py pp_tt_video/detect_cars.py pp_tt_video/detect_events.py pp_tt_video/pipeline.py pp_tt_video/__main__.py tests/test_detections_file.py tests/test_detect_events.py tests/test_pipeline.py tests/test_detect_cars.py
git commit -m "Save the car detections and reuse them (step V2)"
```

---

### Task 3: Explain what the rules did

**Files:**
- Create: `pp_tt_video/explain.py`
- Test: `tests/test_explain.py`

**Interfaces:**
- Consumes: `Detections`, `tracks_from_detections`' building blocks (`keep_car_boxes`, `drop_double_boxes`, `Tracker`), `events_of_track`, `sensor_stretches`, `combine_stretches`, `outside_pace`, `build_timeline`, `load_event_types`.
- Produces:
  - `@dataclass class ShownBox: box: CarBox; track_number: int | None; height_part: float; state: str; reason: str` — `height_part` is the height **as the car rule sees it**: `events_of_track` runs `smooth()` over a track's heights (box height / picture height) before it compares them, so `explain` runs the same `smooth()` over the same list and gives each box its smoothed value. A single oversized box must not show as "passing" when the rule never saw it that way. `state` is `"far"`, `"close"` or `"passing"`: `height_part` against `settings.CLOSE_CAR_HEIGHT` and `settings.PASSING_CAR_HEIGHT`. For dropped boxes that belong to no track ("too wide", "double") `height_part` is the box's own height and `state` is `"far"`; `reason` is `""` for a kept box, else `"too wide"`, `"double"` or `"never sure enough"`.
  - `@dataclass class PictureBoxes: time_seconds: float; kept: list; dropped: list`
  - `@dataclass class DroppedStretch: stretch: Stretch; reason: str` — reason `"outside the part at pace"`.
  - `@dataclass class Explanation: pictures: list; tracks: list; timeline: list; kept_stretches: list; dropped_stretches: list; session_parts: list; duration_seconds: float; sensor_seconds: list` (`sensor_seconds` is `[]` when the video has none).
  - `explain(detections, sensor_seconds, duration_seconds) -> Explanation`.
  - Track numbers start at 1, in order of first appearance. A box belongs to the track whose sighting holds that same box object.
  - `boxes_at(explanation, time_seconds) -> PictureBoxes | None`: the last analysed picture at or before `time_seconds`, if it is no older than one analysis step (`1 / frames_per_second`); otherwise None.
  - `labels_at(explanation, time_seconds) -> tuple[str, ...]` (from the timeline) and `dropped_at(explanation, time_seconds) -> list[DroppedStretch]`.

- [ ] **Step 1: Write the failing tests** in `tests/test_explain.py`, all on hand-made `Detections` and made-up sensor seconds (reuse the `driving(...)` helper idea from `tests/test_make_profile.py`; move it to `tests/helpers.py` so both files use it).
  - `test_kept_box_has_its_track_number_and_height`: one car, 5 pictures, box height 72 in a 720 picture → every picture has one kept box, `track_number == 1`, `height_part == 0.1`, `reason == ""`.
  - `test_state_follows_the_car_heights`: three cars far apart in the picture, each with a steady height over 5 pictures: 36, 50 and 90 of 720 → `"far"`, `"close"`, `"passing"`; and with `using_profile` setting `CLOSE_CAR_HEIGHT` to 0.2 the 50-high car is `"far"`.
  - `test_one_oversized_box_does_not_change_the_state`: one car with heights 36, 36, 200, 36, 36 → the middle box has `height_part == 0.05` and state `"far"`, as the rule sees it after smoothing.
  - `test_too_wide_box_is_dropped_with_reason`: a box 700 wide in a 1280 picture → in `dropped`, reason `"too wide"`, not in `kept`.
  - `test_double_box_is_dropped_with_reason`: a box inside another → the less sure one is `"double"`.
  - `test_unsure_track_is_dropped_with_reason`: a car whose confidence never reaches `CAR_MIN_CONFIDENCE` → all its boxes `"never sure enough"`.
  - `test_two_cars_get_two_numbers`.
  - `test_event_outside_pace_is_dropped_with_reason`: sensor data that is gentle throughout plus a car track that makes an `overtaking` → the stretch is in `dropped_stretches` with the reason, the timeline has no `overtaking`.
  - `test_timeline_equals_the_normal_detection`: for one made-up case with pace, a car event and a slide, `explanation.timeline == timeline_from_detections(...)` with `read_video_info` and `read_sensors` patched to the same data.
  - `test_no_cars_and_no_sensors`: empty pictures and `sensor_seconds=[]` → no boxes, timeline is one `clear` event, nothing fails.
  - `test_boxes_at`: pictures at 0.0 and 0.2 (5 per second) → `boxes_at(e, 0.1)` is the 0.0 picture; `boxes_at(e, 0.39)` the 0.2 one; `boxes_at(e, 5.0)` is None.

- [ ] **Step 2: Run them to see them fail** — Expected: `No module named 'pp_tt_video.explain'`.

- [ ] **Step 3: Write `explain.py`.** Where a rule keeps a decision to itself (a track skipped for low confidence), read it from the same condition the rule uses (`track.best_confidence < settings.CAR_MIN_CONFIDENCE`); do not change the rule.

- [ ] **Step 4: Run all checks** — `.venv\Scripts\python.exe -m unittest`, all pass.

- [ ] **Step 5: Give the author the commit commands**

```bash
git add pp_tt_video/explain.py tests/test_explain.py tests/helpers.py tests/test_make_profile.py
git commit -m "Collect what the rules kept, dropped and why"
```

---

### Task 4: The check video with boxes and events (V3)

**Files:**
- Create: `pp_tt_video/check_video_settings.py`, `pp_tt_video/draw.py`, `pp_tt_video/check_video.py`
- Modify: `pp_tt_video/video.py` (writing), `pp_tt_video/pipeline.py`
- Test: `tests/test_draw.py`, `tests/test_check_video.py`, `tests/test_video.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `Explanation`, `boxes_at`, `labels_at` (Task 3); `Detections`, `detections_for` (Task 2); `read_frames`, `read_video_info`, `analysis_size`.
- Produces:
  - `check_video_settings.py` with, each under a comment that says what it does and which values it takes: `FRAMES_PER_SECOND = 30`, `KEEP_SOUND = True`, `SHOW_KEPT_BOXES = True`, `SHOW_BOX_DETAILS = True`, `SHOW_EVENTS = True`. (Later tasks add theirs.)
  - `video.py`: `class VideoWriter` used as `with VideoWriter(path, width, height, frames_per_second, sound_from=None) as writer: writer.write(pixels)`. It starts ffmpeg reading raw `rgb24` pictures from its input pipe, encoding H.264 (`h264_nvenc` when `settings.USE_GRAPHICS_CARD`, else `libx264`), `-pix_fmt yuv420p`; with `sound_from`, the sound of that file is copied (`-map 0:v -map 1:a? -c:a copy -shortest`). It writes to `<name>.part.mp4` and renames on a clean end; on an error it removes the part file and raises `VideoError` with ffmpeg's message.
  - `draw.py`:
    - `picture_size(video_width, video_height, strip_height) -> tuple[int, int]`: `(width, video_height + strip_height)` with the total made even.
    - `draw_picture(image, time_seconds, explanation, profile_name) -> PIL.Image`: returns a new image of `picture_size`; draws, as the settings say, the kept boxes (colour by state; label `"car 3  0.87  h 0.11"` when `SHOW_BOX_DETAILS`), the event line across the top (`", ".join(labels)`), and in the top right corner `f"profile: {profile_name}"` and the time as `mm:ss`. The strip area is left dark (Task 6 fills it).
  - `check_video.py`:
    - `check_video_path_for(video_path, output_folder=None) -> Path` (`x-check.mp4`).
    - `write_check_video(video_path, output_path, explanation, profile_name, on_progress=None)`.
  - `pipeline.py`: `make_check_video(video, output_folder, overwrite, profile, events_maker, on_progress) -> tuple[bool, str]`: skips when the file exists; gets the detections with `detections_for(..., keep_file=True)`; reads the sensors (an empty list on `SensorError`); inside `with using_profile(profile):` calls `explain` and `write_check_video` with `profile.name`. `process_video` calls it when `check_video` is True, after the events step.

- [ ] **Step 1: Write the failing tests**
  - `tests/test_draw.py`: `test_picture_size_is_even` (`(1280, 720, 240)` → `(1280, 960)`; `(1280, 720, 241)` → `(1280, 962)`; `(1280, 960, 240)` → `(1280, 1200)`); `test_drawn_picture_has_the_right_size`; `test_kept_box_is_drawn` (a black 1280x720 image with one kept box at (100,100)-(300,250): the returned image has non-black pixels on that box's edge and stays black in the box's middle); `test_nothing_drawn_when_switched_off` (patch `SHOW_KEPT_BOXES`, `SHOW_EVENTS` to False and compare with a drawing of an explanation without boxes); `test_time_without_boxes_does_not_fail`.
  - `tests/test_video.py`, skipped when ffmpeg is missing: `test_written_video_reads_back`: write 10 pictures of 64x48 at 5 per second with `libx264` (patch `USE_GRAPHICS_CARD` to False) into a temporary folder → `read_video_info` gives 64x48 and about 2 seconds; no `.part` file remains. `test_failed_write_leaves_no_file`: an odd width (65) makes the encoder fail → `VideoError`, no output file and no part file.
  - `tests/test_check_video.py`, skipped when ffmpeg is missing: make a 2-second 64x48 source video with `VideoWriter`, a small explanation, run `write_check_video` → the output is 64 wide, `picture_size` high, about 2 seconds long.
  - `tests/test_pipeline.py`: `test_check_video_is_skipped_when_it_exists`; `test_check_video_uses_the_profile` (fake `write_check_video` records `profile_name` and `settings.PACE_MIN_EFFORT` → the folder profile's name and value).

- [ ] **Step 2: Run them to see them fail** — Expected: `No module named 'pp_tt_video.draw'`.

- [ ] **Step 3: Write the code.** Fonts: `ImageFont.load_default(size=...)` (part of Pillow, no font file needed). Turn a `Frame` into an image with `Image.frombytes("RGB", (width, height), frame.pixels)` and back with `image.tobytes()`.

- [ ] **Step 4: Run all checks; make a real check video and measure**

Run: `.venv\Scripts\python.exe -m unittest` — all pass.
Run the module with `--check-video` on the 12-17 example into the scratch folder from Task 2 (its detections are saved, so only the drawing runs). Note the time taken and the file size. Expected: no longer than the video (6:27) and a few hundred MB. If it takes longer, tell the author and propose `FRAMES_PER_SECOND = 5`. Show the author where the file is; the author watches it and says whether the boxes are too jumpy (decides Task 8).

- [ ] **Step 5: Add `--check-video` to `CLAUDE.md` (Practical details), and give the author the commit commands**

```bash
git add pp_tt_video/check_video_settings.py pp_tt_video/draw.py pp_tt_video/check_video.py pp_tt_video/video.py pp_tt_video/pipeline.py tests/test_draw.py tests/test_check_video.py tests/test_video.py tests/test_pipeline.py CLAUDE.md
git commit -m "Write a check video with car boxes and events (step V3)"
```

---

### Task 5: Show what was thrown away (V4)

**Files:**
- Modify: `pp_tt_video/check_video_settings.py`, `pp_tt_video/draw.py`
- Test: `tests/test_draw.py`

**Interfaces:**
- Consumes: `PictureBoxes.dropped`, `dropped_at` (Task 3).
- Produces: settings `SHOW_DROPPED_BOXES = True`, `SHOW_DROPPED_EVENTS = True`. `draw_picture` draws dropped boxes thin and grey with their reason as label, and under the event line a second, grey line such as `"dropped: sliding (outside the part at pace)"`.

- [ ] **Step 1: Write the failing tests**: `test_dropped_box_is_drawn_grey` (the edge pixels of a dropped box are grey: red, green and blue equal; a kept box's are not); `test_dropped_boxes_can_be_switched_off`; `test_dropped_event_line_is_drawn` (the picture differs from one drawn without dropped stretches, only in the top band); `test_dropped_events_can_be_switched_off`.
- [ ] **Step 2: Run them to see them fail** — Expected: failures on the grey pixels.
- [ ] **Step 3: Write the code.**
- [ ] **Step 4: Run all checks; redraw the 12-17 check video** with `--overwrite` on the check video only (delete `...-check.mp4` in the scratch folder and run again; the detections are reused). Expected: the too-wide cockpit boxes, if any, show grey; events in the pit lane show as dropped. Show the author.
- [ ] **Step 5: Give the author the commit commands**

```bash
git add pp_tt_video/check_video_settings.py pp_tt_video/draw.py tests/test_draw.py
git commit -m "Show dropped boxes and dropped events on the check video (step V4)"
```

---

### Task 6: The sensor strip (V5)

**Files:**
- Create: `pp_tt_video/charts.py`
- Modify: `pp_tt_video/offtrack.py` (`shake_over_time` gets an axis), `pp_tt_video/explain.py`, `pp_tt_video/draw.py`, `pp_tt_video/check_video_settings.py`
- Test: `tests/test_charts.py`, `tests/test_draw.py`, `tests/test_motion_events.py`

**Interfaces:**
- Produces:
  - `offtrack.shake_over_time(sensor_seconds, axis=None)`: `axis=None` means `settings.ACCELERATION_AXIS_DOWN`, so the rule's result is unchanged.
  - `charts.py`:
    - `@dataclass class Line: name: str; times: list; values: list; from_rule: bool` — `from_rule` False marks a line shown for information only.
    - `@dataclass class Chart: title: str; lines: list; thresholds: list; marks: list` — `thresholds` is a list of `(label, value)`, `marks` a list of times.
    - `pace_chart(sensor_seconds) -> Chart`: lines "force" (`forward_force_per_second`) and "effort" (`effort_per_second`); thresholds `("pace", settings.PACE_MIN_EFFORT)`, `("hard", settings.PACE_HARD_FORCE)`.
    - `sliding_chart(sensor_seconds) -> Chart`: line "cornering force" from `cornering_and_turning`; thresholds `("min", settings.SLIDE_MIN_CORNERING_FORCE)`, `("-min", -settings.SLIDE_MIN_CORNERING_FORCE)`; marks = `find_catch_times(...)`.
    - `turning_chart(sensor_seconds) -> Chart`: line "turning" from `cornering_and_turning`; thresholds `("min", settings.SLIDE_MIN_TURNING_BEFORE)`, `("-min", -settings.SLIDE_MIN_TURNING_BEFORE)`; the same marks. It is a chart of its own because turning is in radians per second (about ±0.5) and the cornering force in m/s² (about ±11): on one scale the turning line would be flat.
    - `offtrack_chart(sensor_seconds) -> Chart`: line "shake" (the rule's, down axis) and two information lines "shake sideways" and "shake forward" (`from_rule=False`); threshold `("min", settings.OFFTRACK_MIN_SHAKE)`. The two extra lines were added after step P2: the false offtracks on the son's footage shake up and down only, the real ones in every direction, and the rework of the rule needs to see that.
    - `CHARTS = {"pace": pace_chart, "sliding": sliding_chart, "turning": turning_chart, "offtrack": offtrack_chart}`.
    - `window(line, start, end) -> tuple[list, list]`: the times and values inside a time window. It is called for every line of every picture, so it finds the two ends with `bisect` (a standard-library search in a sorted list) and does not walk the whole list.
  - `explain.py`: `Explanation` gets `charts: dict` (name → Chart), built inside `explain`, so inside `using_profile`; `{}` without sensor data.
  - Settings: `SHOW_STRIP = True`, `STRIP_CHARTS = ["pace", "sliding", "turning", "offtrack"]`, `SHOW_THRESHOLDS = True`, `STRIP_SECONDS_BEFORE = 8`, `STRIP_SECONDS_AFTER = 2`, `STRIP_HEIGHT = 320` (80 pixels per chart).
  - `draw.py`: `draw_strip(image, time_seconds, explanation)`: one row per chart named in `STRIP_CHARTS`; each row has one fixed scale for the whole video, so a value means the same height at every moment: from its 99.5th percentile over the whole video or twice its largest threshold, whichever is larger; values beyond the scale are drawn at the edge of the row. (A scale to the largest value would let one spike, such as the forward shake of 43 in 09-41, flatten everything else.) Judge the scale on the first real output and tell the author if it reads badly; rule lines solid, information lines thin; threshold lines dashed with their label and value; a vertical line at "now"; marks as small ticks. Without charts it writes "no sensor data". With `SHOW_STRIP` False the picture has no strip (`picture_size` with strip height 0).

- [ ] **Step 1: Write the failing tests**
  - `tests/test_charts.py`: `test_pace_chart_thresholds_follow_the_profile` (inside `using_profile` with `PACE_MIN_EFFORT = 0.5` the threshold value is 0.5; outside, the built-in value); `test_offtrack_chart_has_one_rule_line_and_two_information_lines`; `test_offtrack_rule_line_equals_the_rule` (its values equal `shake_over_time(sensor_seconds)`); `test_sliding_marks_are_the_catch_times`; `test_window` (times 0..9, window 2.5 to 5 → 3, 4, 5).
  - `tests/test_motion_events.py`: `test_shake_axis`: made-up data that shakes only sideways → `shake_over_time(data)` is 0 everywhere, `shake_over_time(data, settings.ACCELERATION_AXIS_SIDEWAYS)` is not.
  - `tests/test_draw.py`: `test_strip_is_drawn_below_the_picture` (non-dark pixels below row 720); `test_threshold_line_is_at_the_profile_value` (draw twice, built-in and with a profile that halves `OFFTRACK_MIN_SHAKE`: the strips differ); `test_no_sensor_data_says_so` (does not fail, strip not empty); `test_time_past_the_sensor_data_does_not_fail`; `test_strip_can_be_switched_off` (picture height equals the video height).

- [ ] **Step 2: Run them to see them fail** — Expected: `No module named 'pp_tt_video.charts'`.
- [ ] **Step 3: Write the code.**
- [ ] **Step 4: Run all checks; redraw the 12-17 check video.** Measure the drawing time again (the strip adds lines per picture). Show the author. Also update `CHECK_VIDEO_TECHNICAL_SPEC.md` 6.3 and section 7 with the turning chart, the two information lines and the strip height.

- [ ] **Step 4b: Make the check video the whole thing was built for.** Ask the author, then run `--check-video` on `input video files\practice driver\GX010183.MP4` into a scratch folder (detection about 6 minutes, then drawing; nothing in the video's own folder is touched, and its `profile.toml` applies). This is the video in which the author confirmed all 19 offtracks as false. Expected: at the 19 moments the "shake" line crosses its threshold while "shake sideways" and "shake forward" stay low. Give the author the file and the list of moments. This is the tool for the offtrack rework.
- [ ] **Step 5: Give the author the commit commands**

```bash
git add pp_tt_video/charts.py pp_tt_video/offtrack.py pp_tt_video/explain.py pp_tt_video/draw.py pp_tt_video/check_video_settings.py tests/test_charts.py tests/test_draw.py tests/test_motion_events.py CHECK_VIDEO_TECHNICAL_SPEC.md
git commit -m "Draw the sensor strip with the rules' thresholds (step V5)"
```

---

### Task 7: The overview picture (V6)

**Files:**
- Create: `pp_tt_video/overview.py`
- Modify: `pp_tt_video/check_video_settings.py`, `pp_tt_video/pipeline.py`
- Test: `tests/test_overview.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `Explanation` with `charts`, `session_parts`, `kept_stretches`, `dropped_stretches`, `tracks`.
- Produces:
  - `overview_path_for(video_path, output_folder=None) -> Path` (`x-overview.png`).
  - `draw_overview(explanation, profile_name, video_name) -> PIL.Image`: 2000 pixels wide, time along the bottom with a tick per minute. From the top: a title line (video name, profile name); the pace effort with its two thresholds and the session parts as coloured bands behind it, with a legend; one row per event label that occurs, kept stretches as filled bars, dropped ones as outlines; one row of bars for the tracks.
  - `write_overview(path, explanation, profile_name, video_name)`.
  - Setting `WRITE_OVERVIEW = True`.
  - `pipeline.make_check_video` also writes the overview (skipped when it exists; made even when the check video itself already exists).

- [ ] **Step 1: Write the failing tests**: `test_path`; `test_size` (2000 wide); `test_dropped_and_kept_bars_differ` (two overviews of the same stretch, once kept, once dropped, differ); `test_no_sensor_data_does_not_fail`; `test_very_short_video_does_not_fail` (5 seconds); in `test_pipeline.py`: `test_overview_is_written_with_the_check_video`, `test_overview_can_be_switched_off`.
- [ ] **Step 2: Run them to see them fail** — Expected: `No module named 'pp_tt_video.overview'`.
- [ ] **Step 3: Write the code.**
- [ ] **Step 4: Run all checks; make the overviews of the three examples and of GX010181** (detections of 12-17 are saved; for the others this needs their detection, about 12 minutes together: ask the author first). Then make the overview of one practice-driver video **from the sensors only** by calling `explain` with empty detections in a throwaway script, to show the author the whole-video picture of the false offtracks without running the detection there.
- [ ] **Step 5: Update the documents and give the author the commit commands.** `CHECK_VIDEO_TECHNICAL_SPEC.md`: mark V1 to V6 as built, with the measured drawing time and file size. `CLAUDE.md`: progress (check video done; next: the offtrack rework) and the check video in Practical details.

```bash
git add pp_tt_video/overview.py pp_tt_video/check_video_settings.py pp_tt_video/pipeline.py tests/test_overview.py tests/test_pipeline.py CHECK_VIDEO_TECHNICAL_SPEC.md CLAUDE.md
git commit -m "Write an overview picture of the whole video (step V6)"
```

---

### Task 8: Box smoothing (V7), only if the author asks for it

Decided by the author after watching the check video of Task 4: "look first, smooth if needed". Skip this task when the boxes look fine.

**Files:**
- Modify: `pp_tt_video/explain.py`, `pp_tt_video/check_video_settings.py`
- Test: `tests/test_explain.py`

**Interfaces:**
- Produces: setting `BOX_SMOOTHING = "hold"` (`"hold"` or `"slide"`). With `"slide"`, `boxes_at` moves each kept box evenly between its position in the last analysed picture and in the next one, for boxes of the same track in both; a box with no partner in the next picture is held.

- [ ] **Step 1: Write the failing tests**: `test_slide_moves_the_box_halfway` (a track at left 100 at 0.0 and left 200 at 0.2 → at 0.1 the box's left is 150); `test_hold_keeps_the_box` (same data, `"hold"` → 100); `test_slide_holds_a_box_without_a_next_sighting`; `test_unknown_value_is_refused` (a clear `ValueError` naming the setting).
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Write the code.**
- [ ] **Step 4: Run all checks; redraw one check video with `"slide"`** and show the author.
- [ ] **Step 5: Give the author the commit commands**

```bash
git add pp_tt_video/explain.py pp_tt_video/check_video_settings.py tests/test_explain.py
git commit -m "Move the boxes smoothly between analysed pictures (step V7)"
```
