"""Processes a set of videos, one after the other.

This is the function the main program will call later. Running the module by
hand (see __main__.py) uses the same function.
"""

import time
from dataclasses import dataclass
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.gps import GpsExtractionError, extract_gps


@dataclass
class FileResult:
    """What happened to one video."""

    video: Path
    ok: bool            # False only when something went wrong
    message: str        # a short text for the user
    seconds: float = 0  # how long the processing took


def find_videos(inputs):
    """Turn a list of files and folders into a list of video files.

    A folder stands for all video files directly inside it.
    """
    videos = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            for entry in sorted(path.iterdir()):
                if entry.is_file() and entry.suffix.lower() in settings.VIDEO_EXTENSIONS:
                    videos.append(entry)
        else:
            videos.append(path)
    return videos


def process_video(video, overwrite=False):
    """Process one video and return a FileResult. Never raises an error."""
    started = time.monotonic()
    try:
        gpx_path = extract_gps(video, overwrite=overwrite)
        ok, message = True, f"GPS written to {gpx_path.name}"
    except FileExistsError:
        ok, message = True, "GPX file already exists, skipped"
    except GpsExtractionError as error:
        ok, message = False, str(error)
    return FileResult(video, ok, message, time.monotonic() - started)


def process_videos(inputs, overwrite=False, on_start=None, on_done=None):
    """Process every video and return one FileResult per video.

    Each video is handled on its own: a failure is recorded and the run
    continues with the next video.

    To follow the progress, the caller can pass two functions:
      on_start(number, total, video)  is called before a video is processed,
      on_done(number, total, result)  is called as soon as it is finished.
    """
    videos = find_videos(inputs)
    total = len(videos)
    results = []
    # enumerate numbers the videos: 1, 2, 3, ...
    for number, video in enumerate(videos, start=1):
        if on_start:
            on_start(number, total, video)
        result = process_video(video, overwrite=overwrite)
        results.append(result)
        if on_done:
            on_done(number, total, result)
    return results
