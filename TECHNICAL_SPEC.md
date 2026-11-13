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

Python libraries, installed in a virtual environment `.venv` inside the project (not in Git) and listed in `requirements.txt`:

| Library | Version | Needed for |
|---|---|---|
| PyTorch | 2.15.0, build for CUDA 13.4 | Running detection models on the graphics card |
| torchvision | 0.29.2 | Ready-made, pre-trained detection models |
| NumPy | 2.5.4 (installed with PyTorch) | Handling pictures as tables of numbers |

All three are under BSD-style licences, compatible with this project's MIT licence. The project is run with the environment's Python: `.venv\Scripts\python.exe`.

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

- Decode with the graphics card, scale down to 1280 pixels wide, and analyse 10 frames per second.
- A tolerance of 5 seconds and events lasting 2 seconds or more make this safe.

### Speed measurement (result of step 5)

Measured on the 12-17 example (6:27 long, 5312x2988) on the RTX 3060 Ti:

| Method | Time | Speed |
|---|---|---|
| Graphics card, reduced to 1280x720, 10 frames per second | 53 s | 7.3 times real time |
| Graphics card, reduced to 640x360, 10 frames per second | 53 s | 7.3 times real time |
| Graphics card, 1280x720, all 30 frames per second | 53 s | 7.3 times real time |
| Processor only, 1280x720, 10 frames per second | 34 s per minute of video | 1.8 times real time |
| Processor only, one picture per second (key frames) | 38 s | 10.3 times real time |

What this means:

- **The graphics card is four times faster than the processor** and is used by default. A setting switches to the processor on a PC without an Nvidia card.
- **The output size and frame rate do not change the decoding time.** The camera's pictures build on each other, so every one of them must be decoded even if only a few are kept. The limit is the graphics card's decoder, which was fully busy during the test. Size and frame rate can therefore be chosen for what detection needs.
- **One picture per second is not worth it.** It is only a little faster and too coarse for events that last two seconds.
- **A day's footage:** 20 files of about 13 minutes are about 260 minutes of video, which decode in about 36 minutes. Detection comes on top and is not measured yet, but the business requirement of "a few hours" has plenty of room.
- Reading the video through Python (`pp_tt_video/video.py`) is as fast as ffmpeg alone: 7.3 times real time.

### What the picture looks like

The camera sits behind the driver in an open-top car and looks forward with a very wide angle:

- The road ahead fills only a small band in the middle of the picture. The lower half is dashboard and interior, the top is sky and the windscreen frame, and the driver's helmet covers part of the left side.
- A car 20 to 30 metres ahead is only about 60 pixels wide in the 1280-pixel picture.
- Because the car is open, the areas beside it are visible to the left and right of the windscreen frame. That is where a car alongside appears.

Consequence for step 6: shrinking the whole picture wastes most of the pixels on interior and sky.

### The view moves relative to the car (found at the start of step 6)

Frames from the 12-17 example, a few seconds apart, show the cockpit in clearly different places in the picture: the windscreen frame tilts and shifts, and the driver's helmet is sometimes at the left edge, sometimes fills a third of the picture, sometimes is out of view. The camera's view is therefore not fixed to the car.

**Cause: the camera's stabilisation (HyperSmooth) was switched on** (confirmed by the user). Stabilisation keeps the outside world steady in the picture. When the car turns, leans or bounces, the camera compensates by shifting and rotating the picture, so the cockpit appears to move instead. It also cuts away part of the picture's edge to have room for this.

- The examples were recorded this way, so the module must cope with it.
- **Mount:** the camera is fixed to the car's roll bar with GoPro's own mount (confirmed by the user), so it moves with the car.
- The motion sensors are not affected by stabilisation: they record the raw movement of the camera body. With the rigid mount they therefore measure the car's movement, plus whatever vibration the mount adds.
- Suggestion for future recordings (the user's decision): with stabilisation off and the camera fixed to the car, the cockpit stays in one place, the road region could be cut out and enlarged, and the picture is wider. The module must still handle recordings made with stabilisation on.

Consequences:

- **No fixed cut-out.** A fixed region of the picture cannot be assumed to show the road. The detector must either look at the whole picture or find the windscreen in each picture.
- **Positions in the picture are unreliable.** "The other car moved from the centre to the left" may be the camera turning, not the car moving. The detector should rely on things that do not depend on where the camera points, mainly how the size of another car changes over time: a car that grows and then disappears was caught and passed; a car that appears large and then shrinks has passed us.
- **The motion sensors may not measure the car.** If the camera moves relative to the car, its gyroscope and accelerometer record the camera's motion, not only the car's. This may be why the slide did not stand out in step 4, and it must be settled before step 7.

What the known events look like:

- `overtaken` (01:02 to 01:15): nothing is visible ahead until about 01:07; by 01:11 a car that has passed is close ahead on the right. Just before, it is visible only in the door mirror, a few pixels wide.
- `overtaking` (02:00 to 02:09): a car is small in the distance at 01:59, close alongside on the left at 02:02, and gone at 02:05.

### Signals available in a GoPro file

| Signal | Useful for | State |
|---|---|---|
| Picture | Other cars, obstacles, road surface | Available |
| Sound | Tyre squeal (sliding), engine load (warm up, cooling) | Available |
| Gyroscope and accelerometer | Sliding, off-track vibration, speed changes | **Verified:** present in all three examples, for the whole video |
| GPS speed | Warm up, cooling, and as a help for sliding | Present, but only usable while the camera has a satellite fix |

The motion sensors matter: unlike the GPS, they do not need a satellite fix, so they are valid for the whole video.

### What the example files contain (result of step 4)

All sensor data sits in one data track of the MP4 (GoPro's metadata track), stored in blocks of one second. ExifTool reads it with the `-ee` option, the same way it reads the GPS.

| Data | Rate | Notes |
|---|---|---|
| Accelerometer | about 200 values per second, 3 axes, in m/s² | One axis points down (reads about 9.8, gravity), one sideways (above 10 in fast corners), one along the car |
| Gyroscope | about 200 values per second, 3 axes | How fast the car rotates around each axis |
| Gravity vector | 30 per second | Which way is down, computed by the camera |
| Camera orientation | 30 per second | How the camera is turned in space |
| GPS position and speed | 10 per second | Speed in km/h; each point carries a flag saying whether the camera had a fix |
| Sound level | about 10 per second | A coarse loudness value, separate from the sound track |
| Other | once per second or less | Exposure, colour, camera temperature and similar; not needed |

GPS fix per example, read from the camera's own fix flag:

| Example | Points with a fix | Meaning |
|---|---|---|
| 09-41 (first session of the day) | 55 of 7873 | Almost no usable GPS |
| 10-32 | all 6248 | GPS speed usable for the whole video |
| 12-17 | all 3871 | GPS speed usable for the whole video |

So the GPS is poor only while the camera is still searching for satellites, which mainly hits the first recording of the day. The fix flag tells the module when GPS speed can be trusted. It is a help where available, never something a detector may depend on.

First look at a known event: the slide at 04:53 in the 12-17 example does **not** stand out in simple per-second maximum values. Clear driving over kerbs produces equally large rotation and vibration. A plain threshold will therefore not work for `sliding`; the detector must compare signals, for example how fast the car turns against how hard it is cornering and how fast it is going. This is work for step 7.

### First detection experiment (step 6)

Two ready-made models from torchvision, both trained to find everyday objects including cars, were run on the two known events in the 12-17 example, on pictures reduced to 1280x720.

| Model | Speed | Result |
|---|---|---|
| Faster R-CNN, MobileNet (small, fast) | 26 pictures per second | Finds the real cars, but also reports the cockpit as a "motorcycle" and the interior mirror as a "car" in most pictures. Too many false detections. |
| Faster R-CNN, ResNet-50 v2 (larger, slower) | 10 pictures per second | Finds the real cars with a confidence of 0.95 to 1.00. False detections are rare and have low confidence. **Chosen.** |

What the chosen model sees in the known events:

- `overtaking` (reference 02:00 to 02:09): one car followed without a gap from 01:57 to 02:02. Its width in the picture goes 98, 73, 54, 72, 103, 146, 190 pixels, then it is gone. Growing and then gone: caught and passed.
- `overtaken` (reference 01:02 to 01:15): from 01:02 to 01:03.5 a car is detected **inside the door mirror**, which is the car coming from behind. At 01:10 a car appears at the right edge 269 pixels wide and shrinks: 215, 116, 82, 74, 58. Appearing large and then shrinking: it has passed. The hand-marked start of 01:02 matches the moment the car shows in the mirror.

Consequences for the design:

- A simple confidence limit (about 0.9) separates real cars from false detections.
- Very small detections (under about 40 pixels wide) are distant cars on other parts of the track. They come and go and are ignored.
- The door mirror gives an early sign of a car behind. It is used as supporting evidence only, since the mirror moves in the picture and is small.
- Speed: at 10 pictures per second, detection runs at about real time, which would make a full day's footage take over four hours. Analysing 5 pictures per second halves that and is still fine for events lasting two seconds or more. Faster settings of the model are to be tried.

### Car tracking as built (result of step 6)

Four parts, each in its own file:

| Part | File | What it does |
|---|---|---|
| Detector | `detect_cars.py` | Runs the model on 5 pictures per second and returns a box around every car, truck or bus it finds |
| Tracker | `tracking.py` | Links the boxes from picture to picture, so each car has a history |
| Rules | `car_events.py` | Turns each car's history into `overtaking`, `overtaken` or `held up` |
| Timeline | `timeline.py` | Fills the gaps with `clear`, combines overlapping labels, rounds to whole seconds |

**Height, not width.** The rules use how tall another car looks. Width was tried first and failed: a car seen from the side in a corner is more than twice as wide as the same car seen from behind, so its width jumps around while its distance does not change. Height stays steady.

The rules, with heights as a part of the picture's height:

| Event | Rule |
|---|---|
| `overtaking` | The car is taller than 0.11 of the picture (it is right next to us) and then vanishes while that large, and it was already being followed before it got that large. Starts where its final growth began. |
| `overtaken` | The car is taller than 0.11 of the picture from the first moment it is seen, and then shrinks. Starts 3 seconds before it appears; ends where it has shrunk to half. |
| `held up` | The car stays taller than 0.0625 of the picture for at least 3 seconds, outside of a pass. |
| nothing | A car that stays smaller than that (a quicker car ahead), a car seen large in only one picture, a car seen large from first to last sighting, a car the model was never at least 0.9 sure about. |

All values are in `settings.py`.

**Speed:** decoding and detection together run at about 3 times real time. A day's footage (about 260 minutes) takes about 90 minutes.

**Scores against the hand-made files.** Counted only for the part of each video driven at pace (after `warm up`, before `cooling` or `crash`):

| Example | Real events found | Missed | Extra detections |
|---|---|---|---|
| 12-17 | 4 of 4 (overtaken, 2 overtaking, held up) | 0 | 0 |
| 10-32 | 4 of 5 (overtaken, 3 overtaking) | 1 (held up) | 1 (held up) |
| 09-41 | 2 of 2 (2 overtaking) | 0 | 4 |

Notes on these numbers:

- **The four extra detections in 09-41 are real cars.** Pictures at each of those moments (02:54, 03:35 to 03:40, 04:05, 10:34 to 10:38) show another car close ahead. The hand-made file for this session does not mention them. Whether they are events the reference lacks, or situations that should stay `clear`, is for the user to say.
- **The missed `held up` in 10-32** is a car that the user marked as holding them up while it was still small in the picture (0.045 to 0.055 of the picture's height). At that size the 12-17 example has a car ahead that the user marked as `clear`. Size alone cannot tell these two apart, so the rule stays on the cautious side.
- **The extra `held up` in 10-32** is the car that has just overtaken: it stays close ahead for five seconds before pulling away.
- Three videos are too few to call this accurate. The numbers show the method works in principle.

**Not solved in this step: the pit lane.** Outside the part driven at pace the rules produce many wrong events: parked cars passed slowly in the paddock read as `overtaking`, cars driving past while standing still read as `overtaken` (in 12-17, after the breakdown). Over the three whole videos that is about 20 wrong events. They disappear once the module knows when the car is not driving at pace, which is step 8 (`warm up` and `cooling`). **Until then the events files are not usable outside the at-pace part.** It may be worth doing step 8 before step 7.

**Tried and dropped: the door mirror.** The model does find the overtaking car in the door mirror seconds before it comes alongside, but the mirror is too small and moves too much in the stabilised picture for a reliable rule. The fixed 3-second lead before the car appears is used instead.

### Proposed method per event type

| Label | Proposed method | Confidence in the method |
|---|---|---|
| `overtaking` | **Built in step 6** (see above): a tracked car grows and then vanishes while large. | Good on the examples |
| `overtaken` | **Built in step 6:** a tracked car appears large and then shrinks. Start time is moved 3 seconds earlier. | Good on the examples |
| `held up` | **Built in step 6:** a tracked car stays close ahead for at least 3 seconds. | Medium: size alone does not always match the user's judgement |
| `sliding` | Gyroscope and accelerometer together: the car turns faster than its cornering force and speed explain. Supported by tyre sound. A simple threshold on one signal is not enough (see step 4 result). | Medium; sensor data is confirmed, the method is not |
| `offtrack` | Accelerometer: strong vibration typical of grass or gravel. Supported by the picture: the surface under the car is not tarmac. | Medium |
| `warm up`, `cooling` | GPS speed where the camera has a fix; otherwise an estimate of pace from engine sound, vibration and picture motion. First and last sustained stretch at low pace. | Medium; the business specification accepts leaving these out |
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

## 14. Ideas for a later phase

Noted here so they are not lost. None of this is part of the current plan.

### Use RaceBox Mini data for detection

Idea from the user: in a later phase, read the RaceBox Mini recording of the same session, synchronise it with the video, and use it as a signal for detection.

- The RaceBox Mini records at 25 values per second and is more accurate than the GoPro GPS in every respect. Unlike the GoPro GPS, it does not depend on the camera having found satellites.
- It would give reliable speed and position for the whole video. That helps `warm up` and `cooling` directly, and `sliding` and `offtrack` through the comparison of speed, turning and cornering force.
- It changes the module's boundary. The business specification currently says that synchronising with RaceBox Mini data belongs to other modules. If this idea is taken up, that boundary must be decided again there first.
- Until then the detectors are built to work from the GoPro file alone, so RaceBox data can later be added as an extra signal without redesigning them.

## 15. Open technical questions

1. Do the libraries we need (video reading, detection on the graphics card) already support Python 3.15? Until checked, the project stays on 3.13.
2. May Python libraries be installed on this PC?
3. Will future recordings be made with stabilisation off?
4. Which signal combination separates a slide from driving over a kerb?
5. Which example is the published one, and what is the YouTube link to its video? (Video not uploaded yet.)
