"""Checks for searching a video for objects (cones, so far).

The first part works with stand-ins and needs no model. The second part
needs the detection libraries, the graphics card and the example video, so
it is skipped where any of those is missing.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pp_tt_video import find_objects, settings
from pp_tt_video.objects_file import ObjectBox, load_objects, objects_path_for, save_objects
from pp_tt_video.video import Frame, VideoInfo, read_frames

EXAMPLE_FOLDER = settings.PROJECT_FOLDER / "example video  and output file"
EXAMPLE_VIDEO = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 12-17.MP4"
LIBRARIES_PRESENT = all(importlib.util.find_spec(name) is not None for name in ("torch", "transformers", "PIL"))

INFO = VideoInfo(width=3840, height=2160, frames_per_second=30, duration_seconds=1.0, codec="hevc")


class StandInDetector:
    """Finds one cone in every picture, without a model."""

    def __init__(self):
        self.batches = []

    def detect(self, frames):
        self.batches.append(len(frames))
        return [[ObjectBox("cone", 10, 20, 40, 35, 0.5)] for _ in frames]


def five_frames(video_path, frames_per_second=None, **_):
    """Stands in for read_frames: five tiny pictures, 0.2 seconds apart."""
    for number in range(5):
        yield Frame(time_seconds=number * 0.2, width=4, height=2, pixels=bytes(4 * 2 * 3))


class FindObjectsTest(unittest.TestCase):
    def setUp(self):
        for name, stand_in in [("read_frames", five_frames), ("read_video_info", lambda path: INFO)]:
            patcher = mock.patch.object(find_objects, name, stand_in)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_every_picture_gets_its_boxes(self):
        objects = find_objects.find_objects("x.mp4", StandInDetector())
        self.assertEqual([time for time, _ in objects.pictures], [0.0, 0.2, 0.4, 0.6000000000000001, 0.8])
        self.assertEqual(objects.pictures[0][1], [ObjectBox("cone", 10, 20, 40, 35, 0.5)])

    def test_header_says_how_the_search_was_done(self):
        objects = find_objects.find_objects("x.mp4", StandInDetector())
        self.assertEqual(objects.analysis_width, settings.ANALYSIS_WIDTH)
        self.assertEqual(objects.picture_height, 720)
        self.assertEqual(objects.frames_per_second, settings.OBJECT_FRAMES_PER_SECOND)
        self.assertEqual(objects.min_confidence, settings.OBJECT_MIN_CONFIDENCE)
        self.assertEqual(objects.model, settings.OBJECT_MODEL)
        self.assertEqual(objects.words, settings.OBJECT_WORDS)

    def test_pictures_are_read_at_the_object_rate(self):
        asked = {}

        def remember(video_path, frames_per_second=None, **_):
            asked["rate"] = frames_per_second
            return five_frames(video_path)

        with mock.patch.object(find_objects, "read_frames", remember), \
                mock.patch.object(settings, "OBJECT_FRAMES_PER_SECOND", 3):
            find_objects.find_objects("x.mp4", StandInDetector())
        self.assertEqual(asked["rate"], 3)

    def test_pictures_are_handed_over_in_batches(self):
        detector = StandInDetector()
        with mock.patch.object(settings, "OBJECT_BATCH_SIZE", 2):
            find_objects.find_objects("x.mp4", detector)
        self.assertEqual(detector.batches, [2, 2, 1])

    def test_progress_ends_at_one(self):
        parts = []
        find_objects.find_objects("x.mp4", StandInDetector(), parts.append)
        self.assertTrue(parts)
        self.assertEqual(parts, sorted(parts))
        self.assertLessEqual(parts[-1], 1.0)
        self.assertGreater(parts[-1], 0.5)

    def test_video_without_pictures_gives_no_pictures(self):
        with mock.patch.object(find_objects, "read_frames", lambda *a, **k: iter(())):
            objects = find_objects.find_objects("x.mp4", StandInDetector())
        self.assertEqual(objects.pictures, [])


class ObjectsFileForTest(unittest.TestCase):
    """The command's work for one video: search, or use the file that is there."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.video = self.folder / "x.mp4"
        self.video.write_bytes(b"")
        for name, stand_in in [("read_frames", five_frames), ("read_video_info", lambda path: INFO)]:
            patcher = mock.patch.object(find_objects, name, stand_in)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_file_is_written(self):
        detector = StandInDetector()
        objects, searched = find_objects.objects_file_for(self.video, detector)
        self.assertTrue(searched)
        self.assertEqual(load_objects(objects_path_for(self.video)), objects)

    def test_fitting_file_is_used_again(self):
        find_objects.objects_file_for(self.video, StandInDetector())
        detector = StandInDetector()
        objects, searched = find_objects.objects_file_for(self.video, detector)
        self.assertFalse(searched)
        self.assertEqual(detector.batches, [])
        self.assertEqual(len(objects.pictures), 5)

    def test_overwrite_searches_again(self):
        find_objects.objects_file_for(self.video, StandInDetector())
        detector = StandInDetector()
        _, searched = find_objects.objects_file_for(self.video, detector, overwrite=True)
        self.assertTrue(searched)
        self.assertTrue(detector.batches)

    def test_file_that_does_not_fit_is_replaced(self):
        find_objects.objects_file_for(self.video, StandInDetector())
        with mock.patch.object(settings, "OBJECT_MIN_CONFIDENCE", 0.4):
            objects, searched = find_objects.objects_file_for(self.video, StandInDetector())
            self.assertTrue(searched)
            self.assertEqual(load_objects(objects_path_for(self.video)).min_confidence, 0.4)

    def test_broken_file_is_replaced(self):
        objects_path_for(self.video).write_text("{", encoding="utf-8")
        objects, searched = find_objects.objects_file_for(self.video, StandInDetector())
        self.assertTrue(searched)
        self.assertEqual(load_objects(objects_path_for(self.video)), objects)

    def test_output_folder(self):
        out = self.folder / "out"
        out.mkdir()
        find_objects.objects_file_for(self.video, StandInDetector(), output_folder=out)
        self.assertTrue((out / "x-objects.json").exists())
        self.assertFalse(objects_path_for(self.video).exists())


@unittest.skipUnless(LIBRARIES_PRESENT and EXAMPLE_VIDEO.exists(), "detection libraries or example video missing")
class ObjectDetectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = find_objects.ObjectDetector()   # loaded once for all checks in this class
        # At 02:28 in this example a knocked-over cone lies at the edge of the road, close by.
        cls.frames = list(read_frames(EXAMPLE_VIDEO, start_seconds=148.0, duration_seconds=0.4,
                                      frames_per_second=5))
        cls.results = cls.detector.detect(cls.frames)

    def test_one_list_per_picture(self):
        self.assertEqual(len(self.results), len(self.frames))
        self.assertGreater(len(self.frames), 1)

    def test_near_cone_is_found_where_it_is(self):
        best = max(self.results[0], key=lambda box: box.confidence)
        self.assertEqual(best.kind, "cone")
        self.assertGreater(best.confidence, 0.5)
        x, y = best.centre
        # The positions are in the pixels of the reduced picture.
        self.assertTrue(770 < x < 810 and 370 < y < 410, (x, y))

    def test_no_box_is_as_wide_as_half_the_picture(self):
        for boxes, frame in zip(self.results, self.frames):
            for box in boxes:
                self.assertLess(box.width, frame.width / 2)

    def test_nothing_below_the_lowest_score(self):
        for boxes in self.results:
            for box in boxes:
                self.assertGreaterEqual(box.confidence, settings.OBJECT_MIN_CONFIDENCE)


if __name__ == "__main__":
    unittest.main()
