"""Runs the module by hand from a terminal.

Example, from the project folder:
    .venv\\Scripts\\python.exe -m pp_tt_video "path/to/video.mp4"
    .venv\\Scripts\\python.exe -m pp_tt_video "path/to/folder with videos"

Python runs this file when a package is started with "-m".
"""

import argparse
import sys

from pp_tt_video.pipeline import process_videos

# Remembers the last percentage shown, so each step is printed only once.
last_shown = {"percent": -1}


def show_start(number, total, video):
    """Tell the user which video is being worked on right now."""
    # flush=True shows the line at once instead of waiting for more output.
    print(f"[{number}/{total}] {video.name}: working ...", flush=True)
    last_shown["percent"] = -1


def show_progress(number, total, part):
    """Show how far the detection has got, in steps of 10 percent."""
    percent = int(part * 10) * 10
    if percent > last_shown["percent"]:
        last_shown["percent"] = percent
        print(f"[{number}/{total}]   detecting events: {percent}%", flush=True)


def show_done(number, total, result):
    """Tell the user how the video went."""
    status = "OK" if result.ok else "FAILED"
    print(f"[{number}/{total}] {status}: {result.message} ({result.seconds:.0f} s)", flush=True)


def main():
    parser = argparse.ArgumentParser(
        prog="pp_tt_video",
        description="Extract the GPS track and the events from GoPro trackday videos.",
    )
    parser.add_argument("inputs", nargs="+", help="video files, or folders that contain videos")
    parser.add_argument("--overwrite", action="store_true", help="replace output files that already exist")
    parser.add_argument("--output-folder", help="write the output files here instead of next to the videos")
    parser.add_argument("--gps-only", action="store_true", help="extract only the GPS tracks, detect no events")
    arguments = parser.parse_args()

    results = process_videos(
        arguments.inputs,
        overwrite=arguments.overwrite,
        output_folder=arguments.output_folder,
        with_events=not arguments.gps_only,
        on_start=show_start,
        on_progress=show_progress,
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
