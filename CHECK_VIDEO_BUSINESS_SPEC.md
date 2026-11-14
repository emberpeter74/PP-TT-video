# Check video: business specification

Status: draft for the author's approval. Items marked **(assumption)** are the assistant's proposals and wait for the author to confirm or correct them.

This document says **what** the check video must do. **How** it is built is in `CHECK_VIDEO_TECHNICAL_SPEC.md`. The module itself is described in `BUSINESS_SPEC.md` and `TECHNICAL_SPEC.md`.

## 1. Purpose

The module works on the three example videos, but on other footage its results are poor. The events file only shows the final answer, not how the module got there.

The check video makes the work behind the answer visible. It is the module's normal video, made smaller, with the following drawn over it: what the module saw (the cars it found), what it measured (the sensor values its rules look at) and what it decided (the events). Watching it, the author can see where a rule goes wrong: a car that was not found, a threshold that is never reached, an event that was found and then thrown away.

It is a **tool for checking and tuning the module**. It is not meant for reviewing the driving, and it is not used by the larger program.

## 2. How it is used

- The check video is **an option of the existing command line tool**. The command line tool stays as it is; without the option it behaves exactly as now.
- The author runs the tool with the option, waits until the video is done, and watches the check video in any video player.
- What is drawn can be chosen in a **separate settings file** with an explanation for every setting (section 6).

Decided by the author:

- The check video is made by the command line tool; there is no separate program with buttons. **(The author chose this as the simplest way.)** Two wishes from the first discussion are dropped for now, on purpose: choosing a video and starting the analysis from a window, and watching while the analysis runs. They can be added later if they are missed.
- The sensor readings are drawn **into the video**, in a strip below the picture, so a spike and what caused it are seen at the same moment.
- The picture is the reduced size the module already works with; the full 5.3K picture is not needed.
- The sensor data is also written to **its own file**, separate from the GPX file (section 5).

## 3. What the check video shows

### 3.1 The picture

- The video, reduced to the width the module analyses (1280 pixels), with sound **(assumption: sound kept, because tyre noise and kerbs help to judge a moment)**.
- A **box around every car** the module kept, with:
  - the car's track number (the same car keeps its number while it is followed),
  - the model's confidence, from 0 to 1,
  - how tall the car appears, as a part of the picture height: this is the value the car rules decide on.
- The box colour shows how the car rules see the car at that moment: far, close (counts towards `held up`), or passing (counts towards `overtaking` or `overtaken`).
- **Boxes the module threw away**, drawn differently (thin, grey), with the reason: too wide (the own cockpit), a double box around the same car, or a car the model was never sure enough of. **(Assumption: shown by default, because "what was thrown away" is exactly what the author needs to see; can be switched off.)**
- Boxes exist for 5 pictures per second, the video has 30. At first a box stays where it is until the next one is known. If that looks too jumpy, the box can be moved smoothly between the two (a setting). **(Decided by the author: look first, smooth if needed.)**

### 3.2 The events

- Across the top of the picture: the label or labels that apply at this moment, as the module would write them in the events file.
- **Events that were found but thrown away** are shown too, crossed out or grey, with the reason (for example: "sliding, dropped: outside the part at pace"). **(Assumption, same reason as the thrown-away boxes.)**
- The check video always shows what the **current** rules decide. If the events file was written earlier, with other settings, or was corrected by hand, the two can differ. The events file is never changed by making a check video.

### 3.3 The sensor strip

Below the picture, a strip with moving charts of the sensor values around the current moment (a few seconds before and after, with a line at "now"). Each chart shows the value a rule looks at, with the rule's threshold drawn as a line, so it is visible whether and when the threshold is crossed:

| Chart | Rule it belongs to |
|---|---|
| Braking and accelerating force, and the pace effort | `warm up`, `cooling`, the part at pace |
| Cornering force and turning rate | `sliding` |
| Shake (how hard the car shakes up and down) | `offtrack` |

Which charts are shown is a setting.

### 3.4 The profile

Decided by the author: the check video is drawn **with the driver and car profile** the module used for that video (business spec section 3, "Driver and car profile").

- The profile's name is shown on every picture, for example "profile: son", or "profile: built-in values" when there is none.
- **Every threshold that is drawn is the profile's value**: the threshold lines in the sensor strip and in the overview picture, and the car sizes behind the box colours (far, close, passing). The rules decide with the profile's values, so the pictures must show the same ones.
- The saved detections do not depend on the profile. So the same video can be drawn again with another profile in minutes, without the slow detection, to compare two profiles.

### 3.5 The overview picture **(assumption)**

Some problems only show over the whole video, not in a few seconds. The four new videos that came out as one long `warm up` are an example: the pace rule never fired anywhere. So besides the video, the tool writes **one picture of the whole video**:

- the pace effort over time, with its thresholds,
- the large parts (out of session, warm up, at pace, cooling, crash) as coloured bands,
- the events, kept and thrown away, as bars,
- the tracked cars as bars,
- the name of the profile used.

The author did not ask for this. It is proposed because the moving strip shows only a few seconds at a time.

## 4. Goals, non-goals, anti-goals

Goals:

- See, for any moment, what the module saw, measured and decided.
- See why a whole video went wrong (the overview picture).
- Change what is drawn without changing code.

Non-goals (not now):

- A window with buttons, choosing files, starting the analysis.
- Watching while the analysis runs.
- Editing events from the video.
- Showing the full 5.3K picture.
- Anything for the larger program: the check video is for the author only.

Anti-goals (would make it a failure even if it works):

- **The check video changes the results.** With or without the option, the events file and the GPX file must be exactly the same.
- **The normal run gets slower or breaks.** Without the option nothing extra is done.
- **The pictures show something other than what the rules use.** A threshold line that does not match the rule's real threshold would mislead. The charts must take their values and thresholds from the rules themselves.

## 5. The sensor data file

- Every video gets a sensor data file next to its GPX file: `name-sensors.csv`. **(Assumption: written always, like the GPX file, also with `--gps-only`, because reading the sensors takes only seconds.)**
- It is a plain table that opens in Excel: one row per measurement (about 200 per second), with the time in the video, the three acceleration values and the three rotation values, exactly as the camera stored them.
- The raw values are kept on purpose: the rules assume the camera is mounted in a certain way (which axis points forward). If the other footage was filmed with the camera mounted differently, only the raw values will show it.
- Like the other files, it is skipped when it already exists, unless `--overwrite` is given.
- This is a new output of the module and is added to section 6 of `BUSINESS_SPEC.md` when it is built.

## 6. The settings file

- A separate file holds only the settings of the check video. Every setting has a comment that says what it does and what values it takes.
- It covers at least: which layers are drawn (kept boxes, thrown-away boxes, box details, events, thrown-away events, the strip, each chart, the threshold lines), how many seconds the strip shows, how tall the strip is, the frame rate of the check video, box smoothing on or off, and whether the overview picture is written.
- The rules' own thresholds are **not** in this file. They stay in the module's settings and the driver and car profile, so the pictures always show the thresholds the rules really use.

## 7. Output files

For a video `name.MP4`, with the option:

| File | What it is |
|---|---|
| `name-check.mp4` | The check video |
| `name-overview.png` | The overview picture |
| `name-detections.json` | The cars found in every analysed picture, kept so the check video can be drawn again without the slow detection |

Without the option, only `name-sensors.csv` is new (section 5).

All are written to the same folder as the other output files and skipped when they exist, unless `--overwrite` is given.

## 8. Place in the order of work

The check video is built **before step 9** (`obstacle`, `other event`), after the driver and car profiles. The reason: the rules already built fail on other footage, and that has to be understood before more rules are added.

## 9. Open questions

1. The assumptions marked above: sound kept, thrown-away boxes and events shown by default, the overview picture, the sensor file written always.
2. The file names in section 7.
