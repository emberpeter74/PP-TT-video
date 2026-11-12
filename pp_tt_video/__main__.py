"""Runs the module by hand from a terminal.

Example, from the project folder:
    py -V:3.13 -m pp_tt_video "path/to/video.mp4"
    py -V:3.13 -m pp_tt_video "path/to/folder with videos"

Python runs this file when a package is started with "-m".
"""

import argparse
import sys

from pp_tt_video.pipeline import process_videos


def main():
    parser = argparse.ArgumentParser(
        prog="pp_tt_video",
        description="Extract the GPS track from GoPro trackday videos.",
    )
    parser.add_argument("inputs", nargs="+", help="video files, or folders that contain videos")
    parser.add_argument("--overwrite", action="store_true", help="replace GPX files that already exist")
    arguments = parser.parse_args()

    results = process_videos(arguments.inputs, overwrite=arguments.overwrite)

    if not results:
        print("No video files found.")
        return 1
    for result in results:
        status = "OK    " if result.ok else "FAILED"
        print(f"{status} {result.video.name}: {result.message}")

    # Exit code 0 means success; anything else tells the caller that
    # at least one video failed.
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
