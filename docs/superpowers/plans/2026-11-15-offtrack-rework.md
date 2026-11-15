# Offtrack Rule Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The offtrack rule no longer reports the camera's fast vibration, and finds both offtracks the author marked in 09-41 (02:31 and 11:15).

**Architecture:** `shake_over_time` in `pp_tt_video/offtrack.py` averages each measurement with the ones that follow it before it measures the shake; the fast vibration (about 87 per second) cancels out, the slower bumps of rough ground stay. The thresholds move to the smoothed scale. The check video's offtrack chart shows the smoothed shake as the rule's line and the unsmoothed shake for information.

**Tech Stack:** Python 3.13 in `.venv`, `unittest`, `statistics.pstdev`. Nothing new to install.

**Spec:** `docs/superpowers/specs/2026-11-15-offtrack-rework-design.md`

## Global Constraints

- Run the checks with `.venv\Scripts\python.exe -W error::ResourceWarning -m unittest`.
- The author runs Git. Each task ends by giving the `git add` and `git commit` commands with a line on what each does; never commit or push.
- Stop after each task and wait for the author's go-ahead.
- Rules read `settings.NAME` at the moment they run; never copy a setting into a default argument or with `from pp_tt_video.settings import NAME`.
- Values: `OFFTRACK_SMOOTHING_MEASUREMENTS = 4`, `OFFTRACK_MIN_SHAKE = 2.2`, `OFFTRACK_MIN_SECONDS = 1.2`; `OFFTRACK_LEAD_SECONDS = 1.5` and `OFFTRACK_TAIL_SECONDS = 0.5` stay.
- Never run the module on `input video files/practice driver` with `--overwrite` in place. Sensors-only scripts and runs with `--output-folder` to the scratch folder are fine. Changing a file in that folder (its `profile.toml`) needs the author's yes.
- Do not change the hand-made events files.
- Code readable for someone new to Python: plain names, comments that say why.
- The repository is public: no absolute paths from this PC, no personal data.

## Review Focus

1. **A piece with fewer measurements than the smoothing count** (a camera that measures more slowly, or a gap in the data): the rule must not fail, and the piece counts as calm (shake 0). Without smoothing, normal driving (2.4 to 2.9) lies above the new threshold, so falling back to it would give false alarms. Test in Task 1.
2. **`OFFTRACK_SMOOTHING_MEASUREMENTS` set to 0 or a negative number:** treated like 1 (no smoothing), no error. Test in Task 1.
3. **Shaking that is still going on when the video ends:** reported, if it lasted long enough. Test in Task 1.
4. **A profile written before this change:** its comment line must show the built-in value in force now, not a fixed 7.0. Test in Task 1 (`test_make_profile.py` reads the value from `settings`).
5. **A check video where the unsmoothed shake is far larger than the threshold:** the threshold line must not be squeezed to the bottom of the chart. Test in Task 2.

---

### Task 1: The rule

**Files:**
- Modify: `pp_tt_video/offtrack.py`, `pp_tt_video/settings.py` (the "Offtrack" block), `pp_tt_video/charts.py` (only the call in `offtrack_chart`, so the checks stay green)
- Test: `tests/test_motion_events.py`, `tests/test_charts.py`, `tests/test_make_profile.py`
- Documents: `BUSINESS_SPEC.md`, `TECHNICAL_SPEC.md`, `CLAUDE.md`

**Interfaces:**
- Produces:
  - `offtrack.smoothed(values, count) -> list`: the average of every `count` neighbouring values (`len(values) - count + 1` of them). Returns `values` unchanged when `count <= 1` or `len(values) < count`.
  - `offtrack.shake_over_time(sensor_seconds, smoothing=None) -> [(time, shake), ...]`: `smoothing=None` uses `settings.OFFTRACK_SMOOTHING_MEASUREMENTS`; `smoothing=1` gives the shake without smoothing. The smoothing is done inside each piece (a fifth of a second), never across two pieces. The `axis` parameter is removed: only up-and-down is measured.
    A piece with fewer measurements than the smoothing count gets the shake 0.0 (when smoothing is above 1).
  - `offtrack_stretches` and `detect_offtrack` keep their signatures. `offtrack_stretches` now **counts pieces**: a run is long enough when it has at least `round(settings.OFFTRACK_MIN_SECONDS * settings.OFFTRACK_SAMPLES_PER_SECOND)` pieces (6). Comparing times instead (`last + step - first >= 1.2`) depends on rounding: the same six pieces pass or fail depending on where in the second they start.

- [ ] **Step 1: Write the failing tests**

In `tests/test_motion_events.py`, class `OfftrackTest`. A helper builds seconds of 200 measurements from a pattern of up-and-down values:

```python
def seconds_of(self, pattern, count=3):
    down = [pattern[i % len(pattern)] for i in range(200)]
    return [SensorSecond(float(n), [(-9.8 + d, 0, 0) for d in down], [(0, 0, 0)] * 200) for n in range(count)]

FAST = [12, -12]              # changes with every measurement: the camera's vibration
SLOW = [6] * 10 + [-6] * 10   # ten measurements up, ten down: rough ground
```

- `test_smoothed_averages_neighbours`: `smoothed([1, 2, 3, 4, 5], 2) == [1.5, 2.5, 3.5, 4.5]`.
- `test_smoothing_of_one_changes_nothing`: `smoothed([1, 2, 3], 1) == [1, 2, 3]`; the same for `0` and `-3`.
- `test_too_few_values_are_left_alone`: `smoothed([1, 2], 4) == [1, 2]`.
- `test_fast_vibration_is_not_offtrack`: `detect_offtrack(self.seconds_of(FAST)) == []`, and every shake of `shake_over_time(...)` is below 0.1.
- `test_fast_vibration_shows_without_smoothing`: every shake of `shake_over_time(self.seconds_of(FAST), smoothing=1)` is `12.0` (`assertAlmostEqual`).
- `test_slow_rough_shaking_is_offtrack`: labels of `detect_offtrack(self.seconds_of(SLOW))` are `["offtrack"]` (replaces `test_shake_is_measured_from_the_up_and_down_force`, whose made-up shaking was fast).
- `test_smoothing_setting_is_read_when_the_rule_runs`: with `mock.patch.object(settings, "OFFTRACK_SMOOTHING_MEASUREMENTS", 1)`, `detect_offtrack(self.seconds_of(FAST))` has one stretch.
- `test_piece_with_few_measurements_counts_as_calm`: seconds of 10 measurements each (2 per piece), jumping between +12 and -12: every shake is `0.0` and `detect_offtrack` gives `[]`.
- `test_six_pieces_are_enough_wherever_they_start`: for each start in `(100.0, 100.2, 100.4, 100.6, 100.8)`, six pieces of `4.0` at `start + n / 5` between calm pieces give one stretch; five pieces give none.
- `test_shaking_until_the_end_of_the_video_is_reported`: `offtrack_stretches(self.shakes([1.0] * 10 + [4.0] * 10))` has one stretch.
- Adapt the three existing `offtrack_stretches` checks to the smoothed scale: calm `1.0`, offtrack `5.0` for 10 pieces, kerb `1.8` for 4 pieces, short hard bump `6.0` for 2 pieces.
- `test_shaking_just_under_the_time_is_not_offtrack`: `[1.0] * 10 + [4.0] * 5 + [1.0] * 10` (1.0 s) gives `[]`; with 6 pieces (1.2 s) one stretch.

New class, skipped when the examples are missing (follow the `skipUnless` pattern already in this file):

```python
class OfftrackOnExamplesTest(unittest.TestCase):
    def starts(self, name):
        return [stretch.start for stretch in detect_offtrack(read_sensors(EXAMPLE_FOLDER / name))]

    def test_09_41_has_its_two_offtracks(self):
        first, second = self.starts("RaceBox Track Sessionon 30-05-2026 09-41.MP4")
        self.assertAlmostEqual(first, 151, delta=2)    # 02:31 in the hand-made file
        self.assertAlmostEqual(second, 675, delta=2)   # 11:15

    def test_the_other_examples_have_none(self):
        for name in ("RaceBox Track Sessionon 30-05-2026 10-32.MP4", "RaceBox Track Sessionon 30-05-2026 12-17.MP4"):
            self.assertEqual(self.starts(name), [])
```

In `tests/test_charts.py`: `OfftrackChartTest.setUp` uses slow shaking with 100 measurements per second (ten at -4.8, ten at -14.8, repeated; the helper `second_of` already takes `down`) so every piece has enough measurements to smooth and the rule line is not zero; replace the `== 5.0` assertion by `assertGreater(max(shake.values), 1.0)`; delete `ShakeAxisTest` and `test_information_lines_show_the_other_directions` (Task 2 rewrites the lines check; here only make it pass with what `offtrack_chart` returns after Step 3).

In `tests/test_make_profile.py:106`: `self.assertIn(f"# OFFTRACK_MIN_SHAKE = {settings.OFFTRACK_MIN_SHAKE}", text)`.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_motion_events tests.test_charts tests.test_make_profile`
Expected: `ImportError: cannot import name 'smoothed'`.

- [ ] **Step 3: Write the code**

`offtrack.py`: add `smoothed`; `shake_over_time` takes the up-and-down values of each piece, smooths them, then `pstdev`. Update the file's opening text: the rule looks at slow shaking, and why. `settings.py`: the three values above, each with a comment; the comment of `OFFTRACK_MIN_SHAKE` gives the measured smoothed levels (normal driving about 1.0; the camera's vibration 1.7; the short offtrack 2.3 to 3.5; a full offtrack 5 to 7) and says that 3.5 for 1.0 s is the stricter setting. `charts.py`: `offtrack_chart` keeps one rule line `"shake"` from `shake_over_time(sensor_seconds)`; drop the two axis lines (Task 2 adds the information line). So that no text is stale after this task: the `"offtrack"` comment in `check_video_settings.py` and the Offtrack row of `CHECK_VIDEO_TECHNICAL_SPEC.md` 6.3 (with its "as built" note) describe the one line.

- [ ] **Step 4: Run all checks**

Run: `.venv\Scripts\python.exe -W error::ResourceWarning -m unittest`
Expected: OK.

- [ ] **Step 5: Prove it on all eight videos**

A throwaway script in the scratch folder (not in the project) calls `detect_offtrack(read_sensors(video))` for the three examples and the five videos under `input video files/`, and prints the stretches. It only reads.
Expected: 09-41 has two (about 02:30 and 11:15); the other seven have none. If anything else shows, stop and report it to the author before going on: do not tune the numbers silently.

The script also lists what the old rule (unsmoothed, at least 7.0 for 1.0 s) reported and the new one does not. "No hit" is only proof where someone looked: of the practice driver's videos the author watched GX010183 only, and the author's own GX010181 has no hand-made file. Report these to the author to check on the check video: GX010181 08:40 (2.2 s), 10-32 08:15 (3.4 s), 09-41 00:23, 11:42 and 11:58. Measured while planning (counting pieces): the new rule's only near miss in all eight videos is 12-17 at 02:12.7 (5 pieces, one short).

- [ ] **Step 6: Update the documents and give the author the commit commands**

- `BUSINESS_SPEC.md`: what "offtrack" finds now (also a short excursion of a second or so); the false-alarm finding is marked as solved, with how.
- `TECHNICAL_SPEC.md`: the rule as built, the table of measurements and the dropped approaches from the design, the result of Step 5, the known risk (two numbers fitted to two offtracks; the stricter pair 3.5 and 1.0 s as fallback).
- `CLAUDE.md`: Progress: the rework is done; remove "the short offtrack at 02:31 is missed" from the weak spots; replace the false-alarm paragraph by one line saying it is solved. **Keep** the sentence about not running with `--overwrite` on the practice driver's folder until the author says it can go.

```bash
git add pp_tt_video/offtrack.py pp_tt_video/settings.py pp_tt_video/charts.py pp_tt_video/check_video_settings.py CHECK_VIDEO_TECHNICAL_SPEC.md tests/test_motion_events.py tests/test_charts.py tests/test_make_profile.py BUSINESS_SPEC.md TECHNICAL_SPEC.md CLAUDE.md docs/superpowers/specs/2026-11-15-offtrack-rework-design.md docs/superpowers/plans/2026-11-15-offtrack-rework.md
git commit -m "Offtrack rule ignores the camera's fast vibration"
```

---

### Task 2: The check video's offtrack chart

**Files:**
- Modify: `pp_tt_video/charts.py`, `pp_tt_video/check_video_settings.py` (the comment of `"offtrack"` under `STRIP_CHARTS`)
- Test: `tests/test_charts.py`
- Documents: `CHECK_VIDEO_TECHNICAL_SPEC.md` (the Offtrack row of 6.3 and its "as built" note), `CLAUDE.md` if the profile is made again

**Interfaces:**
- Consumes: `shake_over_time(sensor_seconds, smoothing=None)` from Task 1.
- Produces:
  - `offtrack_chart(sensor_seconds)`: lines `Line("shake", ..., from_rule=True)` (smoothed, what the rule decides on) and `Line("shake unsmoothed", ..., from_rule=False)` (`smoothing=1`); threshold `("min", settings.OFFTRACK_MIN_SHAKE)`.
  - `with_scale(chart)`: the "level only 0.5% of the values exceed" is taken from the rule's lines only. A chart with no rule line uses all its lines, as now. Information lines beyond the scale are drawn at the edge (the drawing already does that).

- [ ] **Step 1: Write the failing tests** in `tests/test_charts.py`
  - `test_one_rule_line_and_one_information_line`: `[(line.name, line.from_rule) for line in chart.lines] == [("shake", True), ("shake unsmoothed", False)]`.
  - `test_rule_line_is_what_the_rule_measures`: its (times, values) equal `shake_over_time(self.data)`.
  - `test_information_line_is_the_shake_without_smoothing`: equals `shake_over_time(self.data, smoothing=1)`.
  - `test_fast_vibration_shows_only_in_the_information_line`: a second of 100 measurements that jump with every measurement (`down=(-4.8, -14.8) * 50`): the rule line stays below 0.1, the information line reaches 5.0.
  - In `ScaleTest`, `test_information_lines_do_not_set_the_scale`: a chart with a rule line of values up to 2, an information line up to 50 and a threshold of 2.2 gets `high == 4.4`.
  - `test_chart_of_information_lines_only_still_gets_a_scale`: `high` is the 99.5% level of those lines.
- [ ] **Step 2: Run them to see them fail** — Run: `.venv\Scripts\python.exe -m unittest tests.test_charts`. Expected: failures on the line names and on `high`.
- [ ] **Step 3: Write the code**, and update the `"offtrack"` comment in `check_video_settings.py`: thick yellow line = the slow shake the rule decides on, with its threshold; thin green line = the shake without smoothing, where the camera's vibration shows.
- [ ] **Step 4: Run all checks** — `.venv\Scripts\python.exe -W error::ResourceWarning -m unittest`, expected OK.
- [ ] **Step 5: Show the author.** A throwaway script in the scratch folder writes short check video clips, sensors only (empty detections, so no boxes and no detection pass): `read_frames(video, start_seconds, duration_seconds, frames_per_second)` → `draw_picture` → `VideoWriter`, inside `using_profile`. `frame.time_seconds` is the position in the video; confirm that on the first frame before trusting the drawing. Clips of 30 seconds: 09-41 from 02:20, 09-41 from 11:05, GX010183 from 08:00 (reading only), and one each around the old rule's lost hits of Task 1 Step 5 in the author's own videos (GX010181 08:40, 10-32 08:15). Also the overview pictures of 09-41 and GX010183 (sensors only). Copy all to `check videos/`. A full check video with car boxes needs a detection pass: only with the author's yes.
- [ ] **Step 6: Ask the author two things**, and do each only on a yes: make the practice driver's `profile.toml` again (`.venv\Scripts\python.exe -m pp_tt_video.make_profile "input video files/practice driver" --overwrite`; first show with `--print-only` that the four driver values come out the same); and remove the `--overwrite` warning from `CLAUDE.md`.
- [ ] **Step 7: Update the documents and give the author the commit commands.**

```bash
git add pp_tt_video/charts.py pp_tt_video/check_video_settings.py tests/test_charts.py CHECK_VIDEO_TECHNICAL_SPEC.md CLAUDE.md
git commit -m "Check video shows the smoothed shake the offtrack rule uses"
```
