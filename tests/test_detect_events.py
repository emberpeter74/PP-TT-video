"""Checks for building the car tracks from saved detections."""

import unittest
from unittest import mock

from pp_tt_video import detect_events, settings
from pp_tt_video.detect_cars import CarBox, keep_car_boxes
from pp_tt_video.detect_events import tracks_from_detections
from pp_tt_video.detections_file import Detections
from pp_tt_video.stretch import Stretch
from pp_tt_video.tracking import Tracker
from tests.helpers import cone_box, objects_of


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


class ObstaclesInTimelineTest(unittest.TestCase):
    """The knocked-over cones go into the timeline, like every other event.

    The video and its sensors are stand-ins: a 60-second video whose first
    20 seconds are a warm-up lap.
    """

    def setUp(self):
        from pp_tt_video.video import VideoInfo
        info = VideoInfo(width=5312, height=2988, frames_per_second=29.97, duration_seconds=60.0, codec="hevc")
        warm_up = Stretch(0.0, 20.0, settings.WARM_UP_LABEL)
        for name, stand_in in [("read_video_info", lambda video: info),
                               ("detect_from_sensors", lambda video, duration: ([warm_up], []))]:
            patcher = mock.patch.object(detect_events, name, stand_in)
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def labels_of(timeline):
        return [label for event in timeline for label in event.labels]

    @staticmethod
    def lying_cone_at(time):
        return objects_of([(time, [cone_box(600, 30, 15, 0.4)])])

    def test_lying_cone_at_pace_is_an_obstacle(self):
        timeline = detect_events.timeline_from_detections("x.mp4", detections_of([]), self.lying_cone_at(30.0))
        self.assertIn("obstacle", self.labels_of(timeline))
        obstacle = next(event for event in timeline if "obstacle" in event.labels)
        self.assertEqual(obstacle.start, 30)

    def test_lying_cone_outside_the_part_at_pace_is_dropped(self):
        timeline = detect_events.timeline_from_detections("x.mp4", detections_of([]), self.lying_cone_at(5.0))
        self.assertNotIn("obstacle", self.labels_of(timeline))

    def test_without_objects_the_timeline_is_as_before(self):
        without = detect_events.timeline_from_detections("x.mp4", detections_of([]))
        empty = detect_events.timeline_from_detections("x.mp4", detections_of([]), objects_of([]))
        self.assertEqual(without, empty)
        self.assertNotIn("obstacle", self.labels_of(without))


if __name__ == "__main__":
    unittest.main()
