# Trackday footage analysis module: technical specification

Status: steps 0 to 8 of the order of work (section 13) are built, plus `out of session` and a first rule for `crash`. Sections marked "as built" or "result of step" describe what exists; the rest is still a proposal.

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

- **The four extra detections in 09-41 are real overtakes** (confirmed by the user, who left them out of the hand-made file on purpose, as a test). Against what really happened, the module's result for them is:

  | Moment | What happened | What the module reports |
  |---|---|---|
  | 02:54 | overtaking | `overtaking`: correct |
  | 03:35 to 03:40 | sliding and overtaking | `held up` from 03:35, `overtaking` from 03:38: the overtake is correct; the `held up` before it is a judgement call |
  | 04:05 | overtaking | Nothing: **missed**. The car is seen large in only one picture, and the rule that guards against one-picture glitches drops it. An earlier version of the rules, without that guard, found it. |
  | 10:34 to 10:38 | overtaking | `held up`: **wrong label**. The car is close for 4 seconds, but the pass itself is not recognised. |

  So of 11 real overtakes in the three examples (`overtaking` and `overtaken`), 9 are found, 1 is missed and 1 is reported as `held up`. The two failures are the next things to improve in the car rules. The hand-made events file for 09-41 does not contain these four overtakes yet; until it does, the comparison tool counts them as false alarms.
- **The missed `held up` in 10-32** is a car that the user marked as holding them up while it was still small in the picture (0.045 to 0.055 of the picture's height). At that size the 12-17 example has a car ahead that the user marked as `clear`. Size alone cannot tell these two apart, so the rule stays on the cautious side.
- **The extra `held up` in 10-32** is the car that has just overtaken: it stays close ahead for five seconds before pulling away.
- Three videos are too few to call this accurate. The numbers show the method works in principle.

**Not solved in this step: the pit lane.** Outside the part driven at pace the rules produce many wrong events: parked cars passed slowly in the paddock read as `overtaking`, cars driving past while standing still read as `overtaken` (in 12-17, after the breakdown). Over the three whole videos that is about 20 wrong events. **Solved in step 8:** car events during `warm up` and `cooling` are dropped (see "Warm up and cooling as built").

**Tried and dropped: the door mirror.** The model does find the overtaking car in the door mirror seconds before it comes alongside, but the mirror is too small and moves too much in the stabilised picture for a reliable rule. The fixed 3-second lead before the car appears is used instead.

### Reading the motion sensors (built in step 8)

`sensors.py` runs ExifTool once per video with the print format `pp_tt_video/sensors.fmt` and gets, for every one-second block, about 200 accelerometer and 200 gyroscope measurements. This takes about 5 seconds per video, against minutes for the pictures.

Which of the three numbers of a measurement means what was read from the examples and is kept in `settings.py`:

| Sensor | Number | Meaning | How it was recognised |
|---|---|---|---|
| Accelerometer | 0 | Down | Reads about -9.8 m/s² when the car stands still: gravity |
| Accelerometer | 1 | Sideways: cornering force | Up to 12 m/s² in corners, same sign as the turning |
| Accelerometer | 2 | Along the car: plus when braking, minus when accelerating | Plus while the GPS speed falls |
| Gyroscope | 0 | Turning left or right | Follows the cornering force |

This holds for a camera standing upright and looking forward (assumption: all recordings are made this way). A camera mounted differently needs other values in the settings.

Averaging the 200 measurements of a second removes the vibration of engine and road, which is several times larger than the forces of driving.

### Warm up and cooling as built (result of step 8)

**Speed does not work.** In the 10-32 example, where the GPS is good, the laps at pace run between 56 and 118 km/h and the cool-down lap between 52 and 90 km/h. The cornering force does not work either: the cool-down lap still has corners at 11 m/s².

**Braking and accelerating does.** At pace the force along the car swings between about +5 (braking) and -4 m/s² (accelerating) every few seconds; on a slow lap it stays within about ±2.5. The rule in `pace.py`:

1. Per second: the average force along the car, without its sign.
2. "Effort": the average of that over 40 seconds around each second. At pace it is 1.5 to 2.7, on slow laps 0.4 to 1.3. The car is at pace where the effort is at least 1.3, for at least 20 seconds.
3. The part at pace runs from the start of the first such stretch to the end of the last. Slow moments in between stay inside it.
4. The 40-second average blurs the edges, so each edge is moved inward to the first or last second with a force of at least 3.0 m/s².
5. An edge closer than 10 seconds to the start or end of the video means the video starts or ends at pace.
6. Before the part is `warm up`, after it `cooling`. Car events that fall into either are dropped. (Since then refined by `session.py`, see "Out of session and crash as built".)

All values are in `settings.py`.

Result on the examples:

| Example | Hand-made file | Module |
|---|---|---|
| 09-41 | `warm up` until 01:44, `cooling` from 11:20 | `warm up` until 01:39, `cooling` from 11:22 |
| 10-32 | no `warm up`, `cooling` from 07:36 | no `warm up`, `cooling` from 07:35 |
| 12-17 | no `warm up`, `crash` from 05:00 | no `warm up`, `cooling` from 05:02 |

All within the tolerance of 5 seconds. The roughly 20 wrong car events in the pit lane and paddock are gone; the car events at pace are unchanged from step 6. In 12-17 the label is wrong (`cooling` instead of `crash`) because `crash` is not detected yet; the moment is right.

Limits:

- The values were set on three videos from one day, one car and one driver. Another car or a wet track may need other values.
- The GPS speed is not used at all, so the rule behaves the same with and without a satellite fix.
- A video without sensor data gets no `warm up` or `cooling`; the car rules then run over the whole video as before.

### Sliding and offtrack as built (result of step 7)

Both come from the motion sensors alone, so they cost almost no time and do not depend on the stabilised picture. Both are dropped during `warm up` and `cooling`, like the car events.

**Sliding (`sliding.py`): the catch.** In a normal corner the cornering force and the turning go together. When the rear steps out and the driver steers against it, the car is for a moment still pushed sideways as hard as before but has stopped turning into the corner, or turns the other way. Example, 10-32 at 06:43: the cornering force stays at about 10 m/s² while the turning rate goes from -0.8 to +0.6 radians per second within 0.8 seconds. A kerb or a chicane does not do this: there force and turning change together. This answers open question 4.

The rule, looking 10 times per second:

1. The cornering force is at least 7 m/s².
2. The car turns against the corner.
3. Within the second before, it turned into the corner at 0.4 radians per second or more.
4. This holds in at least 2 samples close together.
5. `sliding` starts 2 seconds before the catch and ends with it.

**Offtrack (`offtrack.py`): shaking.** The "shake" is how much the up-and-down force jumps around within a fifth of a second (its standard deviation). On the track it is about 2.5 m/s², on a kerb 5 to 6, on grass or gravel 9 to 13. The rule: a shake of at least 7 for at least 1 second. `offtrack` starts 1.5 seconds before the shaking and ends 0.5 seconds after it.

All values are in `settings.py`.

Result on the examples, at pace:

| Example | Marked by hand | Found | Missed | Extra |
|---|---|---|---|---|
| 09-41 | 4 sliding, 2 offtrack | 4 sliding, 1 offtrack (11:15) | offtrack at 02:31 | sliding at 02:47 |
| 10-32 | 4 sliding | 4 sliding | none | none |
| 12-17 | 2 sliding | 2 sliding | none | none |

Notes:

- **All 10 marked slides are found**, each within 2 seconds of the marked start.
- **The extra slide at 02:47 in 09-41** shows the same catch as the others, only shorter. Whether it is a real slide the hand-made file leaves out is for the user to check in the video.
- **The missed offtrack at 02:31 in 09-41** shakes the car at 5 to 7 m/s² for about a second, which is what a kerb does. Lowering the limit to catch it would report kerbs in all three videos. It stays missed: a false alarm is worse than a missed event. The picture (grass under the car) may be able to tell them apart later.
- **In 12-17 the hand-made file has `sliding` from 02:49 to 03:11**, 22 seconds, directly followed by `held up`. The module reports the slide from 02:48 to 02:51 and `clear` after it. The comparison tool counts this as found.
- The paddock and the pit lane shake the car as much as grass does (three places in 09-41, one in 10-32). They fall into `warm up` or `cooling` and are dropped there.

Limits:

- Only slides that are caught with a quick steering correction are found. A car that slowly pushes wide over its front wheels shows no catch.
- The values come from one day, one car and one driver on a dry track.
- The sound (tyre squeal) is not used; the sensors proved enough on the examples.

### Out of session and crash as built (after step 7)

`session.py` divides a video into its large parts, in this order: `out of session`, `warm up`, the part at pace, `cooling` (or `crash`), `out of session`. The part at pace still comes from `pace.py`; the rest is new. Any part can be missing: a video may start on the track or end before the car leaves it (stated by the user).

**Start: has the car joined the track yet?**

1. A sign is needed that the car is not on the track at the start of the video: it is slower than 45 km/h in the first 15 seconds. The slowest corners of the track are above 50 km/h.
2. The speed comes from the GPS when the camera has a fix (10-32: 35 km/h, 12-17: 24 km/h). Without a fix it is worked out in the first turn: cornering force divided by turning rate (09-41: 3.0 m/s² at 0.44 radians per second is 25 km/h). The turn must be at least 0.3 radians per second for this to be trusted.
3. Without such a sign the video is taken to start on the track: no `out of session`.
4. With it, `out of session` lasts until the first acceleration onto the track is over: the car accelerates with at least 2 m/s², and the part ends when that drops below 1 m/s².
5. Braking with 2 m/s² or more before that acceleration means the car is on the track already: no `out of session`.

**End: has the car left the track?**

1. The video must end with the car standing still for at least 3 seconds. Standing still is read from the shake (below 1.0 m/s²; driving, even slowly, shakes the car more). If the video ends while the car moves, the last part simply runs to the end.
2. `out of session` starts 10 seconds after the last real corner (cornering force of 5 m/s² or more) before that standstill. The turns of the pit lane and paddock stay below 3.5 m/s² in the examples.

**Crash.** If the car stands still less than 60 seconds after it stopped driving at pace, there was no cool-down lap. Everything after the part at pace is then `crash`, with no `cooling` and no `out of session` (decided by the user).

| Example | Pace ends | Car stands still | Seconds between | Result |
|---|---|---|---|---|
| 09-41 | 11:20 | 12:50 | 90 | `cooling`, then `out of session` |
| 10-32 | 07:34 | 09:14 | 100 | `cooling`, then `out of session` |
| 12-17 | 05:01 | 05:37 | 36 | `crash` |

**Events are only kept in the part at pace.** Everything a detector reports during `out of session`, `warm up`, `cooling` or `crash` is dropped.

Result on the examples, against the times the user marked:

| Example | Marked by hand | Module |
|---|---|---|
| 09-41 | `out of session` until 00:17 and from 12:38 | until 00:18 and from 12:38 |
| 10-32 | `out of session` until 00:05 and from 08:44 | until 00:03 and from 08:45 |
| 12-17 | `out of session` until 00:06, `crash` from 05:00 | until 00:08, `crash` from 05:02 |

All within the tolerance of 5 seconds.

Limits:

- **Fitted on three videos.** The 10 seconds after the last corner come from two examples; the 60 seconds for a crash separate 36 from 90. Another track, with a longer pit lane or a corner in it, will need other values.
- **A false `crash`:** driving straight from a fast lap into the pits and parking within a minute looks the same as a breakdown (risk accepted by the user).
- **A collision after which the car drives on** is not detected.
- **A video that starts in the pit lane while already rolling straight**, without GPS fix, shows no sign of being off the track and gets no `out of session` at its start.
- All values are in `settings.py`.

### Proposed method per event type

| Label | Proposed method | Confidence in the method |
|---|---|---|
| `overtaking` | **Built in step 6** (see above): a tracked car grows and then vanishes while large. | Good on the examples |
| `overtaken` | **Built in step 6:** a tracked car appears large and then shrinks. Start time is moved 3 seconds earlier. | Good on the examples |
| `held up` | **Built in step 6:** a tracked car stays close ahead for at least 3 seconds. | Medium: size alone does not always match the user's judgement |
| `sliding` | **Built in step 7** (see above): the car keeps its cornering force but turns against the corner. | Good on the examples, for slides that are caught |
| `offtrack` | **Built in step 7:** hard up-and-down shaking for a second or more. The picture is not used yet. | Medium: finds clear cases, misses two wheels on the grass |
| `warm up`, `cooling` | **Built in step 8** (see above): how hard the car brakes and accelerates, from the accelerometer. Not from speed. | Good on the examples |
| `out of session` | **Built** (see above): slow at the start of the video until the car has accelerated onto the track; after the last real corner before the car parks. | Medium: fits the three examples, values are track-dependent |
| `crash` | **First rule built** (see above): the car stands still within a minute after driving at pace. Collisions after which the car drives on are open. | Medium: one example |
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

### Driver and car profiles (planned, before step 9)

What a profile is and how one is chosen is in section 3 of the business spec. Here: how it is built.

**Approaches considered:**

| Approach | For | Against |
|---|---|---|
| **A. The profile replaces values in `settings` while its videos are processed** | The rules stay untouched; only `pipeline.py` and a new `profile.py` change; the check video draws the profile's thresholds without extra work | The values change behind the rules' backs, so the defaults must always be put back |
| B. Every rule receives the profile as an input | Each function shows what it depends on | Touches every rule and most checks, for no new behaviour |

**Chosen by the user: A.** `settings` is a Python module, and its values can be changed while the program runs. The rules read them at the moment they run (for example `settings.PACE_MIN_EFFORT` inside `find_pace_part`), so a changed value takes effect at once.

This only works as long as every rule keeps reading `settings.NAME` when it runs. Checked when this was written: no file copies a profile value with `from pp_tt_video.settings import ...`, into a function's default value, or into another setting. New code must keep it that way. A copied value would keep the built-in number and silently ignore the profile.

**New files:**

- `pp_tt_video/profile.py`:
  - `find_profile(video, profile_option)`: returns the profile file for a video, or None for the built-in values. Order: the `--profile` option; then `profile.toml` in the video's folder; then none. A `--profile` value ending in `.toml` is a path to a file; any other value is a name and means `profiles/<name>.toml` in the project folder.
  - `load_profile(path)`: reads the file with `tomllib` (part of Python since 3.11, so nothing to install). A name that is not on the list of profile values, or a value that is not a number, stops the run for that video with a clear message. A typo must not be ignored silently, or the built-in value would be used without anyone noticing.
  - `using_profile(profile)`: a *context manager*, used as `with using_profile(profile): ...`. It sets the profile's values in `settings` when the block starts and puts the built-in values back when it ends, also when an error happens inside it.
- `pp_tt_video/make_profile.py`: the command `python -m pp_tt_video.make_profile "<folder>" [--name <name>] [--overwrite]`. Without `--name` it writes `profile.toml` into the folder, so the next run on that folder picks it up by itself. With `--name son` it writes `profiles/son.toml`. An existing file is not replaced without `--overwrite`.

**The list of profile values** (kept in `profile.py`):

| Value | Depends on | Made by `make_profile` |
|---|---|---|
| `PACE_MIN_EFFORT`, `PACE_HARD_FORCE` | the driver: how hard he brakes and accelerates | scaled by the braking ratio |
| `SLIDE_MIN_CORNERING_FORCE`, `SESSION_TRACK_CORNER_FORCE` | the driver: how hard he corners | scaled by the cornering ratio |
| `OFFTRACK_MIN_SHAKE`, `STANDSTILL_MAX_SHAKE` | the car: suspension, seat, mount | written with the built-in value, commented out, to be changed by hand |
| `PASSING_CAR_HEIGHT`, `CLOSE_CAR_HEIGHT`, `MAX_CAR_WIDTH_FRACTION` | the camera position and lens | the same |

**How `make_profile` measures** (sensors only, about 5 seconds per video):

- Braking level: the 95th percentile of the pace effort (`effort_per_second(forward_force_per_second(...))`), over all seconds of all videos in the folder. The 95th percentile is the value that 5% of the seconds exceed: a typical "hard" level that ignores the slow parts (paddock, warm up) as long as the driver is at pace for more than 5% of the footage, and is not thrown by a single spike.
- Cornering level: the 95th percentile of the sideways force per second, without its sign.
- The user's own levels are stored in `settings.py` as `REFERENCE_EFFORT` and `REFERENCE_CORNERING`, measured once from the three examples in step P2. A first measurement gave about 2.5 and 11.
- Ratio = driver's level / user's level; each driver value = built-in value × ratio. For the son's four videos the first measurement suggests a braking ratio of about 0.4 and a cornering ratio of about 0.55.
- The file records the measured levels, the ratios and the video names it was made from, as comments, so it can be seen later where the numbers came from.

An example of what `make_profile` writes:

```toml
# Driver and car profile, made by make_profile from 4 videos:
# GX010179.MP4, GX010180.MP4, GX010182.MP4, GX010183.MP4
# Braking level 0.98 (user: 2.50), ratio 0.39
# Cornering level 6.1 (user: 11.0), ratio 0.55

# --- Driver: scaled from the measurement above ---
# Average braking or accelerating force (m/s²) from which the car counts as at pace.
PACE_MIN_EFFORT = 0.51
# ...

# --- Car and camera: built-in values, remove the # to change one ---
# How hard the car must shake (m/s²) to count as off the track.
# OFFTRACK_MIN_SHAKE = 7.0
```

**In the pipeline:** for every video, `find_profile` and `load_profile` run first, then the detection (and the check video, when asked) runs inside `with using_profile(...)`. The GPS extraction, the sensor data file and the detections file do not depend on the profile. The line printed per video says which profile was used, for example `profile: son (profiles/son.toml)` or `profile: built-in values`.

**On the check video:** it is drawn inside the same `using_profile` block, so every threshold line in the sensor strip and the overview picture, and the car height limits behind the box colours, are the profile's values. The profile's name is written in a corner of every picture and on the overview. See `CHECK_VIDEO_TECHNICAL_SPEC.md`.

**Git:** the `profiles/` folder is ignored by Git **(assumption: profiles carry driver names, and the repository is public)**. A `profile.toml` in a video folder is outside Git anyway.

**Checks:**

- `find_profile`: the option wins over a folder file; a folder file is found; none gives None; a name and a path are both understood.
- `load_profile`: an unknown name and a non-number are refused with a clear message.
- `using_profile`: the values are set inside the block and the built-in ones are back afterwards, also after an error.
- `make_profile`: on made-up sensor data with known levels, the ratios and the scaled values are as expected; the written file can be read back by `load_profile`.
- Without any profile, the events files of the three examples are exactly as before.

## 9. Event type list

- A CSV file with two columns: `label` and `description`.
- Read at the start of every run.
- Only one small part of the module knows that the list is a CSV file. Replacing it with a database later means replacing that part only.

## 10. Starting the module

- **By hand:** a command that takes a folder or a list of video files.
- **From the main program:** a function that takes the same list and returns, per file, whether it succeeded and where the outputs are.
- Both use the same code underneath.

## 11. Measuring accuracy

- The hand-made events files are the reference. Each example has `name-events.original.txt`, exactly as the user wrote it, and `name-events.txt`, a cleaned copy in the agreed format. The comparison tool and the checks use the cleaned copy.
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
   - Added after step 7 at the user's wish: `out of session`, and a first rule for `crash`.
   - Added before step 9 at the user's wish, because the rules fail on other footage:
     - **P1.** Profiles: reading a profile file, choosing it (`--profile`, folder file, built-in values), applying it per video.
     - **P2.** The `make_profile` command, with the user's reference levels measured from the three examples.
     - **V1 to V7.** The check video, see `CHECK_VIDEO_TECHNICAL_SPEC.md`.
     - Profiles come first **(assumption)**: they are small, and on the son's four videos they show at once whether events appear at all. The check video then shows whether they are the right ones.
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
4. Which signal combination separates a slide from driving over a kerb? (Answered in step 7: cornering force against turning rate, see "Sliding and offtrack as built".)
5. Which example is the published one, and what is the YouTube link to its video? (Video not uploaded yet.)
