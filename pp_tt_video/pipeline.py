"""Processes a set of videos, one after the other.

This is the function the main program will call later. Running the module by
hand (see __main__.py) uses the same function.
"""

from dataclasses import dataclass
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.gps import GpsExtractionError, extract_gps


@dataclass
class FileResult:
    """What happened to one video."""

    video: Path
    ok: bool        # False only when something went wrong
    message: str    # a short text for the user


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


def process_videos(inputs, overwrite=False):
    """Process every video and return one FileResult per video.

    Each video is handled on its own: a failure is recorded and the run
    continues with the next video.
    """
    results = []
    for video in find_videos(inputs):
        try:
            gpx_path = extract_gps(video, overwrite=overwrite)
            results.append(FileResult(video, True, f"GPS written to {gpx_path.name}"))
        except FileExistsError:
            results.append(FileResult(video, True, "GPX file already exists, skipped"))
        except GpsExtractionError as error:
            results.append(FileResult(video, False, str(error)))
    return results
