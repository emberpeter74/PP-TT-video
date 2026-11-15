"""Saves the cars found in a video, and loads them again.

Finding the cars is the slow part of the detection: about a third of the
video's length. Everything after it (following the cars, the rules) takes
seconds. So the boxes the model found are saved once, and the check video
and any later tuning work from the saved copy.

What is saved is what the model gave: every vehicle box of every analysed
picture, before anything is thrown away. The file is in JSON, a text format
that Python reads and writes directly.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.detect_cars import CarBox


class DetectionsError(Exception):
    """Raised when a detections file cannot be read."""


@dataclass
class Detections:
    """The cars found in one video, and how the pictures were analysed."""

    analysis_width: int        # width of the analysed pictures, in pixels
    picture_height: int        # their height
    frames_per_second: float   # how many pictures per second were analysed
    min_confidence: float      # finds below this were not kept by the model
    pictures: list             # one (time in seconds, [CarBox, ...]) per analysed picture


def detections_path_for(video_path, output_folder=None):
    """Return where the detections file for a video belongs.

    Naming rule: "something.mp4" gives "something-detections.json".
    """
    video_path = Path(video_path)
    folder = Path(output_folder) if output_folder else video_path.parent
    return folder / (video_path.stem + "-detections.json")


def save_detections(path, detections):
    """Write the detections to a file.

    The file is written under a temporary name and renamed when complete,
    so an interrupted run never leaves half a file.
    """
    path = Path(path)
    content = {
        "analysis_width": detections.analysis_width,
        "picture_height": detections.picture_height,
        "frames_per_second": detections.frames_per_second,
        "min_confidence": detections.min_confidence,
        "pictures": [
            {
                "time": time,
                "boxes": [[box.left, box.top, box.right, box.bottom, box.confidence] for box in boxes],
            }
            for time, boxes in detections.pictures
        ],
    }
    part = path.with_name(path.name + ".part")
    # json writes numbers so that they read back exactly as they were.
    part.write_text(json.dumps(content), encoding="utf-8")
    part.replace(path)


def load_detections(path):
    """Read a detections file. Raises DetectionsError when it cannot be used."""
    path = Path(path)
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
        return Detections(
            analysis_width=content["analysis_width"],
            picture_height=content["picture_height"],
            frames_per_second=content["frames_per_second"],
            min_confidence=content["min_confidence"],
            pictures=[
                (picture["time"], [CarBox(*values) for values in picture["boxes"]])
                for picture in content["pictures"]
            ],
        )
    # A missing file, a half-written one, or one with parts missing.
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise DetectionsError(f"Detections file {path.name} cannot be read: {error}")


def fits_settings(detections):
    """True when a detection run today would analyse the video the same way.

    Detections made with another picture size, picture rate or lowest
    confidence must not be reused: the rules would get different boxes than
    a fresh detection gives.
    """
    return (
        detections.analysis_width == settings.ANALYSIS_WIDTH
        and detections.frames_per_second == settings.ANALYSIS_FRAMES_PER_SECOND
        and detections.min_confidence == settings.MIN_DETECTION_CONFIDENCE
    )
