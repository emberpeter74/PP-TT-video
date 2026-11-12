# Trackday footage analysis module: business specification

Status: draft, updated from the example video and example output file. Open questions are in section 10.

This document says **what** the module must do. **How** it is built (language, tools, hardware, detection methods) is in `TECHNICAL_SPEC.md`.

## 1. Purpose

Analyse in-car GoPro footage from trackdays and report which parts of the footage show a **clear track** and where **events** happen, so the interesting moments can be found without watching hours of video.

## 2. Place in the larger program

- This is one module of a larger program that will be written over the coming months.
- A trackday consists of several sessions, and each session of any number of laps. Splitting footage into sessions and laps is done by **another module** and is not this module's concern.
- This module receives video and returns its findings as a text file. Other modules consume that file.
- Because other modules depend on it, the input and output must be clearly defined and stable (see sections 3 and 6).

## 3. Input

GoPro MP4 footage recorded from inside the user's race car, processed offline after the trackday.

- **Camera:** GoPro 13, forward view only. There is no rear camera, so a car approaching from behind becomes visible only once it is alongside or ahead.
- The module receives a **set of video files in one run**: in principle all GoPro files of a trackday. The set can be a single file or as many as 20.
- **Every file is handled separately.** Each video in the set gets its own GPX file and its own events file (section 6). The module does not join files, also not chapter files of one recording; that is left to other modules.
- The video's base name can be anything. `RaceBox Track Sessionon DD-MM-YYYY HH-MM` is only an example; the module must not depend on any naming pattern.
- One file failing must not stop the rest of the set from being processed (assumption, to confirm).

Reference input: `example video  and output file/RaceBox Track Sessionon 30-05-2026 09-41.MP4`

| Property | Value in the example |
|---|---|
| Length | 13:07 |
| File size | 5.3 GB |
| Video | H.265 (HEVC Main, level 6.0), 5312x2988, 29.97 fps, about 54 Mbit/s |
| Audio | AAC, 48 kHz, stereo, 189 kbit/s |

Notes:

- The footage has sound. Audio may help with some events (for example tyre noise while sliding); whether to use it is a design decision for later.
- The GoPro MP4 contains an embedded GPS track. The module must extract it (see section 6).
- The GoPro GPS is almost always poor: both the position fix and the camera's clock start late (see section 6). It is not used for event detection and not as position data in the larger program.
- The larger program takes its position and time data from a separate, more accurate GPS telemetry device, the **RaceBox Mini**.
- GoPro files may also carry accelerometer and gyroscope data. Not yet checked for the example.

## 4. What the module must detect

The footage is divided into consecutive states. Normally one label applies at a time, but **labels can be combined** when two things happen at once (for example `overtaken, sliding`).

### Event type list

- The possible event types are **not hardcoded**. The module takes them from a list that is kept outside the program logic.
- Adding, renaming or removing an event type means changing the list, not the module.
- For now the list is a **CSV file**, read at every run, so the user can add types freely. In the future it will be read from a database; the rest of the module must not care where the list comes from.
- A label alone does not tell the module what to look for. **Each entry holds two things: the label and a plain-language description** of what the event looks like (agreed).
- The module uses the description to recognise the event where that works. Types that cannot be recognised that way get a dedicated detection routine or labelled example clips. How well the description route works is unproven and must be tested on the examples.
- Adding a type should normally mean adding one line (label and description) to the list.
- Until a new type can be recognised, such moments still appear as `other event` (section 5).
- The module only writes labels that are in the list, plus `other event` (see section 5).

### Known event types so far

States seen in the example output file:

| Label | Meaning |
|---|---|
| `warm up` | Start of the session before driving at pace |
| `clear` | Clear track, nothing unusual |
| `offtrack` | The user's car leaves the track |
| `sliding` | The user's car slides |
| `overtaking` | The user's car passes another car |
| `cooling` | Cool-down at the end of the session |

States named by the user but not in the example:

| Label | Meaning |
|---|---|
| `overtaken` | Another car passes the user's car |
| `obstacle` | Anything on the road: debris, a stopped car, or any other object |
| `held up` | A car ahead holds the user's car up: following it closely without passing |
| `crash` | The user's car can no longer drive on at pace: a collision or a mechanical failure |

### Descriptions (confirmed by the user)

These are the description texts for each entry in the event type list. All are written from the forward view out of the user's car.

| Label | Description |
|---|---|
| `warm up` | From the start of the video until the car first drives at full pace: standing in the paddock or pit lane, leaving the pits, and the slow first lap. |
| `clear` | The car drives at pace on the track. No other car is close ahead or alongside, nothing lies on the road, and the car stays on the tarmac and under control. |
| `offtrack` | My car leaves the tarmac with at least two wheels: grass, gravel or run-off area is under or directly ahead of the car, often with a shaking picture or dust. Ends when the car is back on the tarmac. |
| `sliding` | My car loses grip but stays on the track: the view swings sideways more than the road bends, the steering is corrected quickly, tyres may squeal. Ends when the car drives straight and stable again. |
| `overtaking` | A car ahead of me comes closer, I move alongside it and pass it, and it disappears from the picture behind me. Starts when I pull alongside; ends when the other car is out of view. |
| `overtaken` | Another car appears at the side of the picture coming from behind, passes me and moves ahead. Starts 3 seconds **before** the other car first appears, so the whole process is covered; ends when it is clearly ahead and has pulled away. |
| `held up` | A car ahead of me holds me up: I follow it closely without passing, and it dictates my line and speed. |
| `obstacle` | Something is on or beside the road that should not be there: debris, car parts, fluid, gravel thrown onto the tarmac, or a stopped car. Starts when it becomes visible; ends when I have passed it. |
| `crash` | My car can no longer drive on at pace: it hits something, is hit by another car, or stops with a mechanical failure. Lasts until the end of the video unless the car drives on. (Draft, to be confirmed. Added from the third example, where the clutch failed.) |
| `cooling` | From the moment the car stops driving at pace at the end of the session until the end of the video: slow final lap, entering the pit lane, parking. |
| `other event` | Anything clearly unusual that fits none of the descriptions above. (Fixed label, not part of the list.) |

Decided by the user:

- Following another car closely without passing is not `clear`; it gets its own label, `held up`.
- `offtrack` counts from two wheels off the tarmac.
- When two things happen at once, the labels are combined, for example `overtaken, sliding`. Any labels may be combined; the module assumes no combination is impossible.
- `overtaken` starts 3 seconds before the other car appears. The value is fixed for now, but it must be easy to fine-tune later.

`warm up` and `cooling`:

- Preferred: the module detects them itself, from the speed of the car.
- This is a wish, not a hard requirement: if it proves not possible, the module may leave them out.
- Note for the design phase: this module has no reliable speed data. The GoPro GPS is mostly invalid and RaceBox Mini data is out of scope, so speed would have to be estimated from the video or sound.

Further candidates, not yet agreed: traffic ahead without a pass, flags or light panels, a slow car, pit lane, weather or surface change.

Observations from the example:

- Events can be very short: several last 2 to 3 seconds.
- An event is normally followed by `clear`, but not always: the last `offtrack` is followed directly by `cooling`.

## 5. Unknown events

The user expects event types they cannot name yet. Requirements:

- The module flags segments that look unusual compared with normal clear driving, even if no known label matches.
- Such a segment is written to the txt file with the label `other event`.
- The user can review these segments and give them a name.
- A newly named event type is added to the event type list (section 4) and can then be detected in later footage without rewriting the module.

## 6. Output

Two files per video: the extracted GPS track and the events file.

**Naming rule:** the created files keep the video's original file name without the `.mp4` extension. For an input `something.mp4` the module writes `something.gpx` and `something-events.txt`. The shared base name is what links the three files.

### 6.1 GPS track (GPX file)

The module extracts the GPS data embedded in the MP4 and saves it as a GPX file.

**Purpose:** the GPX file exists only to synchronise the video with the RaceBox Mini recording of the same session. The stretch of GoPro GPS that is valid links a position in the video to a real time and place, which can be matched against the RaceBox Mini data. Once the two are synchronised, every event time in the events file (section 6.2) can be mapped onto the RaceBox Mini GPS data.

**Boundary:** this module only creates the GPX file. The synchronisation itself, and everything else done with the GPX file, belongs to other modules.

**No modification:** the GPS data is written exactly as extracted. The module does not remove, mark, correct or filter any points, including the invalid ones described below.

Reference output: `example video  and output file/RaceBox Track Sessionon 30-05-2026 09-41.gpx`

- **File name:** the video's name with the extension `.gpx`, in the same folder as the video.
- **Format:** GPX 1.0, one track with one segment; each point has latitude, longitude, elevation and a UTC time. No speed field.
- **Rate:** 10 points per second (7873 points for the 13:07 example).
- **Manual method used so far:** `exiftool -a "-gps*" -p gpx.fmt -ee GX010175.MP4 > GX010175.extracted_gps.gpx`. The module must produce an equivalent file without manual steps. ExifTool is not currently installed on this PC.

Data quality seen in the example, which the user confirms is typical (recorded here for the modules that consume the file; this module passes it through unchanged):

- The first 4833 points (about 8 minutes) have no fix: latitude and longitude are 0.
- The first 987 points carry a placeholder date in 2021 before the real date appears.
- About 2860 further points are implausible: positions scattered across Europe and North Africa at altitudes above 10 km.
- Only the last 178 points (about 18 seconds) are at the actual track (around 47.32 N, 19.51 E).

### 6.2 Events file (txt)

A plain text file, one per video.

Reference output: `example video  and output file/RaceBox Track Sessionon 30-05-2026 09-41-events.txt`

Format, as derived from the example:

- **File name:** the video's name without extension, followed by `-events.txt`, in the same folder as the video.
- **One line per state change:** `mm:ss label`, time and label separated by one space.
- **Time:** position in the video where the state begins, minutes and seconds, zero-padded, one-second resolution. From one hour onward the time is written with hours, as `h:mm:ss` (for example `1:15:10`).
- **Label:** lower case, may contain a space (`warm up`).
- **Combined labels:** when more than one label applies, they are written on the same line separated by a comma and a space, for example `05:25 overtaken, sliding`. A new line is written whenever the set of labels changes. A label must therefore never contain a comma.
- **Duration:** a state lasts until the next line's time; the last state lasts until the end of the video.
- **First line:** starts at `00:00`, so the whole video is covered without gaps.
- **Order:** lines are in ascending time order.
- **Line endings:** Windows (CRLF).

Example:

```
00:00 warm up
01:44 clear
02:31 offtrack
02:33 clear
```

The format has no place for a confidence value or other extra fields.

## 7. Quality expectations

- How the result is used: the larger program evaluates driving per curve or curve combination and only takes the `clear` ones into consideration. The events file decides which curves are excluded.
- **A false alarm is worse than a missed event** (stated by the user). The module should report an event only when it is reasonably sure, and leave doubtful moments as `clear`. This applies to every event type, including `other event`: unusual moments are flagged only when clearly unusual.
- Known consequence: a missed event lets a disturbed curve into the evaluation as if it were clear.
- The reference is a person watching the video and marking the events by hand; the example events file was made this way. Times are the time elapsed since the beginning of the video.
- **Tolerance:** a detected time may differ from the hand-marked time by up to 5 seconds. This is enough because results are used per curve, not per second.
- **Corrections:** when the module classifies something wrongly, the user corrects the events file by hand, and the user's version overrides the machine's (for now). Corrected files are kept as further reference examples for measuring and improving the module.
- The module must not silently replace an events file that already exists, so hand corrections are not lost on a re-run (assumption, to confirm).

## 8. Constraints

- **Where it runs:** on the user's own computer. The footage stays on that computer and is not uploaded anywhere.
- **Processing time:** a full day's set (up to 20 files) may take a few hours.
- **How it is started:** by hand during testing; later it is called from the main program. Both ways must work with the same inputs and outputs.
- **Learning:** the user wants to learn from the project, so the result must be understandable to someone new to programming.
- Camera mount, lens setting and resolution may differ between trackdays; parts of the car's interior may be in frame.

## 9. Out of scope

- Splitting footage into sessions and laps (another module).
- Synchronising the video with RaceBox Mini data and mapping events onto it (other modules).
- Cleaning or validating the GPS data.
- Live, in-car analysis.
- Lap timing and driver coaching (racing line, braking points).
- Identifying other drivers or reading number plates.
- Technology choices: these belong in `TECHNICAL_SPEC.md`, not here.

## 10. Open questions

1. Two more hand-labelled examples are promised; they are expected to contain `overtaken` and `obstacle`. `held up` is a new label with no example yet, so it cannot be checked until footage with it is labelled.
