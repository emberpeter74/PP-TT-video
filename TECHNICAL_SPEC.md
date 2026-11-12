# Trackday footage analysis module: technical specification

Status: first draft of the design. Everything here is a proposal until tested; nothing has been built. No code exists yet.

This document says **how** the module is built. **What** it must do is in `BUSINESS_SPEC.md`, which stays the authority: if the two disagree, the business specification wins.

## 1. Environment

| Item | Value | Source |
|---|---|---|
| Computer | The user's home PC, Windows 11 Pro | stated by user |
| Graphics card | Nvidia GeForce RTX 3060 Ti, 8 GB memory | read from the PC |
| Camera | GoPro 13, forward view | stated by user |
| Footage | H.265, 5312x2988, 29.97 fps, about 400 MB per minute, with stereo sound | example file |

Tools on the PC:

| Tool | Needed for | State |
|---|---|---|
| Python | The module itself | Two versions are installed with the Python install manager (`py`): 3.15.2 (the default) and 3.13.17. The project uses **3.13**, because the newest release is often not yet supported by video and detection libraries. Whether those libraries already support 3.15 is unverified. |
| ExifTool | GPS extraction | Version 13.59, in the `executables` folder. Same version that produced the reference GPX file. |
| ffmpeg, ffprobe | Reading and downscaling video, extracting sound, reading video properties | Build of 13 July 2024, in the `executables` folder. Supports Nvidia hardware decoding of H.265. |

### The `executables` folder

ExifTool and ffmpeg need no installation on Windows, so they are kept in a folder `executables` inside the project:

- `exiftool.exe` with its `exiftool_files` folder, and the GPX template `gpx.fmt`;
- `ffmpeg.exe`, `ffprobe.exe` (and `ffplay.exe`, which the module does not use).

Rules:

- The module looks for its tools in this folder. The folder's location is a setting, not fixed in the logic.
- The folder is **not in the Git repository**: the files are large (about 125 MB each for ffmpeg) and carry their own licences. The README tells others which tools to download and where to put them.

## 2. Language

**Python**, for three reasons:

- The user wants to learn it.
- It is the standard language for video analysis: the libraries for decoding video, reading GoPro data and running detection models on an Nvidia card all exist for it.
- The larger program can call a Python module directly.

Consequence for style: the code must be readable for someone learning the language. Small files, plain names, comments that explain why, no clever shortcuts.

## 3. Where it runs

The module runs entirely on the home PC. Reasons:

- A trackday produces up to about 100 GB of footage (20 files of about 5 GB). Uploading that to a cloud service would take longer than processing it at home.
- The business specification requires the footage to stay on the user's computer.
- The graphics card is suitable: it can decode H.265 video in hardware and run standard detection models.

Limit to keep in mind: 8 GB of graphics memory is enough for object detection and small image-and-text models, but not for the large models that "understand" video from a description. This affects the description route in section 6.

## 4. Structure

One run processes a list of video files. Each file goes through the same steps, independently of the others.

| Step | What it does | Output |
|---|---|---|
| 1. Check input | For each file: does it exist, is it a video, do output files already exist | List of files to process |
| 2. Extract GPS | Runs ExifTool on the file | `name.gpx` |
| 3. Read signals | Reads motion sensor data and sound from the file; decodes a reduced version of the picture | Signals per moment in time |
| 4. Detect | Each detector looks at the signals and reports where its event type occurs, with a confidence | Candidate events |
| 5. Build timeline | Keeps only confident candidates, combines overlapping labels, fills the rest with `clear` | Timeline |
| 6. Write events | Writes the timeline in the agreed format | `name-events.txt` |

Rules across all steps:

- A failure in one file is recorded and the run continues with the next file.
- An existing events file is not replaced unless the user asks for it explicitly.
- Steps 2 and 3–6 are independent: GPS extraction still works if detection fails, and the other way round.

## 5. GPS extraction (step 2)

- The module calls ExifTool with the same options the user has used by hand:
  `exiftool -a "-gps*" -p gpx.fmt -ee <video> > <name>.gpx`
- `gpx.fmt` is ExifTool's GPX template file. A copy is kept in the `executables` folder next to ExifTool.
- The output is written unchanged, as the business specification requires.
- Check: the module's output for the example video must be identical to the reference GPX file.

## 6. Detection (steps 3 and 4)

### Reducing the video

Analysing every frame at 5.3K is unnecessary and too slow. Proposal:

- Decode with the graphics card, scale down to roughly 1280 pixels wide, and analyse about 5 to 10 frames per second.
- A tolerance of 5 seconds and events lasting 2 seconds or more make this safe.
- Expected to run several times faster than real time; **to be measured**, not assumed.

### Signals available in a GoPro file

| Signal | Useful for | State |
|---|---|---|
| Picture | Other cars, obstacles, road surface | Available |
| Sound | Tyre squeal (sliding), engine load (warm up, cooling) | Available |
| Gyroscope and accelerometer | Sliding, off-track vibration, speed changes | Normally recorded by GoPro cameras; **to be verified** in the example file |
| GPS | Nothing: mostly invalid | Not used for detection |

The motion sensors matter: unlike the GPS, they do not need a satellite fix, so if present they are valid for the whole video.

### Proposed method per event type

| Label | Proposed method | Confidence in the method |
|---|---|---|
| `overtaking` | Detect other cars with a ready-made object detection model and follow each one across frames. A car that is ahead, grows, moves to the side and leaves the picture has been passed. | Good |
| `overtaken` | Same tracking. A car that enters from the side edge and moves toward the centre has passed. Start time is moved 3 seconds earlier. | Good |
| `held up` | Same tracking. A car that stays large and centred ahead for several seconds without being passed. | Good, but no example yet |
| `sliding` | Gyroscope: the car turns faster than the steering situation explains. Supported by tyre sound. Fallback without sensors: sideways motion of the picture. | Medium; depends on sensor data |
| `offtrack` | Accelerometer: strong vibration typical of grass or gravel. Supported by the picture: the surface under the car is not tarmac. | Medium |
| `warm up`, `cooling` | Estimate of pace from engine sound and picture motion; first and last sustained stretch at low pace. | Medium; the business specification accepts leaving these out |
| `obstacle` | Hardest. Objects on the road that are not moving cars: object detection for stopped cars, description-based recognition for debris. | Low; debris is small and rare |
| `other event` | Compare each moment with normal clear driving in the same video and flag only strong deviations. | Low; conflicts with the false-alarm rule, so it starts very conservative |

### The description route

The business specification gives each event type a description. Technically this means a model that scores how well a picture matches a sentence.

- Models of this kind that fit in 8 GB exist and are fast, but judge single pictures, not motion. They suit `obstacle`; they do not suit `sliding`.
- Larger models that follow motion do not fit this graphics card.
- Proposal: build the detectors above first, and test the description route on the examples as an experiment before relying on it.

## 7. Building the timeline (step 5)

- Each detector reports stretches of time with a confidence value.
- A stretch is kept only if its confidence is above a threshold. Thresholds start high, because a false alarm is worse than a missed event.
- Stretches from different detectors that overlap produce a combined label.
- Everything not covered by a kept stretch is `clear`.
- Very short gaps between two stretches of the same label are closed, so one event is not reported as several.

## 8. Settings

Values the user may want to tune are kept in one settings place with plain names, never scattered through the logic.

| Setting | Value | Meaning |
|---|---|---|
| Overtaken lead time | 3 seconds | How much earlier `overtaken` starts than the first sight of the other car |
| Confidence thresholds | to be set from the examples | How sure a detector must be before an event is reported |
| Analysis frame rate and size | to be set after speed tests | Trade-off between speed and accuracy |

## 9. Event type list

- A CSV file with two columns: `label` and `description`.
- Read at the start of every run.
- Only one small part of the module knows that the list is a CSV file. Replacing it with a database later means replacing that part only.

## 10. Starting the module

- **By hand:** a command that takes a folder or a list of video files.
- **From the main program:** a function that takes the same list and returns, per file, whether it succeeded and where the outputs are.
- Both use the same code underneath.

## 11. Measuring accuracy

- The hand-made events files are the reference (one exists, two more are promised).
- A comparison tool lines up the module's events file with the reference and counts, per label: correct detections (within 5 seconds), false alarms, and missed events.
- Every change to a detector is judged by these counts, with false alarms weighted most.
- Limitation: three videos are few. Results will be indicative, not statistical proof. `held up` has no example yet.

## 12. Version control

The project is kept in a **Git repository**, so every change is recorded and can be undone.

- The repository is created in the project folder before the first code is written. Git and GitHub Desktop are already installed on the PC.
- **In the repository:** the two specification documents, the code, the event type list (CSV), the settings, and the small reference files (events files and GPX files).
- **Not in the repository:** video files. One example video is 5.3 GB, far too large for Git. Videos are excluded by an ignore rule and stay only on the disk.
- Each step in the order of work below ends with a commit, so the history follows the plan and shows what changed at each step.
- The repository is published to **GitHub as a public repository** (decided by the user).

Because it is public, anyone can read everything in it. Consequences:

- Nothing private goes into the repository: no passwords or keys, no personal data, no absolute paths from this PC.
- **One example is published** (decided by the user): its events file and GPX file are in the repository. Its video is not; the video is on the user's YouTube channel and the repository only gives the link to it.
- All other examples and reference files stay on this PC and are excluded from the repository.
- **Name:** `PP-TT-video` (decided by the user, to match the name of another module of the larger program that is already on GitHub).
- **Licence:** MIT (decided by the user).
- **README** (content decided by the user):
  - the goal of the project;
  - a block diagram of the solution, following the steps in section 4;
  - links to both specifications (`BUSINESS_SPEC.md` and `TECHNICAL_SPEC.md`);
  - the link to the example video on YouTube, added once the video is uploaded;
  - a note that the project is not affiliated with GoPro (proposed).
- The block diagram is written as a Mermaid diagram inside the README (proposed). GitHub draws Mermaid diagrams automatically, and the diagram stays editable as text instead of being a picture file.

## 13. Proposed order of work

0. Create the Git repository with the two specification documents and the ignore rule for videos.
1. Locate Python; check that ExifTool and ffmpeg run from the `executables` folder (done for the tools).
2. GPS extraction, checked against the reference GPX file.
3. Events file writer and the comparison tool.
4. Check which sensor data the example file contains.
5. Video reduction and a speed measurement.
6. Car tracking: `overtaking`, `overtaken`, `held up`.
7. `sliding` and `offtrack`.
8. `warm up` and `cooling`.
9. `obstacle`, `other event`, and the description experiment.

Each step ends with something that can be run and checked, so the user can follow and learn step by step.

## 14. Open technical questions

1. Do the libraries we need (video reading, detection on the graphics card) already support Python 3.15? Until checked, the project stays on 3.13.
2. Does the example file contain gyroscope and accelerometer data?
3. May Python libraries be installed on this PC?
4. How fast does the reduced video decode on this graphics card?
5. Which example is the published one, and what is the YouTube link to its video? (Video not uploaded yet.)
