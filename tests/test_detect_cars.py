"""Checks for finding cars with the detection model.

These need the detection libraries, the graphics card and the example video,
so they are skipped where any of those is missing.
"""

import importlib.util
import unittest

from pp_tt_video import settings
from pp_tt_video.video import read_frames

EXAMPLE_FOLDER = settings.PROJECT_FOLDER / "example video  and output file"
EXAMPLE_VIDEO = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 12-17.MP4"
LIBRARIES_PRESENT = importlib.util.find_spec("torch") is not None and importlib.util.find_spec("torchvision") is not None


@unittest.skipUnless(LIBRARIES_PRESENT and EXAMPLE_VIDEO.exists(), "detection libraries or example video missing")
class CarDetectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pp_tt_video.detect_cars import CarDetector
        cls.detector = CarDetector()   # loaded once for all checks in this class

    def test_car_that_has_just_overtaken_is_found(self):
        # At 01:10.6 in this example a car that has just passed is close ahead.
        frames = list(read_frames(EXAMPLE_VIDEO, start_seconds=70.6, duration_seconds=0.4))
        results = self.detector.detect(frames)
        self.assertEqual(len(results), len(frames))
        best = max(results[0], key=lambda box: box.confidence)
        self.assertGreater(best.confidence, 0.9)
        self.assertGreater(best.height / frames[0].height, settings.PASSING_CAR_HEIGHT)

    def test_empty_track_gives_no_confident_large_car(self):
        # At 01:06 the track ahead is empty.
        frames = list(read_frames(EXAMPLE_VIDEO, start_seconds=66.0, duration_seconds=0.2))
        boxes = self.detector.detect(frames)[0]
        large = [box for box in boxes
                 if box.confidence > 0.9 and box.height / frames[0].height > settings.CLOSE_CAR_HEIGHT]
        self.assertEqual(large, [])


if __name__ == "__main__":
    unittest.main()
