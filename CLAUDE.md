# How we work on this project

This file is read by Claude Code at the start of every session. It holds what is not written anywhere else: how the author and the assistant work together.

## Read first

1. `BUSINESS_SPEC.md`: what the module must do. It is the authority.
2. `TECHNICAL_SPEC.md`: how it is built, the order of work, open questions, ideas for later.
3. `git log --oneline`: what has been done, one commit per step.

## Progress

Steps refer to "Proposed order of work" in `TECHNICAL_SPEC.md`. Update this list when a step is finished.

- Done: steps 0 to 6 (repository, tools, GPS extraction, events files and comparison tool, sensor data check, video reduction and speed measurement, car tracking for `overtaking`, `overtaken` and `held up`), step 7 (`sliding` and `offtrack` from the motion sensors) and step 8 (`warm up` and `cooling` from the motion sensors; events outside the at-pace part are dropped).
- Done after step 7, at the author's wish: the label `out of session` (before the car joins the track, after it has left) and a first rule for `crash` (the car stands still within a minute after driving at pace). Both are in `pp_tt_video/session.py`.
- Done before step 9, at the author's wish: driver and car profiles, steps P1 and P2 (`pp_tt_video/profile.py`, `pp_tt_video/make_profile.py`). The built-in values in `settings.py` are the author's own driving; a profile scales the driver values for someone else. The plan is in `docs/superpowers/plans/`.
- Done: the check video, steps V1 to V6 (`CHECK_VIDEO_BUSINESS_SPEC.md`, `CHECK_VIDEO_TECHNICAL_SPEC.md`, plan in `docs/superpowers/plans/`). Step V7 (box smoothing) was skipped: the author found the boxes fine.
- Next, in this order (decided by the author): a rework of the offtrack rule with the check video as the tool; then step 9 (`obstacle`, `other event`, the description experiment). A car standing on the track counts as `obstacle` (decided by the author).
- **The offtrack rule gives false alarms on the son's footage** (`input video files/practice driver`): 6 to 19 per video, all 19 in GX010183 confirmed false by the author. They are a camera vibration (up-and-down only, about 87 per second), not rough ground. A profile cannot fix it. Measurements are in the technical spec under "Driver and car profiles". Until the rule is reworked, do not run the module on those videos with `--overwrite` in place: it would write the false alarms into their events files. A run with `--output-folder` to a scratch folder touches nothing there and is fine.
- Not yet judged on the son's videos: whether all of GX010182 and GX010183 is at pace, and whether the `crash` in GX010179 is a stop in the pits.
- Known weak spots in the sensor rules: the short offtrack at 02:31 in 09-41 is missed (right wheels about 20 cm off for a few tenths of a second; the up-and-down shake stays under the threshold), and only slides caught with a steering correction are found.
- Open questions 2 to 5 in the business spec wait for the author's answer (two assumptions, the changed descriptions of `out of session`, `warm up` and `cooling`, a possible unmarked slide at 02:47 in 09-41, the 22-second `sliding` in the 12-17 hand-made file).
- A brisk first lap is not `warm up` (decided by the author): 10-32 and 12-17 rightly get none.
- Known weak spots in the car rules, from the 09-41 example: the overtake at 04:05 is missed and the one at 10:34 to 10:38 is reported as `held up` (see the table in the technical spec).
- The hand-made events file for 09-41 lacks four real overtakes (02:54, about 03:38, 04:05, 10:34 to 10:38). The author left them out on purpose as a test. Ask the author for the exact lines before adding them; do not edit the file unasked.

## Working together

- **The author is learning Python and Git.** Explain what you do and why, in plain language. When introducing something new (a command, a Python feature), say what it is in a sentence.
- **Plan before code.** Do not write code for a new step until the author says to start it. One step at a time.
- **The author runs the Git commands.** Give `git add`, `git commit` and `git push` as commands to run, with a line on what each does. Commit yourself only when asked to, and never push.
- **A declined action is not a stop sign.** If the author declines one change, skip that change and carry on with the rest.
- **Decisions go into the specs as they are made.** What the module must do goes into the business spec; how it is built goes into the technical spec. Mark your own assumptions as assumptions so the author can confirm or correct them.
- **Do not change the hand-made reference files** in the example folder without asking. They are the author's own work and are not in Git. Each example has two: `name-events.original.txt` is the author's file and is never touched; `name-events.txt` is the cleaned copy the tools use. The author has agreed that the cleaned copies are kept in step with the originals; say so when you update one.
- **Ask before installing anything**, including Python libraries. Installed so far: PyTorch and torchvision (see `requirements.txt`), in the virtual environment `.venv`.
- **Each step ends with something that runs**, with its checks passing, and one commit.

## Code style

- Readable for someone new to Python: small files, plain names, comments that explain why.
- Values that may need tuning live in `pp_tt_video/settings.py`, never in the logic.
- Rules read `settings.NAME` at the moment they run. Never copy a setting with `from pp_tt_video.settings import NAME` or into a function's default value: a profile changes the values in `settings` while a video is processed, and a copy would silently keep the built-in number.
- Event types are data (`event_types.csv`), not code.
- Every new piece of behaviour gets a check in `tests/`.

## Practical details

- **Python:** the project runs with the virtual environment's Python, `.venv\Scripts\python.exe` (Python 3.13 with the detection libraries). The environment was made with `py -V:3.13 -m venv .venv`. Version 3.15 is also installed on the PC and is the default for plain `python`; it has no libraries.
- **Run the checks:** `.venv\Scripts\python.exe -m unittest`
- **Run the module:** `.venv\Scripts\python.exe -m pp_tt_video "<video file or folder>"`. It writes a GPX file, a sensor data file (`name-sensors.csv`, also with `--gps-only`) and an events file per video and skips files that already exist. `--output-folder <folder>` writes elsewhere (needed for the examples, whose hand-made files sit next to the videos); `--gps-only` skips detection.
- **Profiles:** `--profile <name or .toml file>` uses that profile for every video; a name means `profiles/<name>.toml` (the folder is not in Git). Without the option, a `profile.toml` in a video's folder is used for that video; otherwise the built-in values. Every video line says which profile was used.
- **Make a profile:** `.venv\Scripts\python.exe -m pp_tt_video.make_profile "<folder with one driver's videos>"` writes `profile.toml` into that folder. `--name <name>` writes `profiles/<name>.toml` instead; `--print-only` measures and writes nothing; `--overwrite` replaces an existing profile.
- **Other footage** is in `input video files/` (not in Git), one folder per driver: `practice driver` (the author's son, four videos, has a `profile.toml`) and `stronger driver` (the author, one video). No hand-made events files there.
- **Check video:** `--check-video` also writes `name-check.mp4`: the video at 1280 pixels wide with the car boxes, the events, the profile and the time drawn in, and below it a strip with the sensor values and thresholds the rules use. It also writes `name-overview.png`, one picture of the whole video (pace, session parts, events kept and thrown away, cars). It keeps the car detections in `name-detections.json` and uses them again, so only the first run is slow; after that, delete the check video and run again to redraw it in under half of the video's length (measured: 181 s for the 6:27 example, 195 MB). A missing overview is added in seconds, as long as the detections file is there. What is drawn is set in `pp_tt_video/check_video_settings.py`. Not usable with `--gps-only`. Always give `--output-folder` a scratch folder when trying things. Check videos kept for watching are in `check videos/` (not in Git: they show faces).
- **Check events files:** `.venv\Scripts\python.exe -m pp_tt_video.check_events "<folder>"`
- **Measure reading speed:** `.venv\Scripts\python.exe -m pp_tt_video.measure_speed "<video>"`
- **Compare two events files:** `.venv\Scripts\python.exe -m pp_tt_video.compare "<reference>" "<detected>"`
- **Detection is slow to repeat** (about a third of the video's length). When tuning rules, save the detections once and work from the saved copy.
- **The motion sensors are quick to read** (about 5 seconds per video, `pp_tt_video/sensors.py`). Rules that only need them (`pace.py`, `session.py`, `sliding.py`, `offtrack.py`) can be tried on all examples in seconds.
- **External tools** (ExifTool, ffmpeg, ffprobe, `gpx.fmt`) are in `executables/`, which is not in Git.
- **Examples** are in `example video  and output file/` (two spaces after "video"), which is not in Git: three videos of 2.6 to 5.3 GB, each with a hand-made events file and a GPX file. One check needs them and is skipped when they are missing.
- **The repository is public.** Nothing private goes into it: no keys, no personal data, no absolute paths from this PC.
