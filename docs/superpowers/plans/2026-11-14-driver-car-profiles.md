# Driver and car profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the module judge each driver-and-car combination on its own scale: a profile file replaces some threshold values in `settings` while that driver's videos are processed, and a `make_profile` command writes such a file from a folder of the driver's videos.

**Architecture:** Approach A from the spec. A new `pp_tt_video/profile.py` finds, reads and applies a profile; applying means overwriting names in the `settings` module inside a `with using_profile(...)` block and putting the built-in values back afterwards. The rules are not touched. `pipeline.py` wraps the detection of each video in that block. A new `pp_tt_video/make_profile.py` measures the driver from the motion sensors and writes the file.

**Tech Stack:** Python 3.13 in `.venv`, standard library only (`tomllib`, `contextlib`, `argparse`, `unittest`, `unittest.mock`). Nothing is installed.

**Spec:** `BUSINESS_SPEC.md` section 3, "Driver and car profile"; `TECHNICAL_SPEC.md` section 8, "Driver and car profiles"; order of work in `TECHNICAL_SPEC.md` section 13 (steps P1 and P2). The check video (V1 to V7) is a separate plan.

## Global Constraints

- Run the checks with `.venv\Scripts\python.exe -m unittest`. The project uses `unittest`, not pytest. Test files are `tests/test_<name>.py`, classes derive from `unittest.TestCase`.
- **The author runs Git.** Each task ends by giving the author the `git add` and `git commit` commands with one line on what each does. Do not commit or push yourself.
- The author is learning Python: plain names, small files, comments that say why. Explain anything new (a context manager, `tomllib`) in a comment in one sentence.
- Values that may need tuning live in `pp_tt_video/settings.py`, never in the logic.
- The repository is public: no absolute paths from this PC in code, tests or docs.
- Rules must keep reading `settings.NAME` at the moment they run. Never `from pp_tt_video.settings import NAME`, never a setting as a function's default value.
- **Without a profile, every events file must come out exactly as before.**
- Ask before installing anything. Nothing in this plan needs an install.

## Review Focus

1. **A profile file saved by Windows Notepad starts with an invisible "BOM" mark**, which `tomllib` rejects. The profile must still load. Test in Task 1.
2. **A typo in a profile** (`PACE_MIN_EFORT = 0.5`, or `PACE_MIN_EFFORT = "low"`) must stop that video with a message naming the file and the name. The rest of the run goes on, and the GPX file is still written. Tests in Tasks 1 and 3.
3. **One run over two folders, one with `profile.toml` and one without:** the second folder's videos must get the built-in values, not the first folder's. Test in Task 3.
4. **`--profile son` when `profiles/son.toml` does not exist** must say which file it looked for. Test in Task 2.
5. **`make_profile` on a folder with no usable sensor data, or with a `profile.toml` already in it,** must write nothing and say why. Test in Task 5.

---

### Task 1: Reading and applying a profile

**Files:**
- Create: `pp_tt_video/profile.py`
- Test: `tests/test_profile.py`

**Interfaces:**
- Produces:
  - `PROFILE_VALUES: dict[str, str]`: every name a profile may set, mapped to what it depends on. Exactly these keys and values:
    `"PACE_MIN_EFFORT": "driver braking"`, `"PACE_HARD_FORCE": "driver braking"`, `"SLIDE_MIN_CORNERING_FORCE": "driver cornering"`, `"SESSION_TRACK_CORNER_FORCE": "driver cornering"`, `"OFFTRACK_MIN_SHAKE": "car"`, `"STANDSTILL_MAX_SHAKE": "car"`, `"PASSING_CAR_HEIGHT": "camera"`, `"CLOSE_CAR_HEIGHT": "camera"`, `"MAX_CAR_WIDTH_FRACTION": "camera"`.
  - `class ProfileError(Exception)`
  - `@dataclass(frozen=True) class Profile: name: str; path: Path | None; values: dict` with a property `description -> str`: `"built-in values"` when `path` is None, otherwise `f"{name} ({path.name})"`.
  - `BUILT_IN = Profile("built-in values", None, {})`
  - `load_profile(path: Path) -> Profile`
  - `using_profile(profile: Profile)`: a context manager.

- [ ] **Step 1: Write the failing tests** in `tests/test_profile.py`, class `LoadProfileTest` and class `UsingProfileTest`. Each test writes its file into a `tempfile.TemporaryDirectory()`.
  - `test_reads_values`: file `son.toml` with `PACE_MIN_EFFORT = 0.5` and `OFFTRACK_MIN_SHAKE = 6` → `profile.values == {"PACE_MIN_EFFORT": 0.5, "OFFTRACK_MIN_SHAKE": 6.0}`, `profile.name == "son"`.
  - `test_folder_file_is_named_after_its_folder`: `<tmp>/practice driver/profile.toml` → `profile.name == "practice driver"`.
  - `test_comments_and_empty_file_are_fine`: a file holding only comments → `profile.values == {}`.
  - `test_file_saved_with_bom`: the bytes `b"\xef\xbb\xbfPACE_MIN_EFFORT = 0.5\n"` → loads, value 0.5.
  - `test_unknown_name_is_refused`: `PACE_MIN_EFORT = 0.5` → `ProfileError` whose message contains `"PACE_MIN_EFORT"` and the file name.
  - `test_text_value_is_refused`: `PACE_MIN_EFFORT = "low"` → `ProfileError` with `"PACE_MIN_EFFORT"` in the message.
  - `test_true_false_is_refused`: `PACE_MIN_EFFORT = true` → `ProfileError` (Python counts `True` as a number, the profile must not).
  - `test_broken_file_is_refused`: `PACE_MIN_EFFORT = ` → `ProfileError` with the file name in the message.
  - `test_missing_file_is_refused`: a path that does not exist → `ProfileError` with the path in the message.
  - `UsingProfileTest.test_values_set_inside_and_restored_after`: with `Profile("x", None, {"PACE_MIN_EFFORT": 0.5})`, inside the block `settings.PACE_MIN_EFFORT == 0.5`; after it, the value read before the block.
  - `test_restored_after_an_error`: raise `ValueError` inside the block, catch it outside → value restored.
  - `test_built_in_changes_nothing`: inside `using_profile(BUILT_IN)` `settings.PACE_MIN_EFFORT` is unchanged.

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_profile -v`
Expected: error `No module named 'pp_tt_video.profile'`.

- [ ] **Step 3: Write `pp_tt_video/profile.py`**
  - `load_profile`: read the bytes, decode with `"utf-8-sig"` (this drops a BOM), parse with `tomllib.loads`. Turn `FileNotFoundError` and `tomllib.TOMLDecodeError` into `ProfileError`. Accept `int` and `float` but not `bool`, and store every value as `float`. Name: the folder's name when the file is called `settings.PROFILE_FILE_NAME`, otherwise the file name without `.toml`.
  - `using_profile`: build it with `contextlib.contextmanager`. Remember the old values, set the new ones with `setattr(settings, name, value)`, `yield`, and put the old ones back in `finally`.
  - Add to `settings.py`, in a new section `# --- Driver and car profiles ---` with comments: `PROFILE_FILE_NAME = "profile.toml"` and `PROFILES_FOLDER = PROJECT_FOLDER / "profiles"`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv\Scripts\python.exe -m unittest tests.test_profile -v`
Expected: all pass. Then run all checks with `.venv\Scripts\python.exe -m unittest`. Expected: all pass, none skipped except the one that needs the examples when they are missing.

- [ ] **Step 5: Give the author the commit commands**

```bash
git add pp_tt_video/profile.py pp_tt_video/settings.py tests/test_profile.py
git commit -m "Read a driver and car profile and apply it to the settings"
```

---

### Task 2: Choosing the profile for a video

**Files:**
- Modify: `pp_tt_video/profile.py`
- Modify: `.gitignore` (add `profiles/` with a comment: profiles carry driver names and the repository is public)
- Test: `tests/test_profile.py`

**Interfaces:**
- Consumes: `load_profile`, `ProfileError`, `BUILT_IN` from Task 1; `settings.PROFILE_FILE_NAME`, `settings.PROFILES_FOLDER`.
- Produces:
  - `find_profile(video: Path, profile_option: str | None) -> Path | None`
  - `profile_for_video(video: Path, profile_option: str | None) -> Profile`: `find_profile`, then `load_profile`, or `BUILT_IN` when nothing is found. Raises `ProfileError`.

- [ ] **Step 1: Write the failing tests**, class `FindProfileTest`. Patch `settings.PROFILES_FOLDER` to a temporary folder with `unittest.mock.patch.object`.
  - `test_option_name_means_profiles_folder`: option `"son"` → `PROFILES_FOLDER / "son.toml"`.
  - `test_option_ending_in_toml_is_a_path`: option `"some/where/x.TOML"` → `Path("some/where/x.TOML")`.
  - `test_option_wins_over_folder_file`: the video's folder holds `profile.toml`, option `"son"` → the `son.toml` path.
  - `test_folder_file_is_found`: no option, `profile.toml` next to the video → that path.
  - `test_nothing_gives_none`: no option, no file → `None`.
  - `test_profile_for_video_without_profile_is_built_in`: → `BUILT_IN`.
  - `test_missing_named_profile_says_where_it_looked`: option `"son"`, no such file → `ProfileError` whose message contains `"son.toml"`.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_profile -v`
Expected: the new tests fail with `cannot import name 'find_profile'`.

- [ ] **Step 3: Add `find_profile` and `profile_for_video` to `profile.py`, and the `.gitignore` line**

`find_profile` does not check whether a file named by the option exists. `load_profile` reports a missing file, so the message names the path it looked for.

- [ ] **Step 4: Run all checks**

Run: `.venv\Scripts\python.exe -m unittest`
Expected: all pass.

- [ ] **Step 5: Give the author the commit commands**

```bash
git add pp_tt_video/profile.py tests/test_profile.py .gitignore
git commit -m "Choose the profile for a video: option, folder file or built-in values"
```

---

### Task 3: Using the profile when processing videos

**Files:**
- Modify: `pp_tt_video/pipeline.py` (`EventsMaker.make_events_file`, `process_video`, `process_videos`)
- Modify: `pp_tt_video/__main__.py` (new option)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `profile_for_video`, `using_profile`, `ProfileError` from Tasks 1 and 2.
- Produces:
  - `process_videos(inputs, overwrite=False, output_folder=None, with_events=True, on_start=None, on_progress=None, on_done=None, profile_option=None)`
  - `process_video(video, overwrite=False, output_folder=None, events_maker=None, with_events=True, on_progress=None, profile_option=None)`
  - `EventsMaker.make_events_file(video, output_folder, overwrite, on_progress=None, profile=BUILT_IN)`
  - Command line: `--profile NAME_OR_FILE`, help text `"driver and car profile: a name from the profiles folder, or a .toml file"`.

- [ ] **Step 1: Write the failing tests** in `tests/test_pipeline.py`, class `ProfileInPipelineTest`. Each test makes empty `.mp4` files in a temporary folder. It patches `pp_tt_video.detect_cars.CarDetector` with a `MagicMock`, patches `pp_tt_video.pipeline.write_events_file` with a `MagicMock` (so no real timeline is needed), and patches `pp_tt_video.detect_events.detect_timeline` with a fake. The fake records `settings.PACE_MIN_EFFORT` at the moment it is called and then returns `[]`. The GPX step fails on the empty files, which is fine: the tests look at what the fake recorded and at the messages.
  - `test_folder_profile_is_used_for_its_videos`: folder A holds `a.mp4` and `profile.toml` with `PACE_MIN_EFFORT = 0.5` → the fake recorded `0.5`, and after the run `settings.PACE_MIN_EFFORT` is back to its value from before.
  - `test_second_folder_without_profile_gets_built_in_values`: folder A as above, folder B with `b.mp4` and no profile, `process_videos([A, B])` → recorded `[0.5, <built-in value>]`.
  - `test_profile_option_wins`: folder A's `profile.toml` says 0.5, option is a path to `other.toml` with `PACE_MIN_EFFORT = 0.7` → recorded `0.7`.
  - `test_broken_profile_fails_that_video_and_run_goes_on`: folder A's `profile.toml` holds `PACE_MIN_EFORT = 0.5`, folder B has no profile → two results. The first is not ok and its message contains `"PACE_MIN_EFORT"`; the fake was called once (for B).
  - `test_message_names_the_profile`: for the folder profile, `results[0].message` contains `"profile: A (profile.toml)"`, where `A` is the folder's name.
  - `test_gps_only_ignores_profiles`: `with_events=False` and a broken `profile.toml` → the message does not mention the profile, and the fake is never called.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_pipeline -v`
Expected: `TypeError: ... unexpected keyword argument 'profile_option'`.

- [ ] **Step 3: Change `pipeline.py` and `__main__.py`**
  - In `process_video`, only when `with_events`: call `profile_for_video(video, profile_option)` before the events step. On `ProfileError`, the events part becomes `(False, str(error))` and the GPS part is kept as it is. Otherwise add `f"profile: {profile.description}"` to the message, between the GPS part and the events part, joined with `"; "` as now.
  - In `make_events_file`, the detection call `detect_timeline(...)` runs inside `with using_profile(profile):`. Writing the file stays outside the block.
  - Pass `profile_option` from `process_videos` to `process_video`, and from `__main__` (`arguments.profile`) to `process_videos`.
  - Update the module docstring of `pipeline.py`: it should mention that a profile may apply.

- [ ] **Step 4: Run all checks**

Run: `.venv\Scripts\python.exe -m unittest`
Expected: all pass, including the check that needs the examples, when they are present. It runs without a profile, so its result must not change.

- [ ] **Step 5: Give the author the commit commands**

```bash
git add pp_tt_video/pipeline.py pp_tt_video/__main__.py tests/test_pipeline.py
git commit -m "Apply the driver and car profile per video (step P1)"
```

---

### Task 4: Measuring a driver and scaling the values

**Files:**
- Create: `pp_tt_video/make_profile.py` (the measuring and writing parts; the command comes in Task 5)
- Modify: `pp_tt_video/settings.py` (reference levels)
- Test: `tests/test_make_profile.py`

**Interfaces:**
- Consumes: `forward_force_per_second`, `effort_per_second` from `pace.py`; `value_per_second` from `session.py`; `PROFILE_VALUES`, `load_profile` from `profile.py`; `SensorSecond` from `sensors.py`.
- Produces:
  - `percentile(values: list[float], percent: float) -> float`: `sorted(values)[round(percent / 100 * (len(values) - 1))]`. Raises `ValueError` on an empty list.
  - `braking_level(sensor_seconds: list) -> float`: the percentile of `effort_per_second(forward_force_per_second(s))`.
  - `cornering_level(sensor_seconds: list) -> float`: the percentile of the absolute sideways force per second.
  - `driver_levels(videos_sensor_seconds: list[list]) -> tuple[float, float]`: braking and cornering level over **all seconds of all videos pooled**. Pooling means the effort is worked out per video and the seconds are then put together, so the 40-second window never spans two videos.
  - `scaled_values(braking: float, cornering: float) -> dict[str, float]`: for every `PROFILE_VALUES` name marked `"driver braking"`, the built-in value × `braking / settings.REFERENCE_EFFORT`. For `"driver cornering"`, the built-in value × `cornering / settings.REFERENCE_CORNERING`. Rounded to 2 decimals. Car and camera names are not in the result.
  - `profile_text(video_names: list[str], braking: float, cornering: float) -> str`: the file text in the format of the example in `TECHNICAL_SPEC.md` ("Driver and car profiles"). A header with the video names, the levels and the ratios. One comment line per value saying what it does (take the wording from the comments in `settings.py`). The driver values set. The car and camera values written as `# NAME = <built-in value>` under a heading that says to remove the `#` to change one.
  - In `settings.py`, section `# --- Driver and car profiles ---`: `PROFILE_PERCENTILE = 95` (comment: what a percentile is, in one sentence) and `REFERENCE_EFFORT = 2.5`, `REFERENCE_CORNERING = 11.0`. Comment: "the user's own levels, measured on the three examples; replaced by the exact measurement in Task 6".

- [ ] **Step 1: Write the failing tests** in `tests/test_make_profile.py`. Build made-up sensor data from `SensorSecond(start, acceleration, rotation)`, where every second has a few identical measurements. A second with forward force *f* and sideways force *c* is `[(−9.8, c, f)] * 10` with rotation `[(0, 0, 0)] * 10`; this follows the axes in `settings.py`.
  - `test_percentile`: `percentile(list(range(101)), 95) == 95`; `percentile([3.0], 95) == 3.0`; an empty list raises `ValueError`.
  - `test_driver_at_reference_keeps_built_in_values`: patch `REFERENCE_EFFORT` to 2.0 and `REFERENCE_CORNERING` to 10.0, then `scaled_values(2.0, 10.0)` → `{"PACE_MIN_EFFORT": settings.PACE_MIN_EFFORT, "PACE_HARD_FORCE": settings.PACE_HARD_FORCE, "SLIDE_MIN_CORNERING_FORCE": settings.SLIDE_MIN_CORNERING_FORCE, "SESSION_TRACK_CORNER_FORCE": settings.SESSION_TRACK_CORNER_FORCE}`.
  - `test_gentle_driver_gets_lower_values`: same references, `scaled_values(1.0, 5.0)` → each value half the built-in one, rounded to 2 decimals.
  - `test_levels_of_steady_driving`: one video of 300 seconds with forward force 2.0 and sideways force −8.0 every second → `driver_levels([video]) == (2.0, 8.0)`.
  - `test_slow_parts_do_not_pull_the_level_down`: 200 seconds at force 0.3, then 100 seconds at 2.0 → braking level 2.0 (well over 5% of the seconds are at pace).
  - `test_written_text_loads_back`: write `profile_text(["a.MP4"], 1.0, 5.0)` to `profile.toml` in a temporary folder. `load_profile` gives exactly the four driver names, with the values of `scaled_values(1.0, 5.0)`. The text contains `"a.MP4"` and `"# OFFTRACK_MIN_SHAKE ="`.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_make_profile -v`
Expected: `No module named 'pp_tt_video.make_profile'`.

- [ ] **Step 3: Write the functions in `make_profile.py` and the settings**

- [ ] **Step 4: Run all checks**

Run: `.venv\Scripts\python.exe -m unittest`
Expected: all pass.

- [ ] **Step 5: Give the author the commit commands**

```bash
git add pp_tt_video/make_profile.py pp_tt_video/settings.py tests/test_make_profile.py
git commit -m "Measure a driver from the sensors and scale the profile values"
```

---

### Task 5: The `make_profile` command

**Files:**
- Modify: `pp_tt_video/make_profile.py` (add `main()` and `if __name__ == "__main__":`)
- Test: `tests/test_make_profile.py`

**Interfaces:**
- Consumes: Task 4's functions; `find_videos` from `pipeline.py`; `read_sensors`, `SensorError` from `sensors.py`; `settings.PROFILE_FILE_NAME`, `settings.PROFILES_FOLDER`.
- Produces:
  - `make_profile(folder: Path, name: str | None = None, overwrite: bool = False, print_only: bool = False, read=read_sensors) -> tuple[bool, str]`: returns (ok, message). `read` is there so the tests can hand in made-up sensor data instead of reading real videos.
  - The command: `.venv\Scripts\python.exe -m pp_tt_video.make_profile "<folder>" [--name NAME] [--overwrite] [--print-only]`. Exit code 0 when ok, 1 when not.
  - Where it writes: without `--name`, `<folder>/profile.toml`; with `--name son`, `settings.PROFILES_FOLDER / "son.toml"` (the folder is created if missing).
  - `--print-only` prints the levels and ratios per video and over all, and writes nothing. Task 6 uses it to measure the author's own levels.

- [ ] **Step 1: Write the failing tests**, class `MakeProfileCommandTest`, with a fake `read` that returns made-up sensor seconds per video name and raises `SensorError` for a name containing `"broken"`. Videos are empty `.mp4` files in a temporary folder.
  - `test_writes_profile_into_the_folder`: → ok, `profile.toml` exists, and `load_profile` reads it.
  - `test_name_writes_into_profiles_folder`: patch `PROFILES_FOLDER`, `name="son"` → `son.toml` there; nothing in the video folder.
  - `test_existing_file_is_not_replaced`: `profile.toml` already holds `"# mine"` → not ok, the message contains `"--overwrite"`, the file still holds `"# mine"`.
  - `test_overwrite_replaces`: same with `overwrite=True` → ok, new content.
  - `test_video_without_sensors_is_skipped`: `a.mp4` plus `broken.mp4` → ok, the message names `broken.mp4` as skipped, and the profile header lists only `a.mp4`.
  - `test_no_usable_video_writes_nothing`: only `broken.mp4` (or an empty folder) → not ok, no file written.
  - `test_print_only_writes_nothing`: → ok, no file, the message contains the braking level.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_make_profile -v`
Expected: `cannot import name 'make_profile'`.

- [ ] **Step 3: Write `make_profile()` and `main()`**

Follow `__main__.py` for the style of the arguments and messages. Print one line per video as it is read, because reading takes about 5 seconds each.

- [ ] **Step 4: Run all checks**

Run: `.venv\Scripts\python.exe -m unittest`
Expected: all pass.

- [ ] **Step 5: Give the author the commit commands**

```bash
git add pp_tt_video/make_profile.py tests/test_make_profile.py
git commit -m "Add the make_profile command"
```

---

### Task 6: Measure the author, make the son's profile, try it (step P2)

No new code. Real runs, then the documents.

- [ ] **Step 1: Measure the author's levels on the three examples**

Run: `.venv\Scripts\python.exe -m pp_tt_video.make_profile "example video  and output file" --print-only`
Expected: braking about 2.5, cornering about 11 over all three. Nothing is written into the example folder.

- [ ] **Step 2: Put the measured numbers into `settings.py`** as `REFERENCE_EFFORT` and `REFERENCE_CORNERING`, rounded to 2 decimals, and change their comment to say they were measured on the three examples. Run `.venv\Scripts\python.exe -m unittest`. Expected: all pass.

- [ ] **Step 3: Compare with the author's newer video**

Run: `.venv\Scripts\python.exe -m pp_tt_video.make_profile "input video files\stronger driver" --print-only`
Expected: braking about 2.1. Tell the author the ratio. No file is made; the author decides later whether to make a profile of their own.

- [ ] **Step 4: Make the son's profile**

Run: `.venv\Scripts\python.exe -m pp_tt_video.make_profile "input video files\practice driver"`
Expected: `input video files\practice driver\profile.toml` is written, with a braking ratio of about 0.4 and a cornering ratio of about 0.55. Show the author the file.

- [ ] **Step 5: Run the module on the son's videos with the profile**

Ask the author first: this replaces the four events files the module wrote earlier (they hold only `00:00 warm up`), and detection takes about a third of the videos' length, roughly 25 minutes for all four. Run it in the background:

Run: `.venv\Scripts\python.exe -m pp_tt_video "input video files\practice driver" --overwrite`
Expected: every video line says `profile: practice driver (profile.toml)`. The events files now contain a part at pace (`clear` lines) and events. Show the author the four files and the count of each label. A count that looks implausible (for example dozens of `sliding`) is reported as found, not fixed. Judging it is what the check video is for.

- [ ] **Step 6: Update the documents**
  - `TECHNICAL_SPEC.md`: change the heading "Driver and car profiles (planned, before step 9)" to "(built in steps P1 and P2)". Add the measured reference levels and the son's result in a short paragraph.
  - `BUSINESS_SPEC.md`, the footage table: replace "first measurement" with the measured numbers.
  - `CLAUDE.md`: under Progress, add "Done: P1 and P2 (driver and car profiles)" and "Next: the check video (V1 to V7, `CHECK_VIDEO_TECHNICAL_SPEC.md`), then step 9". Under Practical details, add the `make_profile` command and the `--profile` option.
  - `.venv\Scripts\python.exe -m unittest`. Expected: all pass.

- [ ] **Step 7: Give the author the commit commands**

```bash
git add pp_tt_video/settings.py TECHNICAL_SPEC.md BUSINESS_SPEC.md CLAUDE.md
git commit -m "Measure the reference levels and try the son's profile (step P2)"
```
