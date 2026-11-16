"""Saves the objects found in a video (cones, so far), and loads them again.

Searching a video for objects is the slowest part of the work: longer than
the video itself. Everything after it (the rules) takes seconds. So the
boxes the model found are saved once, next to the other output files, and
later runs and any tuning work from the saved copy.

What is saved is what the model gave: every box of every searched picture,
also the ones it was not very sure of. The rules decide later what counts.
The file is in JSON, a text format that Python reads and writes directly.

This file is separate from the car detections (detections_file.py): the two
are made by different models, at different picture rates.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from pp_tt_video import settings


class ObjectsError(Exception):
    """Raised when an objects file cannot be read."""


@dataclass(frozen=True)
class ObjectBox:
    """A box around one object in one picture. Positions are in pixels."""

    kind: str           # what it is: a name from settings.OBJECT_WORDS, for example "cone"
    left: float
    top: float
    right: float
    bottom: float
    confidence: float   # how sure the model is, from 0 to 1

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    @property
    def centre(self):
        return ((self.left + self.right) / 2, (self.top + self.bottom) / 2)


@dataclass
class Objects:
    """The objects found in one video, and how the pictures were searched."""

    analysis_width: int        # width of the searched pictures, in pixels
    picture_height: int        # their height
    frames_per_second: float   # how many pictures per second were searched
    min_confidence: float      # finds below this were not kept
    model: str                 # the name of the model that searched
    words: dict                # kind -> the words the model was given
    pictures: list             # one (time in seconds, [ObjectBox, ...]) per searched picture


def objects_path_for(video_path, output_folder=None):
    """Return where the objects file for a video belongs.

    Naming rule: "something.mp4" gives "something-objects.json".
    """
    video_path = Path(video_path)
    folder = Path(output_folder) if output_folder else video_path.parent
    return folder / (video_path.stem + "-objects.json")


def save_objects(path, objects):
    """Write the objects to a file.

    The file is written under a temporary name and renamed when complete,
    so an interrupted run never leaves half a file.
    """
    path = Path(path)
    content = {
        "analysis_width": objects.analysis_width,
        "picture_height": objects.picture_height,
        "frames_per_second": objects.frames_per_second,
        "min_confidence": objects.min_confidence,
        "model": objects.model,
        "words": objects.words,
        "pictures": [
            {
                "time": time,
                "boxes": [[box.kind, box.left, box.top, box.right, box.bottom, box.confidence] for box in boxes],
            }
            for time, boxes in objects.pictures
        ],
    }
    part = path.with_name(path.name + ".part")
    # json writes numbers so that they read back exactly as they were.
    part.write_text(json.dumps(content), encoding="utf-8")
    part.replace(path)


def load_objects(path):
    """Read an objects file. Raises ObjectsError when it cannot be used."""
    path = Path(path)
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
        return Objects(
            analysis_width=content["analysis_width"],
            picture_height=content["picture_height"],
            frames_per_second=content["frames_per_second"],
            min_confidence=content["min_confidence"],
            model=content["model"],
            words=dict(content["words"]),
            pictures=[
                (picture["time"], [ObjectBox(*values) for values in picture["boxes"]])
                for picture in content["pictures"]
            ],
        )
    # A missing file, a half-written one, or one with parts missing.
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ObjectsError(f"Objects file {path.name} cannot be read: {error}")


def fits_settings(objects):
    """True when a search today would look at the video in the same way.

    Objects found with another picture size, picture rate, lowest score,
    model or words must not be reused: the rules would get different boxes
    than a fresh search gives.
    """
    return (
        objects.analysis_width == settings.ANALYSIS_WIDTH
        and objects.frames_per_second == settings.OBJECT_FRAMES_PER_SECOND
        and objects.min_confidence == settings.OBJECT_MIN_CONFIDENCE
        and objects.model == settings.OBJECT_MODEL
        and objects.words == settings.OBJECT_WORDS
    )
