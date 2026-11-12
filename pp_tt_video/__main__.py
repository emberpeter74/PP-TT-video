"""Runs the module by hand from a terminal.

Example, from the project folder:
    py -V:3.13 -m pp_tt_video "path/to/video.mp4"
    py -V:3.13 -m pp_tt_video "path/to/folder with videos"

Python runs this file when a package is started with "-m".
"""

import argparse
import sys

from pp_tt_video.pipeline import process_videos


def show_start(number, total, video):
    """Tell the user which video is being worked on right now."""
    # flush=True shows the line at once instead of waiting for more output.
    print(f"[{number}/{total}] {video.name}: extracting GPS ...", flush=True)


def show_done(number, total, result):
    """Tell the user how the video went."""
    status = "OK" if result.ok else "FAILED"
    print(f"[{number}/{total}] {status}: {result.message} ({result.seconds:.0f} s)", flush=True)


def main():
    parser = argparse.ArgumentParser(
        prog="pp_tt_video",
        description="Extract the GPS track from GoPro trackday videos.",
    )
    parser.add_argument("inputs", nargs="+", help="video files, or folders that contain videos")
    parser.add_argument("--overwrite", action="store_true", help="replace GPX files that already exist")
    arguments = parser.parse_args()

    results = process_videos(
        arguments.inputs,
        overwrite=arguments.overwrite,
        on_start=show_start,
        on_done=show_done,
    )

    if not results:
        print("No video files found.")
        return 1

    failed = [result for result in results if not result.ok]
    print(f"Finished: {len(results) - len(failed)} of {len(results)} videos without errors.")

    # Exit code 0 means success; anything else tells the caller that
    # at least one video failed.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
