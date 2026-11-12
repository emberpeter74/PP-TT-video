"""Step 3: reading and writing events files.

An events file has one line per change, for example:

    00:00 warm up
    01:44 clear
    05:25 overtaken, sliding

Each line says: from this moment on, these labels apply. They apply until the
next line, and the last line applies until the end of the video.
(See BUSINESS_SPEC.md, section 6.2.)
"""

from dataclasses import dataclass
from pathlib import Path


class EventsFileError(Exception):
    """Raised when an events file cannot be read or must not be written."""


@dataclass(frozen=True)
class Event:
    """One line of an events file."""

    start: int      # seconds since the beginning of the video
    labels: tuple   # one label, or several when things happen at once


def format_time(seconds):
    """Turn seconds into text: 104 -> "01:44", 4510 -> "1:15:10"."""
    hours, rest = divmod(int(seconds), 3600)   # divmod gives quotient and remainder
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_time(text):
    """Turn text into seconds: "01:44" -> 104, "1:15:10" -> 4510."""
    parts = text.split(":")
    if len(parts) not in (2, 3) or not all(part.isdigit() for part in parts):
        raise ValueError(f"not a time: {text!r}")
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def events_path_for(video_path, output_folder=None):
    """Return where the events file for a video belongs.

    Naming rule: "something.mp4" gives "something-events.txt".
    """
    video_path = Path(video_path)
    folder = Path(output_folder) if output_folder else video_path.parent
    return folder / (video_path.stem + "-events.txt")


def read_events_file(path):
    """Read an events file and return its lines as a list of Event.

    Hand-made files are read with some tolerance: upper case letters and
    spaces around a label are accepted, and empty lines are skipped.
    """
    timeline = []
    text = Path(path).read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        # Split at the first space: the time before it, the labels after it.
        time_text, _, label_text = line.partition(" ")
        try:
            start = parse_time(time_text)
        except ValueError:
            raise EventsFileError(f"{Path(path).name}, line {line_number}: no time at the start of {line!r}")
        labels = tuple(label.strip().lower() for label in label_text.split(",") if label.strip())
        if not labels:
            raise EventsFileError(f"{Path(path).name}, line {line_number}: no label in {line!r}")
        timeline.append(Event(start, labels))
    return timeline


def find_problems(timeline, known_labels=None):
    """Return a list of texts describing what is wrong with a timeline.

    An empty list means the timeline follows the rules.
    """
    problems = []
    if not timeline:
        return ["the timeline is empty"]
    if timeline[0].start != 0:
        problems.append(f"the first line starts at {format_time(timeline[0].start)}, not at 00:00")
    # zip pairs every line with the line after it.
    for previous, current in zip(timeline, timeline[1:]):
        if current.start <= previous.start:
            problems.append(
                f"{format_time(current.start)} {', '.join(current.labels)}: "
                f"the time is not later than the line before it ({format_time(previous.start)})"
            )
    for event in timeline:
        for label in event.labels:
            if "," in label or "\n" in label:
                problems.append(f"{format_time(event.start)}: label {label!r} contains a comma or line break")
            elif known_labels is not None and label not in known_labels:
                problems.append(f"{format_time(event.start)}: label {label!r} is not in the event type list")
    return problems


def write_events_file(path, timeline, known_labels=None, overwrite=False):
    """Write a timeline as an events file.

    An existing file is never replaced unless overwrite is True, so that
    corrections made by hand are not lost. A timeline that breaks the rules
    is not written at all.
    """
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Events file already exists: {path}")
    problems = find_problems(timeline, known_labels)
    if problems:
        raise EventsFileError("Timeline not written: " + "; ".join(problems))

    lines = [f"{format_time(event.start)} {', '.join(event.labels)}" for event in timeline]
    # Windows line endings (CRLF), as in the hand-made example files.
    text = "".join(line + "\r\n" for line in lines)
    path.write_bytes(text.encode("utf-8"))
    return path
