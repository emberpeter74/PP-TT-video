# Trackday footage analysis module: business specification

Status: draft, updated from the three example videos and their hand-made events files. Open questions are in section 10.

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

**Examples provided by the user.** Three sessions from one trackday (30 May 2026), each a video with a hand-made events file and an extracted GPX file, in the folder `example video  and output file`:

| Example | Length | Events it contains |
|---|---|---|
| 09-41 | 13:07 | out of session (2), warm up, sliding (4), offtrack (2), overtaking (2), cooling |
| 10-32 | 10:25 | out of session (2), overtaken, overtaking (3), sliding (4), held up, cooling |
| 12-17 | 6:27 | out of session, overtaken, overtaking (2), obstacle (3), sliding (2), held up, crash |

Together they contain every agreed event type at least once. The counts are small, so they can show whether detection works in principle, not how accurate it is in general.

**Two files per example.** `name-events.original.txt` is the file exactly as the user wrote it and is never changed by anyone else. `name-events.txt` is a cleaned copy with the same content in the agreed format (labels from the event type list, lines in time order); the comparison tool and the checks use the cleaned copy. When the user changes an original, the cleaned copy is updated to match.

Reference input, described in detail below: `example video  and output file/RaceBox Track Sessionon 30-05-2026 09-41.MP4`

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

### Driver and car profile

Decided by the user, after four of five new videos came out as one long `warm up`. They were driven by the user's son, a beginner, who brakes and corners far more gently than the user: measured on the sensors, about 40% of the braking effort and 55% of the cornering force. The module's values were set on the user's own driving, so to the module the son never reached pace and every event in those sessions was dropped. The module is also meant to be used by other drivers.

- **A profile says what counts as quick for one driver in one car.** It holds the values the rules compare with. Without a profile the module uses its built-in values, which are the user's own.
- **Choosing a profile:**
  - `--profile <name>` on the command line uses that profile for every video in the run.
  - Otherwise, if the folder of a video holds a profile file, that profile is used for that video. **(Assumption: this also applies when single video files are given instead of a folder: the file's own folder is looked at.)**
  - Otherwise the built-in values are used.
  - `--profile` wins over a profile file in the folder **(assumption: a value typed on the command line is the most deliberate choice)**.
- **Making a profile:** a separate command reads the videos in a folder and writes a profile from them. This is how a new driver starts with the tool.
  - The values are **scaled relative to the user's own driving** (decided by the user, as a first idea to be changed if it does not work). The command measures how hard the driver typically brakes and corners in those videos, compares that with the user's examples, and scales the values that depend on the driver by the same ratio.
  - Only values that depend on the driver are scaled: what counts as pace, the cornering force from which slides are looked for, and the cornering force that marks the last corner before leaving the track. Values that depend on the car or the camera (how hard the car shakes on a kerb, how large another car looks) cannot be measured this way; they keep the built-in values and can be changed by hand in the file.
  - The folder must hold that driver's videos only. The command cannot tell drivers apart.
- **The profile file is plain text** that can be read and edited by hand, with a comment on every value. It is not program code. **(Assumption: a profile may come from another driver, and a file that is program code would run as a program on this PC.)**
- **Which profile was used is always visible:** it is printed for every video when the tool runs, and it is shown on the check video. The events file does not change: its format is fixed for the other modules.
- Known risk: lower values mean the rules react to smaller signals, so false alarms become more likely for a gentle driver. The check video is the tool to see whether a new profile works.

**Footage for trying profiles** (provided by the user, not in Git), in `input video files/`, one folder per driver as the profile rules expect:

| Folder | Driver | Videos | Braking level / cornering level (the user's three examples: 2.61 / 10.92) |
|---|---|---|---|
| `practice driver` | the user's son, a beginner | GX010179, GX010180, GX010182, GX010183 | 1.01 / 5.98 |
| `stronger driver` | the user | GX010181 | 1.98 / 9.75 |

These videos have no hand-made events files, so results on them are judged by watching, not counted with the comparison tool.

**Built (steps P1 and P2).** With the profile made from the son's four videos, the module no longer calls them one long `warm up`: it finds a part at pace in each.

**Found while trying it: `offtrack` gives false alarms on the son's footage.** With a part at pace found, the module reports 6 to 19 `offtrack` events per video. The user watched the whole of GX010183: the car never left the track (once or twice it was on a kerb), so all 19 there are false. They are a vibration of the camera, not rough ground; the technical specification has the measurements. This breaks the rule that a false alarm is worse than a missed event, and a profile cannot fix it. Decided by the user: the offtrack rule is reworked after the check video is built. Until then the module has not been run in full on the son's videos.

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
| `out of session` | The session has not started yet or is already over (added by the user after step 7) |
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
| `out of session` | The session has not started yet or is already over: the car is in the paddock or the pit lane, drives to the track, has left the track, or is parked. From the start of the video until the car joins the track, and from leaving the track until the end of the video. (Wording proposed, to be confirmed.) |
| `warm up` | From joining the track until the car first drives at full pace: the slow first lap. (Wording changed when `out of session` was added, to be confirmed.) |
| `clear` | The car drives at pace on the track. No other car is close ahead or alongside, nothing lies on the road, and the car stays on the tarmac and under control. A car further ahead that I am not catching does not change this. |
| `offtrack` | My car leaves the tarmac with at least two wheels: grass, gravel or run-off area is under or directly ahead of the car, often with a shaking picture or dust. Ends when the car is back on the tarmac. |
| `sliding` | My car loses grip but stays on the track: the view swings sideways more than the road bends, the steering is corrected quickly, tyres may squeal. Ends when the car drives straight and stable again. |
| `overtaking` | A car ahead of me comes closer, I move alongside it and pass it, and it disappears from the picture behind me. Starts when I pull alongside; ends when the other car is out of view. |
| `overtaken` | Another car appears at the side of the picture coming from behind, passes me and moves ahead. Starts 3 seconds **before** the other car first appears, so the whole process is covered; ends when it is clearly ahead and has pulled away. |
| `held up` | A car ahead of me holds me up: I am close behind it, I am not falling back, and it dictates my line and speed. Ends when I start to overtake it, when it pulls away, or when it leaves the track ahead of me. |
| `obstacle` | Something is on or beside the road that should not be there: debris, car parts, fluid, gravel thrown onto the tarmac, or a stopped car. Starts when it becomes visible; ends when I have passed it. |
| `crash` | My car can no longer drive on at pace: it hits something, is hit by another car, or stops with a mechanical failure. Lasts until the end of the video unless the car drives on. (Draft, to be confirmed. Added from the third example, where the clutch failed.) |
| `cooling` | From the moment the car stops driving at pace at the end of the session until it leaves the track: the slow final lap. (Wording changed when `out of session` was added, to be confirmed.) |
| `other event` | Anything clearly unusual that fits none of the descriptions above. (Fixed label, not part of the list.) |

Decided by the user:

- Following another car closely without passing is not `clear`; it gets its own label, `held up`.
- **Following a quicker car is `clear`.** If the car ahead is faster and the user cannot catch it, it does not hold the user up, even though it stays in view. What separates the two cases is distance: `held up` means being close behind a car that is not pulling away; a car that stays at a distance or gets further away leaves the track `clear`.
- **`held up` can turn into `overtaking`.** The user often follows a slower car for a while and passes it when the situation allows. The events file then shows `held up` followed directly by `overtaking`, with no `clear` in between. The switch is at the moment the user pulls out to pass, which is where the description of `overtaking` starts. Both examples with `held up` show this pattern: about 13 and 36 seconds of `held up`, then 2 to 3 seconds of `overtaking`.
- **`held up` needs at least 3 seconds.** Being close behind another car counts as `held up` only after 3 seconds; a shorter moment of closing in before an overtake is not marked. The value is fixed for now, but it must be easy to fine-tune later.
- An overtake does not need a `held up` before it: catching and passing a car without being slowed is `clear` followed by `overtaking`.
- `offtrack` counts from two wheels off the tarmac.
- When two things happen at once, the labels are combined, for example `overtaken, sliding`. Any labels may be combined; the module assumes no combination is impossible.
- `overtaken` starts 3 seconds before the other car appears. The value is fixed for now, but it must be easy to fine-tune later.

`warm up` and `cooling`:

- Preferred: the module detects them itself, from the speed of the car.
- This is a wish, not a hard requirement: if it proves not possible, the module may leave them out.
- **Built (step 8):** the module detects both, but not from the speed. In the examples a cool-down lap is only about 10 km/h slower than a fast lap, so speed does not separate them. What does: at pace the driver brakes and accelerates hard, on a warm-up or cool-down lap gently. The module reads this from the camera's motion sensors, which work for the whole video without GPS. Details are in the technical specification.
- `warm up` is only at the start of a video and `cooling` only at the end. A slow stretch in the middle of a session is neither.
- A video that starts at pace has no `warm up`; one that ends at pace has no `cooling`.

`out of session` (decided by the user, built after step 7):

- It marks the parts of the video in which the session has not started yet or is already over. Paddock, pit lane, the way to and from the track and parking all count the same.
- **A video can start before the car reaches the track, or when it is already on the track.** It can end after the car has left the track, or before. `out of session` is only written where the video shows such a part.
- The order of the large parts of a video is: `out of session`, `warm up`, the part at pace, `cooling`, `out of session`. Any of them can be missing.
- **A brisk first lap is not `warm up`** (decided by the user). When the engine is already hot the first lap is driven at pace, and the module rightly reports no `warm up`: in the 10-32 and 12-17 examples `out of session` is followed directly by `clear`.
- **After a crash there is no `cooling` and no `out of session`** (decided by the user): `crash` lasts until the end of the video. It does not matter when the car was taken off the track.
- **Another car standing on the track is an `obstacle`** like any other (decided by the user). Not built yet.

`crash`, as far as it is built:

- The module reports `crash` when the car stands still less than 60 seconds after it stopped driving at pace: there was no cool-down lap, so something broke or was hit. This finds the breakdown in the 12-17 example.
- Known risk, accepted by the user: driving straight into the pits from a fast lap and parking within a minute would also be reported as `crash`.
- A collision after which the car drives on is not detected.

Assumptions made while building this, to be confirmed by the user:

- **Events are only reported in the part at pace.** `overtaking`, `overtaken`, `held up`, `sliding` and `offtrack` are not reported during `out of session`, `warm up`, `cooling` and `crash`. In the pit lane and paddock, parked and passing cars would otherwise be reported as events, and the larger program ignores everything that is not `clear` anyway.
- **A video in which the car never drives at pace is `warm up`**, after any `out of session` at its start.

`sliding` and `offtrack` (built in step 7, from the camera's motion sensors):

- `sliding` is reported for slides the driver catches with a quick steering correction. All 10 slides marked in the examples are of this kind and are found.
- `offtrack` is reported only when the car clearly shakes on grass or gravel for a second or more. Two wheels off for a moment feel like a kerb to the sensors and are left as `clear`, following the rule that a false alarm is worse than a missed event. Of the 2 marked in the examples, 1 is found. The missed one (02:31 in 09-41) is the right wheels about 20 cm off the track for a few tenths of a second (described by the user). On the son's footage the rule gives false alarms; see "Driver and car profile" in section 3.
- Like the car events, neither is reported outside the part at pace (see the assumption above).

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

Three files per video: the extracted GPS track, the motion sensor data and the events file.

**Naming rule:** the created files keep the video's original file name without the `.mp4` extension. For an input `something.mp4` the module writes `something.gpx`, `something-sensors.csv` and `something-events.txt`. The shared base name is what links the files.

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

### 6.3 Sensor data file (csv)

Decided by the user: the motion sensor data is written to its own file, separate from the GPX file. Built in step V1.

- A plain table (CSV) that opens in Excel: one row per measurement, about 200 per second. A 10-minute video gives about 120,000 rows and 14 MB.
- Columns: the time in the video in seconds, the three acceleration values (m/s²) and the three rotation values (radians per second).
- The values are exactly as the camera stored them, along the camera's own axes. They are kept raw on purpose: the rules assume a certain camera mounting, and only the raw values would show a different one.
- The camera stores the measurements in blocks of about a second and only says when a block starts. The times of the single measurements are spread evenly over their block.
- Written for every video, also with `--gps-only` (assumption, to confirm). Skipped when the file exists, unless `--overwrite` is given.
- A video without motion sensor data (not a GoPro file) gets no sensor file. That is not an error.
- The file is for the user's own analysis and for the check video. No other module depends on it yet, so its format may still change.

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

1. Is the `crash` description right, or should a mechanical failure be its own event type?
2. Are the two assumptions in section 4 right (events only in the part at pace; a video never at pace is `warm up`)?
3. Are the changed descriptions of `out of session`, `warm up` and `cooling` in section 4 right?
4. In the 09-41 example the module reports a slide at 02:47 that the hand-made file does not have. Is it a real slide?
5. In the 12-17 example the hand-made file has `sliding` from 02:49 to 03:11. Did the slide last that long, or is a `clear` line missing?
6. The assumptions on driver and car profiles in section 3: the video's own folder is looked at also for single files; `--profile` wins over a file in the folder; a profile is plain text, not program code.

Settled: the two further examples promised by the user have been provided (see section 3). The 10-32 and 12-17 recordings start in the pit exit and go straight to pace: `out of session` for a few seconds, then `clear`, no `warm up` (confirmed by the user).
