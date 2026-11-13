"""Measures how fast a video can be read in reduced form.

Run by hand from the project folder:
    py -V:3.13 -m pp_tt_video.measure_speed "path/to/video.mp4"
    py -V:3.13 -m pp_tt_video.measure_speed "path/to/video.mp4" --seconds 60
"""

import argparse
import sys
import time

from pp_tt_video.video import VideoError, read_frames, read_video_info


def main():
    parser = argparse.ArgumentParser(
        prog="pp_tt_video.measure_speed",
        description="Measure how fast a video is read in reduced form.",
    )
    parser.add_argument("video", help="the video file")
    parser.add_argument("--seconds", type=float, help="read only this much of the video")
    parser.add_argument("--processor", action="store_true", help="decode on the processor, not the graphics card")
    arguments = parser.parse_args()

    try:
        info = read_video_info(arguments.video)
        print(f"Video: {info.width}x{info.height}, {info.frames_per_second:.2f} frames per second, "
              f"{info.duration_seconds:.0f} s long, format {info.codec}")

        started = time.monotonic()
        count = 0
        frame = None
        for frame in read_frames(arguments.video, duration_seconds=arguments.seconds,
                                 use_graphics_card=False if arguments.processor else None):
            count += 1
            if count % 500 == 0:
                print(f"  {count} frames read, at {frame.time_seconds:.0f} s in the video", flush=True)
        elapsed = time.monotonic() - started
    except VideoError as error:
        print(f"FAILED: {error}")
        return 1

    if frame is None:
        print("No frames were read.")
        return 1
    video_seconds = frame.time_seconds
    print(f"Read {count} frames of {frame.width}x{frame.height} in {elapsed:.1f} s.")
    print(f"That is {video_seconds / elapsed:.1f} times faster than real time.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
