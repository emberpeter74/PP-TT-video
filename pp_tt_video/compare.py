"""Step 3: compare a detected events file with a hand-made reference.

For every label it counts:
    correct       the event is in both files, at about the same time
    missed        the event is in the reference but was not detected
    false alarms  the event was detected but is not in the reference

"About the same time" means within the tolerance in settings.py (5 seconds).

Run by hand from the project folder:
    py -V:3.13 -m pp_tt_video.compare "reference-events.txt" "detected-events.txt"
"""

import argparse
import sys
from dataclasses import dataclass

from pp_tt_video import settings
from pp_tt_video.events import read_events_file

# The last line of an events file lasts "until the end of the video".
# The comparison does not need the real length, so it uses infinity.
END_OF_VIDEO = float("inf")


@dataclass
class LabelScore:
    """The counts for one label."""

    label: str
    correct: int = 0
    missed: int = 0
    false_alarms: int = 0


def to_intervals(timeline):
    """Turn a timeline into stretches of time per label.

    Returns a dictionary: label -> list of (start, end) in seconds.
    "clear" is left out: it is the background, not an event.
    """
    intervals = {}
    for index, event in enumerate(timeline):
        is_last = index == len(timeline) - 1
        end = END_OF_VIDEO if is_last else timeline[index + 1].start
        for label in event.labels:
            if label == settings.CLEAR_LABEL:
                continue
            stretches = intervals.setdefault(label, [])
            # A label that continues over two lines (for example "overtaken"
            # followed by "overtaken, sliding") is one event, not two.
            if stretches and stretches[-1][1] == event.start:
                stretches[-1] = (stretches[-1][0], end)
            else:
                stretches.append((event.start, end))
    return intervals


def is_same_event(reference, detected, tolerance):
    """True when two stretches overlap, allowing for the tolerance."""
    reference_start, reference_end = reference
    detected_start, detected_end = detected
    return detected_start <= reference_end + tolerance and detected_end >= reference_start - tolerance


def compare_timelines(reference, detected, tolerance=None):
    """Compare two timelines and return a list of LabelScore, one per label."""
    if tolerance is None:
        tolerance = settings.TIME_TOLERANCE_SECONDS
    reference_intervals = to_intervals(reference)
    detected_intervals = to_intervals(detected)

    scores = []
    # set(a) | set(b) is every label that occurs in either file.
    for label in sorted(set(reference_intervals) | set(detected_intervals)):
        score = LabelScore(label)
        unused = list(detected_intervals.get(label, []))
        for reference_stretch in reference_intervals.get(label, []):
            # Look for the first detected stretch that is the same event.
            # Each detected stretch can be used only once.
            match = next((d for d in unused if is_same_event(reference_stretch, d, tolerance)), None)
            if match is None:
                score.missed += 1
            else:
                score.correct += 1
                unused.remove(match)
        score.false_alarms = len(unused)
        scores.append(score)
    return scores


def format_scores(scores):
    """Return the scores as a small table of text."""
    lines = [f"{'label':<16}{'correct':>9}{'missed':>9}{'false alarms':>14}"]
    for score in scores:
        lines.append(f"{score.label:<16}{score.correct:>9}{score.missed:>9}{score.false_alarms:>14}")
    lines.append(
        f"{'total':<16}"
        f"{sum(s.correct for s in scores):>9}"
        f"{sum(s.missed for s in scores):>9}"
        f"{sum(s.false_alarms for s in scores):>14}"
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        prog="pp_tt_video.compare",
        description="Compare a detected events file with a hand-made reference.",
    )
    parser.add_argument("reference", help="the hand-made events file")
    parser.add_argument("detected", help="the events file written by the module")
    arguments = parser.parse_args()

    scores = compare_timelines(read_events_file(arguments.reference), read_events_file(arguments.detected))
    print(format_scores(scores))
    return 0


if __name__ == "__main__":
    sys.exit(main())
