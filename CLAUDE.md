# How we work on this project

This file is read by Claude Code at the start of every session. It holds what is not written anywhere else: how the author and the assistant work together.

## Read first

1. `BUSINESS_SPEC.md`: what the module must do. It is the authority.
2. `TECHNICAL_SPEC.md`: how it is built, the order of work, open questions, ideas for later.
3. `git log --oneline`: what has been done, one commit per step.

## Progress

Steps refer to "Proposed order of work" in `TECHNICAL_SPEC.md`. Update this list when a step is finished.

- Done: steps 0 to 5 (repository, tools, GPS extraction, events files and comparison tool, sensor data check, video reduction and speed measurement).
- Next: step 6, car tracking for `overtaking`, `overtaken` and `held up`. It needs the first Python libraries, so ask before installing.

## Working together

- **The author is learning Python and Git.** Explain what you do and why, in plain language. When introducing something new (a command, a Python feature), say what it is in a sentence.
- **Plan before code.** Do not write code for a new step until the author says to start it. One step at a time.
- **The author runs the Git commands.** Give `git add`, `git commit` and `git push` as commands to run, with a line on what each does. Commit yourself only when asked to, and never push.
- **A declined action is not a stop sign.** If the author declines one change, skip that change and carry on with the rest.
- **Decisions go into the specs as they are made.** What the module must do goes into the business spec; how it is built goes into the technical spec. Mark your own assumptions as assumptions so the author can confirm or correct them.
- **Do not change the hand-made reference files** in the example folder without asking. They are the author's own work and are not in Git.
- **Ask before installing anything**, including Python libraries. So far the code uses only Python's standard library.
- **Each step ends with something that runs**, with its checks passing, and one commit.

## Code style

- Readable for someone new to Python: small files, plain names, comments that explain why.
- Values that may need tuning live in `pp_tt_video/settings.py`, never in the logic.
- Event types are data (`event_types.csv`), not code.
- Every new piece of behaviour gets a check in `tests/`.

## Practical details

- **Python:** the project uses 3.13, started with `py -V:3.13`. Version 3.15 is also installed and is the default for plain `python`.
- **If `python` or `py` is not found in the assistant's own shell**, call the interpreter by its full path: `%LOCALAPPDATA%\Python\pythoncore-3.13-64\python.exe`.
- **Run the checks:** `py -V:3.13 -m unittest`
- **Run the module:** `py -V:3.13 -m pp_tt_video "<video file or folder>"`
- **Check events files:** `py -V:3.13 -m pp_tt_video.check_events "<folder>"`
- **Measure reading speed:** `py -V:3.13 -m pp_tt_video.measure_speed "<video>"`
- **Compare two events files:** `py -V:3.13 -m pp_tt_video.compare "<reference>" "<detected>"`
- **External tools** (ExifTool, ffmpeg, ffprobe, `gpx.fmt`) are in `executables/`, which is not in Git.
- **Examples** are in `example video  and output file/` (two spaces after "video"), which is not in Git: three videos of 2.6 to 5.3 GB, each with a hand-made events file and a GPX file. One check needs them and is skipped when they are missing.
- **The repository is public.** Nothing private goes into it: no keys, no personal data, no absolute paths from this PC.
