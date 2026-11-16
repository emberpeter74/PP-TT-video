"""Step 9, part 1: find objects on the road (cones, so far).

A ready-made model does the finding. Unlike the car model it takes words:
it is told in plain English what to look for ("a traffic cone"), and for
every picture it returns boxes around what fits those words, each with a
score between 0 and 1. The words are in settings.OBJECT_WORDS.

The search goes over the video in its own pass, at its own picture rate,
and its result is saved (objects_file.py), because it is slow.

Run by hand from the project folder, to search videos and save the result:
    .venv\\Scripts\\python.exe -m pp_tt_video.find_objects "<video or folder>"
    ... --output-folder <folder>   write the objects files there
    ... --overwrite                search again, also where a file exists
"""

import argparse
import sys
import time
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.objects_file import (
    ObjectBox,
    Objects,
    ObjectsError,
    fits_settings,
    load_objects,
    objects_path_for,
    save_objects,
)
from pp_tt_video.video import VideoError, analysis_size, read_frames, read_video_info


class ObjectDetector:
    """Loads the model once and then searches as many pictures as asked."""

    def __init__(self, use_graphics_card=None):
        # The libraries are imported here, not at the top of the file, so
        # that the parts of the project that do not need them also run
        # without them.
        import torch
        from PIL import Image
        from transformers import Owlv2ForObjectDetection, Owlv2Processor

        if use_graphics_card is None:
            use_graphics_card = settings.USE_GRAPHICS_CARD
        self.torch = torch
        self.image = Image
        self.device = "cuda" if use_graphics_card and torch.cuda.is_available() else "cpu"

        # The "processor" prepares pictures and words for the model and
        # turns its answer back into boxes. Both are downloaded once and
        # kept on this PC afterwards.
        self.processor = Owlv2Processor.from_pretrained(settings.OBJECT_MODEL)
        self.model = Owlv2ForObjectDetection.from_pretrained(settings.OBJECT_MODEL)
        self.model.eval()            # "eval" = use the model, do not train it
        self.model.to(self.device)

        # The model answers with the number of the words that fit; these
        # two lists turn that number back into the kind of object.
        self.kinds = list(settings.OBJECT_WORDS)
        self.words = [settings.OBJECT_WORDS[kind] for kind in self.kinds]

    def detect(self, frames):
        """Search a list of frames.

        Returns one list of ObjectBox per frame, in the same order.
        """
        if not frames:
            return []
        torch = self.torch
        pictures = [self.image.frombytes("RGB", (frame.width, frame.height), frame.pixels) for frame in frames]
        inputs = self.processor(text=[self.words] * len(pictures), images=pictures, return_tensors="pt")
        inputs = inputs.to(self.device)

        # no_grad: we only want answers, so skip the bookkeeping for training.
        with torch.no_grad():
            answers = self.model(**inputs)

        # The model looks at a square picture: ours is put in its top left
        # corner and the rest is filled up. So the boxes are asked for in a
        # square as large as our longest side; they then come back in the
        # pixels of our own picture.
        squares = [[max(frame.width, frame.height)] * 2 for frame in frames]
        found = self.processor.post_process_grounded_object_detection(
            answers, threshold=settings.OBJECT_MIN_CONFIDENCE, target_sizes=torch.tensor(squares))

        results = []
        for answer in found:
            results.append([
                ObjectBox(self.kinds[number], *position, confidence)
                for position, number, confidence in zip(
                    answer["boxes"].tolist(), answer["labels"].tolist(), answer["scores"].tolist())
            ])
        return results


def find_objects(video_path, detector, on_progress=None):
    """The slow part: have the model search every picture of a video.

    Returns the Objects: every box of every searched picture. They can be
    saved (objects_file.py) and used again without searching a second time.
    on_progress(part), if given, is called with the part done so far (0 to 1).
    """
    info = read_video_info(video_path)
    width, height = analysis_size(info)
    pictures = []

    batch = []

    def handle_batch():
        for frame, boxes in zip(batch, detector.detect(batch)):
            pictures.append((frame.time_seconds, boxes))
        if on_progress and info.duration_seconds:
            on_progress(min(1.0, batch[-1].time_seconds / info.duration_seconds))
        batch.clear()

    for frame in read_frames(video_path, frames_per_second=settings.OBJECT_FRAMES_PER_SECOND):
        batch.append(frame)
        if len(batch) >= settings.OBJECT_BATCH_SIZE:
            handle_batch()
    if batch:
        handle_batch()

    return Objects(
        analysis_width=width,
        picture_height=height,
        frames_per_second=settings.OBJECT_FRAMES_PER_SECOND,
        min_confidence=settings.OBJECT_MIN_CONFIDENCE,
        model=settings.OBJECT_MODEL,
        words=dict(settings.OBJECT_WORDS),
        pictures=pictures,
    )


def objects_file_for(video_path, detector, output_folder=None, overwrite=False, on_progress=None):
    """Return the objects of a video, searching only when that is needed.

    A file from an earlier run is used again, unless overwrite is set or the
    file does not fit (half-written, or made with other settings). After a
    search the file is written.
    Returns (objects, searched): searched is False when the file was used.
    """
    path = objects_path_for(video_path, output_folder)
    if path.exists() and not overwrite:
        try:
            saved = load_objects(path)
            if fits_settings(saved):
                return saved, False
        except ObjectsError:
            pass   # not usable: search again and replace it
    objects = find_objects(video_path, detector, on_progress)
    save_objects(path, objects)
    return objects, True


def main():
    parser = argparse.ArgumentParser(
        prog="pp_tt_video.find_objects",
        description="Search videos for objects on the road and save what is found.",
    )
    parser.add_argument("inputs", nargs="+", help="video files, or folders that contain videos")
    parser.add_argument("--overwrite", action="store_true", help="search again, also where an objects file exists")
    parser.add_argument("--output-folder", help="write the objects files here instead of next to the videos")
    arguments = parser.parse_args()

    # Imported here: pipeline.py knows how a folder becomes a list of videos.
    from pp_tt_video.pipeline import find_videos

    videos = find_videos(arguments.inputs)
    if not videos:
        print("No videos found.")
        return 1
    try:
        detector = ObjectDetector()
    except ImportError as error:
        print(f"FAILED: detection libraries are not installed ({error})")
        return 1

    failed = False
    for number, video in enumerate(videos, start=1):
        print(f"[{number}/{len(videos)}] {Path(video).name}", flush=True)
        started = time.monotonic()
        try:
            objects, searched = objects_file_for(video, detector, arguments.output_folder, arguments.overwrite)
        except (VideoError, OSError) as error:
            print(f"    FAILED: {error}")
            failed = True
            continue
        boxes = sum(len(found) for _, found in objects.pictures)
        how = f"searched in {time.monotonic() - started:.0f} s" if searched else "objects file already exists, used"
        print(f"    {len(objects.pictures)} pictures, {boxes} boxes; {how}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
