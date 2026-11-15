"""Checks for drawing one picture of the check video.

Text cannot be read back from a picture, so these checks look at single
pixels (is the edge of a box coloured, is its middle untouched) and compare
whole areas of two drawings.
"""

import unittest
from unittest import mock

from PIL import Image

from pp_tt_video import check_video_settings
from pp_tt_video.detect_cars import CarBox
from pp_tt_video.draw import draw_picture, picture_size
from pp_tt_video.explain import explain
from tests.helpers import car_box, detections_of, pictures_of

BLACK = (0, 0, 0)
BOX = CarBox(100, 300, 300, 450, 0.95)   # 150 of 720 pixels tall: "passing"
EDGE = (100, 375)      # a point on the left edge of BOX
MIDDLE = (200, 375)    # a point in the middle of BOX
TOP_LEFT = (0, 0, 640, 60)       # where the event line is written
TOP_RIGHT = (640, 0, 1280, 60)   # where the profile and the time are written


def black_picture():
    return Image.new("RGB", (1280, 720), BLACK)


def explanation_with(boxes_per_car):
    return explain(detections_of(pictures_of(boxes_per_car)), [], 10.0)


def setting(name, value):
    """Change one setting of the check video for the length of a check."""
    return mock.patch.object(check_video_settings, name, value)


class PictureSizeTest(unittest.TestCase):
    def test_picture_size_is_even(self):
        self.assertEqual(picture_size(1280, 720, 240), (1280, 960))
        self.assertEqual(picture_size(1280, 720, 241), (1280, 962))
        self.assertEqual(picture_size(1280, 960, 240), (1280, 1200))
        self.assertEqual(picture_size(1280, 720, 0), (1280, 720))


class DrawPictureTest(unittest.TestCase):
    def setUp(self):
        self.explanation = explanation_with([[BOX] * 5])

    def draw(self, time_seconds=0.0, explanation=None, profile_name="built-in values"):
        return draw_picture(black_picture(), time_seconds, explanation or self.explanation, profile_name)

    def test_drawn_picture_has_the_right_size(self):
        self.assertEqual(self.draw().size, picture_size(1280, 720, 0))

    def test_the_given_picture_is_not_changed(self):
        picture = black_picture()
        draw_picture(picture, 0.0, self.explanation, "built-in values")
        self.assertEqual(picture.getpixel(EDGE), BLACK)

    def test_kept_box_is_drawn(self):
        drawn = self.draw()
        self.assertNotEqual(drawn.getpixel(EDGE), BLACK)
        self.assertEqual(drawn.getpixel(MIDDLE), BLACK)   # only the outline, the car stays visible

    def test_box_colour_follows_the_state(self):
        far = explanation_with([[car_box(200, 36)] * 5])       # left edge at x = 164
        passing = explanation_with([[car_box(200, 150)] * 5])  # left edge at x = 50
        self.assertNotEqual(self.draw(explanation=far).getpixel((164, 360)),
                            self.draw(explanation=passing).getpixel((50, 360)))

    def test_boxes_can_be_switched_off(self):
        with setting("SHOW_KEPT_BOXES", False):
            self.assertEqual(self.draw().getpixel(EDGE), BLACK)

    def test_box_details_can_be_switched_off(self):
        # The label sits just above the box.
        above_the_box = (100, 260, 400, 299)
        with_details = self.draw().crop(above_the_box)
        with setting("SHOW_BOX_DETAILS", False):
            without = self.draw().crop(above_the_box)
        self.assertNotEqual(with_details.tobytes(), without.tobytes())
        # getextrema gives the darkest and brightest value of red, green and
        # blue: all (0, 0) means the whole area is black.
        self.assertEqual(without.getextrema(), ((0, 0), (0, 0), (0, 0)))

    def test_event_line_can_be_switched_off(self):
        with_events = self.draw().crop(TOP_LEFT)
        with setting("SHOW_EVENTS", False):
            without = self.draw().crop(TOP_LEFT)
        self.assertNotEqual(with_events.tobytes(), without.tobytes())
        # getextrema gives the darkest and brightest value of red, green and
        # blue: all (0, 0) means the whole area is black.
        self.assertEqual(without.getextrema(), ((0, 0), (0, 0), (0, 0)))

    def test_profile_name_is_written(self):
        one = self.draw(profile_name="son").crop(TOP_RIGHT)
        other = self.draw(profile_name="built-in values").crop(TOP_RIGHT)
        self.assertNotEqual(one.tobytes(), other.tobytes())

    def test_time_is_written(self):
        self.assertNotEqual(self.draw(0.0).crop(TOP_RIGHT).tobytes(), self.draw(7.0).crop(TOP_RIGHT).tobytes())

    def test_time_without_boxes_does_not_fail(self):
        drawn = self.draw(time_seconds=9.0)   # long after the last analysed picture
        self.assertEqual(drawn.getpixel(EDGE), BLACK)

    def test_video_without_any_car_does_not_fail(self):
        empty = explain(detections_of([(0.0, [])]), [], 10.0)
        self.assertEqual(self.draw(explanation=empty).getpixel(EDGE), BLACK)


if __name__ == "__main__":
    unittest.main()
