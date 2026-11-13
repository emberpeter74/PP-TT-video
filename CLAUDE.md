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
- Next: step 9 (`obstacle`, `other event`, the description experiment). A car standing on the track counts as `obstacle` (decided by the author).
- Known weak spots in the sensor rules: the short offtrack at 02:31 in 09-41 is missed (it shakes no more than a kerb), and only slides caught with a steering correction are found.
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
- Event types are data (`event_types.csv`), not code.
- Every new piece of behaviour gets a check in `tests/`.

## Practical details

- **Python:** the project runs with the virtual environment's Python, `.venv\Scripts\python.exe` (Python 3.13 with the detection libraries). The environment was made with `py -V:3.13 -m venv .venv`. Version 3.15 is also installed on the PC and is the default for plain `python`; it has no libraries.
- **Run the checks:** `.venv\Scripts\python.exe -m unittest`
- **Run the module:** `.venv\Scripts\python.exe -m pp_tt_video "<video file or folder>"`. It writes a GPX file and an events file per video and skips files that already exist. `--output-folder <folder>` writes elsewhere (needed for the examples, whose hand-made files sit next to the videos); `--gps-only` skips detection.
- **Check events files:** `.venv\Scripts\python.exe -m pp_tt_video.check_events "<folder>"`
- **Measure reading speed:** `.venv\Scripts\python.exe -m pp_tt_video.measure_speed "<video>"`
- **Compare two events files:** `.venv\Scripts\python.exe -m pp_tt_video.compare "<reference>" "<detected>"`
- **Detection is slow to repeat** (about a third of the video's length). When tuning rules, save the detections once and work from the saved copy.
- **The motion sensors are quick to read** (about 5 seconds per video, `pp_tt_video/sensors.py`). Rules that only need them (`pace.py`, `session.py`, `sliding.py`, `offtrack.py`) can be tried on all examples in seconds.
- **External tools** (ExifTool, ffmpeg, ffprobe, `gpx.fmt`) are in `executables/`, which is not in Git.
- **Examples** are in `example video  and output file/` (two spaces after "video"), which is not in Git: three videos of 2.6 to 5.3 GB, each with a hand-made events file and a GPX file. One check needs them and is skipped when they are missing.
- **The repository is public.** Nothing private goes into it: no keys, no personal data, no absolute paths from this PC.
