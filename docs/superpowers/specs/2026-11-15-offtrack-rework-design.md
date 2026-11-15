# Rework of the offtrack rule: design

Status: approved by the author on 2026-11-15. Size: a small change (one rule, two settings changed, one added).

Changed while planning and building (the plan has the details):

- Point 1: `offtrack_stretches` does not stay as it is. It now counts pieces (6 in a row) instead of comparing times, which depended on rounding.
- Point 6: the module only makes whole check videos, so the piece around 02:31 is shown as a short clip made by a throwaway script.

## Why

The offtrack rule reports a vibration of the camera as "offtrack": 6 to 19 times per video on the practice driver's footage, all 19 in GX010183 confirmed false by the author. It also misses the short offtrack at 02:31 in 09-41 (right wheels about 20 cm off for a few tenths of a second).

## Goals, non-goals, anti-goals

- **Goal:** no false offtrack on any of the eight videos we have; the two offtracks the author marked by hand in 09-41 (02:31 and 11:15) are found.
- **Non-goal:** finding every wheel on the grass. Only what shakes the car clearly more than a kerb.
- **Anti-goal:** new false alarms. A false alarm is worse than a missed event.

## What was measured

The false alarms are a fast vibration, about 87 per second, up and down only. Rough ground shakes the car more slowly. If every measurement is averaged with the three that follow it (four measurements are about a fiftieth of a second), the fast vibration cancels out and the slower bumps stay. The "smoothed shake" is the shake of these averages.

| Moment | Shake now (threshold 7) | Smoothed shake |
|---|---|---|
| False alarm, GX010183 08:11 | 10.4 | 1.7 |
| Real offtrack, 09-41 11:17 | 10 to 13 | 5.3 to 7.1 |
| Short offtrack, 09-41 02:32 | 5.3 to 6.7 | 2.3 to 3.5 |
| Normal driving, the author's videos | about 2.5 | about 1.0 |

The smoothed shake that only 1 in 1000 moments exceeds: 4.1 to 5.8 in the author's three example videos, 2.1 to 2.4 in the practice driver's four.

## Approaches

| Approach | Result on the eight videos (119 minutes) | Verdict |
|---|---|---|
| A. Smoothed shake, strict: at least 3.5 for 1.0 s | Finds 11:15 only. Wide margin. | Fallback |
| **B. Smoothed shake, sensitive: at least 2.2 for 1.2 s** | Finds 02:31 and 11:15, nothing else. Thin margin: the short one lasts 1.4 s. | **Chosen by the author** |
| Shake forward or sideways instead | 10 to 60 hits per video on the author's footage | Dropped |
| The rotation sensor | Hundreds of hits per video | Dropped |
| "Unusual for this video" | The practice driver's normal level is half the author's: their kerbs would be flagged | Dropped |

A and B are the same code. Going from B back to A means changing two numbers in `settings.py`.

**Known risk of B:** its two numbers are fitted to two real offtracks. With slightly looser values (1.0 s instead of 1.2 s, in combination with other signals) a moment at 02:12 in 12-17 appears, which has not been judged. New footage may need the numbers moved towards A.

## The design

1. **`offtrack.py`:** `shake_over_time` smooths the measurements of each piece (a fifth of a second) before it measures the shake. The smoothing is a small function of its own. `offtrack_stretches` stays as it is.
2. **`settings.py`:**
   - new `OFFTRACK_SMOOTHING_MEASUREMENTS = 4` (1 switches the smoothing off),
   - `OFFTRACK_MIN_SHAKE` from 7.0 to 2.2,
   - `OFFTRACK_MIN_SECONDS` from 1.0 to 1.2,
   - the lead (1.5 s) and tail (0.5 s) stay,
   - the comments get the measured levels of the table above.
3. **The check video (`charts.py`):** the offtrack chart shows the smoothed shake as the rule's line, with its threshold. One thin line for information: the shake without smoothing, so the camera vibration stays visible. The sideways and forward lines go: they were there to find this rework and are no longer needed. The chart's scale follows the rule's line, so the threshold does not end up squeezed at the bottom. *(The assistant's call.)*
4. **Profiles:** `OFFTRACK_MIN_SHAKE` stays a value a profile may set. A profile written before this change has the old value 7.0 in a comment line; the practice driver's `profile.toml` is made again with `make_profile --overwrite` (needs the author's yes, it is in their folder). *(The assistant's call.)*
5. **Checks:** made-up data for a fast vibration (not reported) and for slow, rough shaking (reported); smoothing with 1 gives the old values; the existing offtrack checks are adapted to the new numbers. One check with the example videos, skipped when they are missing: 09-41 gives offtracks at 02:31 and 11:15 and the other two examples give none.
6. **Proof on real footage:** a sensors-only run over all eight videos (seconds each, nothing written into the practice driver's folder) must give exactly the two offtracks. Then the check video of a piece of 09-41 around 02:31 for the author to look at.
7. **Documents:** business spec (what "offtrack" finds now), technical spec (the rule, the measurements, the dropped approaches), `CLAUDE.md` (the false-alarm warning and the "missed at 02:31" weak spot are removed; the warning about `--overwrite` on the practice driver's folder is lifted only when the author says so).

## Left to the builder

- The exact made-up numbers in the checks.
- Whether the hand-made 09-41 file's times (02:31 to 02:33, 11:15 to 11:20) are met to the second: a difference of a second or two is accepted.
