"""Checks for saving the car detections of a video and loading them again."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pp_tt_video import settings
from pp_tt_video.detect_cars import CarBox
from pp_tt_video.detections_file import (
    Detections,
    DetectionsError,
    detections_path_for,
    fits_settings,
    load_detections,
    save_detections,
)


def some_detections():
    """Two analysed pictures: one with two cars, one with none."""
    return Detections(
        analysis_width=settings.ANALYSIS_WIDTH,
        picture_height=720,
        frames_per_second=settings.ANALYSIS_FRAMES_PER_SECOND,
        min_confidence=settings.MIN_DETECTION_CONFIDENCE,
        pictures=[
            # 0.1 + 0.2 is 0.30000000000000004 in a computer: an awkward
            # number that must come back exactly as it was saved.
            (0.0, [CarBox(100.5, 200.25, 300.75, 0.1 + 0.2, 0.93), CarBox(1.0, 2.0, 3.0, 4.0, 0.5)]),
            (0.2, []),
        ],
    )


class DetectionsFileTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.path = self.folder / "x-detections.json"

    def test_path(self):
        self.assertEqual(detections_path_for(Path("a") / "x.MP4"), Path("a") / "x-detections.json")
        self.assertEqual(detections_path_for(Path("a") / "x.MP4", "out"), Path("out") / "x-detections.json")

    def test_save_and_load_give_the_same_boxes(self):
        save_detections(self.path, some_detections())
        loaded = load_detections(self.path)
        self.assertEqual(loaded, some_detections())
        self.assertEqual(loaded.pictures[0][1][0].bottom, 0.1 + 0.2)
        self.assertEqual(loaded.pictures[1], (0.2, []))

    def test_no_part_file_is_left_behind(self):
        save_detections(self.path, some_detections())
        self.assertEqual([entry.name for entry in self.folder.iterdir()], ["x-detections.json"])

    def test_fits_settings(self):
        detections = some_detections()
        self.assertTrue(fits_settings(detections))
        # Detections made with another picture size, picture rate or lowest
        # confidence are not what a detection would give today.
        for name, value in [("ANALYSIS_WIDTH", 640), ("ANALYSIS_FRAMES_PER_SECOND", 10),
                            ("MIN_DETECTION_CONFIDENCE", 0.3)]:
            with mock.patch.object(settings, name, value):
                self.assertFalse(fits_settings(detections), name)

    def test_broken_file_is_refused(self):
        self.path.write_text('{"analysis_width": 1280, "pictures": [', encoding="utf-8")
        with self.assertRaises(DetectionsError):
            load_detections(self.path)

    def test_file_with_missing_parts_is_refused(self):
        self.path.write_text('{"analysis_width": 1280}', encoding="utf-8")
        with self.assertRaises(DetectionsError):
            load_detections(self.path)


if __name__ == "__main__":
    unittest.main()
