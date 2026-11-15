"""Checks for collecting what the rules kept, what they dropped, and why."""

import unittest
from unittest import mock

from pp_tt_video import settings
from pp_tt_video.detect_cars import CarBox
from pp_tt_video.detect_events import timeline_from_detections
from pp_tt_video.explain import boxes_at, dropped_at, explain, labels_at
from pp_tt_video.profile import Profile, using_profile
from pp_tt_video.video import VideoInfo
from tests.helpers import RACING, ROLLING, car_box, detections_of, driving, pictures_of, repeat

VIDEO_SECONDS = 300


def gentle_driving():
    """Sensor data of a car that never drives at pace: all of it is warm up."""
    return driving([(force, 0.0) for force in repeat(ROLLING, VIDEO_SECONDS)])


def hard_driving():
    """Sensor data of a car at pace from the first second to the last."""
    return driving([(force, 0.0) for force in repeat(RACING, VIDEO_SECONDS)])


def overtaken_car(start=100.0):
    """Pictures of a car we catch and pass: it grows for 3 seconds, then is gone.

    Its height goes from 40 to 124 pixels of 720, well past the height at
    which a car counts as right next to us (0.11 of the picture, 79 pixels).
    """
    boxes = [car_box(640, 40 + number * 6) for number in range(15)]
    return pictures_of([boxes], start=start)


def all_boxes(explanation, kind):
    return [box for picture in explanation.pictures for box in getattr(picture, kind)]


class BoxesTest(unittest.TestCase):
    def test_kept_box_has_its_track_number_and_height(self):
        pictures = pictures_of([[car_box(640, 72)] * 5])
        explanation = explain(detections_of(pictures), [], 10.0)
        self.assertEqual(len(explanation.pictures), 5)
        for picture in explanation.pictures:
            self.assertEqual(picture.dropped, [])
            (shown,) = picture.kept
            self.assertEqual(shown.track_number, 1)
            self.assertAlmostEqual(shown.height_part, 0.1)
            self.assertEqual(shown.reason, "")
            self.assertEqual(shown.box, car_box(640, 72))

    def test_state_follows_the_car_heights(self):
        # Three cars far apart, each with a steady height: 36, 50 and 90 of
        # 720 pixels are 0.05, 0.069 and 0.125 of the picture. A car is
        # "close" from 0.0625 and "passing" from 0.11.
        cars = [[car_box(200, 36)] * 5, [car_box(640, 50)] * 5, [car_box(1050, 90)] * 5]
        detections = detections_of(pictures_of(cars))

        states = {shown.box.height: shown.state for shown in explain(detections, [], 10.0).pictures[2].kept}
        self.assertEqual(states, {36: "far", 50: "close", 90: "passing"})

        with using_profile(Profile("x", None, {"CLOSE_CAR_HEIGHT": 0.1})):
            states = {shown.box.height: shown.state for shown in explain(detections, [], 10.0).pictures[2].kept}
        self.assertEqual(states, {36: "far", 50: "far", 90: "passing"})

    def test_one_oversized_box_does_not_change_the_state(self):
        # The model draws one box far too large. The car rule smooths that
        # away before it decides, so the picture must not show "passing".
        heights = [36, 36, 80, 36, 36]
        pictures = pictures_of([[car_box(640, height) for height in heights]])
        explanation = explain(detections_of(pictures), [], 10.0)
        (shown,) = explanation.pictures[2].kept
        self.assertEqual(shown.box.height, 80)
        self.assertAlmostEqual(shown.height_part, 0.05)
        self.assertEqual(shown.state, "far")

    def test_too_wide_box_is_dropped_with_reason(self):
        cockpit = CarBox(200, 500, 900, 700, 0.8)   # 700 of 1280 pixels wide
        pictures = pictures_of([[car_box(640, 72)] * 3, [cockpit] * 3])
        explanation = explain(detections_of(pictures), [], 10.0)
        for picture in explanation.pictures:
            self.assertEqual([shown.box for shown in picture.kept], [car_box(640, 72)])
            (dropped,) = picture.dropped
            self.assertEqual(dropped.box, cockpit)
            self.assertEqual(dropped.reason, "too wide")
            self.assertIsNone(dropped.track_number)

    def test_double_box_is_dropped_with_reason(self):
        whole = CarBox(600, 300, 700, 360, 0.95)
        part = CarBox(610, 305, 690, 355, 0.6)     # inside the other, less sure
        explanation = explain(detections_of(pictures_of([[whole] * 3, [part] * 3])), [], 10.0)
        for picture in explanation.pictures:
            self.assertEqual([shown.box for shown in picture.kept], [whole])
            self.assertEqual([(shown.box, shown.reason) for shown in picture.dropped], [(part, "double")])

    def test_unsure_track_is_dropped_with_reason(self):
        # The model is never 0.9 sure of this car, so the car rules skip it.
        pictures = pictures_of([[car_box(640, 72, confidence=0.6)] * 5])
        explanation = explain(detections_of(pictures), [], 10.0)
        self.assertEqual(all_boxes(explanation, "kept"), [])
        dropped = all_boxes(explanation, "dropped")
        self.assertEqual(len(dropped), 5)
        self.assertEqual({shown.reason for shown in dropped}, {"never sure enough"})
        self.assertEqual({shown.track_number for shown in dropped}, {1})

    def test_two_cars_get_two_numbers(self):
        # The second car appears two pictures after the first.
        first = [car_box(300, 60)] * 6
        second = [None, None] + [car_box(900, 60)] * 4
        explanation = explain(detections_of(pictures_of([first, second])), [], 10.0)
        numbers = {shown.box.centre[0]: shown.track_number for shown in explanation.pictures[5].kept}
        self.assertEqual(numbers, {300: 1, 900: 2})
        self.assertEqual(len(explanation.tracks), 2)


class EventsTest(unittest.TestCase):
    def test_event_at_pace_is_kept(self):
        explanation = explain(detections_of(overtaken_car()), hard_driving(), VIDEO_SECONDS)
        self.assertEqual([stretch.label for stretch in explanation.kept_stretches], ["overtaking"])
        self.assertEqual(explanation.dropped_stretches, [])
        self.assertEqual(labels_at(explanation, 101.5), ("overtaking",))
        self.assertEqual(labels_at(explanation, 50.0), ("clear",))

    def test_event_outside_pace_is_dropped_with_reason(self):
        explanation = explain(detections_of(overtaken_car()), gentle_driving(), VIDEO_SECONDS)
        (dropped,) = explanation.dropped_stretches
        self.assertEqual(dropped.stretch.label, "overtaking")
        self.assertEqual(dropped.reason, "outside the part at pace")
        # The whole video is warm up; the overtaking is not in the timeline.
        self.assertEqual([event.labels for event in explanation.timeline], [("warm up",)])
        self.assertEqual([part.label for part in explanation.session_parts], ["warm up"])
        self.assertEqual(dropped_at(explanation, 101.5), [dropped])
        self.assertEqual(dropped_at(explanation, 50.0), [])

    def test_timeline_equals_the_normal_detection(self):
        detections = detections_of(overtaken_car())
        info = VideoInfo(width=5312, height=2988, frames_per_second=29.97,
                         duration_seconds=VIDEO_SECONDS, codec="hevc")
        for sensor_seconds in (hard_driving(), gentle_driving()):
            with mock.patch("pp_tt_video.detect_events.read_video_info", lambda video: info), \
                 mock.patch("pp_tt_video.detect_events.read_sensors", lambda video: sensor_seconds):
                normal = timeline_from_detections("x.mp4", detections)
            self.assertEqual(explain(detections, sensor_seconds, VIDEO_SECONDS).timeline, normal)

    def test_no_cars_and_no_sensors(self):
        pictures = [(number * 0.2, []) for number in range(10)]
        explanation = explain(detections_of(pictures), [], 2.0)
        self.assertEqual(all_boxes(explanation, "kept") + all_boxes(explanation, "dropped"), [])
        self.assertEqual([event.labels for event in explanation.timeline], [("clear",)])
        self.assertEqual(explanation.sensor_seconds, [])


class BoxesAtTest(unittest.TestCase):
    def setUp(self):
        pictures = [(0.0, [car_box(300, 60)]), (0.2, [car_box(310, 60)])]
        self.explanation = explain(detections_of(pictures), [], 10.0)

    def test_the_last_analysed_picture_is_used(self):
        self.assertEqual(boxes_at(self.explanation, 0.0).time_seconds, 0.0)
        self.assertEqual(boxes_at(self.explanation, 0.1).time_seconds, 0.0)
        self.assertEqual(boxes_at(self.explanation, 0.2).time_seconds, 0.2)
        self.assertEqual(boxes_at(self.explanation, 0.39).time_seconds, 0.2)

    def test_no_picture_when_the_last_one_is_too_old(self):
        self.assertIsNone(boxes_at(self.explanation, 5.0))

    def test_no_pictures_at_all(self):
        self.assertIsNone(boxes_at(explain(detections_of([]), [], 10.0), 1.0))


if __name__ == "__main__":
    unittest.main()
