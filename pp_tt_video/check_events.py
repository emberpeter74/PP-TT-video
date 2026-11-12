"""Checks events files against the rules and lists what is wrong.

Useful for hand-made files: a typing mistake in a time or a label is found
here instead of confusing the comparison later.

Run by hand from the project folder:
    py -V:3.13 -m pp_tt_video.check_events "path/to/folder or events file"
"""

import argparse
import sys
from pathlib import Path

from pp_tt_video.event_types import known_labels
from pp_tt_video.events import EventsFileError, find_problems, read_events_file


def find_events_files(inputs):
    """Turn a list of files and folders into a list of events files."""
    files = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted(path.glob("*-events.txt")))
        else:
            files.append(path)
    return files


def check_file(path, labels):
    """Return the list of problems in one events file."""
    try:
        timeline = read_events_file(path)
    except (EventsFileError, OSError) as error:
        return [str(error)]
    return find_problems(timeline, labels)


def main():
    parser = argparse.ArgumentParser(
        prog="pp_tt_video.check_events",
        description="Check events files against the rules.",
    )
    parser.add_argument("inputs", nargs="+", help="events files, or folders that contain them")
    arguments = parser.parse_args()

    labels = known_labels()
    files = find_events_files(arguments.inputs)
    if not files:
        print("No events files found.")
        return 1

    files_with_problems = 0
    for path in files:
        problems = check_file(path, labels)
        if problems:
            files_with_problems += 1
            print(f"{path.name}: {len(problems)} problem(s)")
            for problem in problems:
                print(f"    {problem}")
        else:
            print(f"{path.name}: OK")
    return 1 if files_with_problems else 0


if __name__ == "__main__":
    sys.exit(main())
