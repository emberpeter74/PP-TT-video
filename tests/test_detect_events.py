"""Checks for building the car tracks from saved detections."""

import unittest

from pp_tt_video import settings
from pp_tt_video.detect_cars import CarBox, keep_car_boxes
from pp_tt_video.detect_events import tracks_from_detections
from pp_tt_video.detections_file import Detections
from pp_tt_video.tracking import Tracker


def detections_of(pictures):
    return Detections(
        analysis_width=1280,
        picture_height=720,
        frames_per_second=settings.ANALYSIS_FRAMES_PER_SECOND,
        min_confidence=settings.MIN_DETECTION_CONFIDENCE,
        pictures=pictures,
    )


class TracksFromDetectionsTest(unittest.TestCase):
    def test_tracks_match_feeding_the_tracker(self):
        # One car ahead that grows a little in every picture, and in every
        # picture a box 700 pixels wide: the own cockpit, which must be
        # thrown away before the tracker sees it.
        pictures = []
        for number in range(10):
            grow = number * 4
            car = CarBox(600 - grow, 300 - grow, 680 + grow, 360 + grow, 0.95)
            cockpit = CarBox(200, 500, 900, 700, 0.8)
            pictures.append((number * 0.2, [car, cockpit]))

        tracks, picture_height = tracks_from_detections(detections_of(pictures))

        tracker = Tracker()
        for time, boxes in pictures:
            tracker.add_picture(time, keep_car_boxes(boxes, 1280))
        self.assertEqual(tracks, tracker.finish())
        self.assertEqual(picture_height, 720)
        # Said plainly as well: one car, seen ten times, the cockpit never.
        self.assertEqual(len(tracks), 1)
        self.assertEqual(len(tracks[0].sightings), 10)
        self.assertEqual(tracks[0].sightings[0].box.left, 600)

    def test_no_cars_gives_no_tracks(self):
        pictures = [(number * 0.2, []) for number in range(5)]
        self.assertEqual(tracks_from_detections(detections_of(pictures)), ([], 720))


if __name__ == "__main__":
    unittest.main()
