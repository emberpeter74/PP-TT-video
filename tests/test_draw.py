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
from pp_tt_video.draw import draw_picture, full_picture_size, picture_size
from pp_tt_video.explain import explain
from pp_tt_video.profile import Profile, using_profile
from tests.helpers import car_box, cone_box, detections_of, objects_of, pictures_of
from tests.test_explain import VIDEO_SECONDS, gentle_driving, hard_driving, overtaken_car

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
        self.assertEqual(self.draw().size, full_picture_size(1280, 720))

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


MAGENTA = (255, 0, 255)


class ObjectBoxesTest(unittest.TestCase):
    """Cones: a thin box for every cone, a thick magenta one for a lying cone."""

    LYING = cone_box(700, 60, 30, 0.4, centre_y=400)      # left edge at x = 670
    STANDING = cone_box(300, 20, 40, 0.6, centre_y=400)   # left edge at x = 290

    def setUp(self):
        objects = objects_of([(0.0, [self.STANDING, self.LYING])])
        self.explanation = explain(detections_of([(0.0, [])]), [], 10.0, objects)

    def draw(self, explanation=None):
        return draw_picture(black_picture(), 0.0, explanation or self.explanation, "built-in values")

    def test_lying_cone_is_drawn_in_magenta(self):
        self.assertEqual(self.draw().getpixel((670, 400)), MAGENTA)

    def test_standing_cone_gets_a_thin_box_in_another_colour(self):
        colour = self.draw().getpixel((290, 400))
        self.assertNotEqual(colour, BLACK)
        self.assertNotEqual(colour, MAGENTA)

    def test_object_boxes_can_be_switched_off(self):
        with setting("SHOW_OBJECT_BOXES", False):
            drawn = self.draw()
        self.assertEqual(drawn.getpixel((670, 400)), BLACK)
        self.assertEqual(drawn.getpixel((290, 400)), BLACK)

    def test_explanation_without_objects_draws_as_before(self):
        without = explain(detections_of([(0.0, [])]), [], 10.0)
        self.assertEqual(self.draw(without).getpixel((670, 400)), BLACK)


class StripTest(unittest.TestCase):
    """The sensor strip sits below the video picture (rows 720 and down)."""

    STRIP = (0, 720, 1280, 720 + 320)

    def setUp(self):
        self.explanation = explain(detections_of([(0.0, [])]), hard_driving(), VIDEO_SECONDS)

    def strip(self, time_seconds=100.0, explanation=None):
        drawn = draw_picture(black_picture(), time_seconds, explanation or self.explanation, "x")
        return drawn.crop(self.STRIP)

    def test_picture_is_taller_by_the_strip(self):
        drawn = draw_picture(black_picture(), 100.0, self.explanation, "x")
        self.assertEqual(drawn.size, (1280, 720 + 320))
        self.assertEqual(drawn.size, full_picture_size(1280, 720))

    def test_strip_is_drawn_below_the_picture(self):
        self.assertGreater(len(self.strip().getcolors(maxcolors=100000)), 5)

    def test_strip_moves_with_the_time(self):
        self.assertNotEqual(self.strip(100.0).tobytes(), self.strip(103.0).tobytes())

    def test_threshold_line_is_at_the_profile_value(self):
        built_in = self.strip()
        with using_profile(Profile("x", None, {"OFFTRACK_MIN_SHAKE": 3.5})):
            # The explanation is made again: the charts take their thresholds
            # from the settings at that moment.
            halved = self.strip(explanation=explain(detections_of([(0.0, [])]), hard_driving(), VIDEO_SECONDS))
        self.assertNotEqual(built_in.tobytes(), halved.tobytes())

    def test_thresholds_can_be_switched_off(self):
        with setting("SHOW_THRESHOLDS", False):
            without = self.strip()
        self.assertNotEqual(without.tobytes(), self.strip().tobytes())

    def test_only_the_named_charts_are_drawn(self):
        with setting("STRIP_CHARTS", ["pace"]):
            one = self.strip()
        self.assertNotEqual(one.tobytes(), self.strip().tobytes())

    def test_no_sensor_data_says_so(self):
        no_sensors = explain(detections_of([(0.0, [])]), [], 10.0)
        strip = self.strip(5.0, no_sensors)
        self.assertNotEqual(strip.getextrema(), ((0, 0), (0, 0), (0, 0)))

    def test_time_past_the_sensor_data_does_not_fail(self):
        self.strip(VIDEO_SECONDS + 50.0)

    def test_strip_can_be_switched_off(self):
        with setting("SHOW_STRIP", False):
            drawn = draw_picture(black_picture(), 100.0, self.explanation, "x")
            self.assertEqual(drawn.size, (1280, 720))
            self.assertEqual(full_picture_size(1280, 720), (1280, 720))


def is_grey(pixel):
    """Grey has equal parts of red, green and blue (and is not black)."""
    red, green, blue = pixel
    return red == green == blue and red > 0


class DroppedBoxesTest(unittest.TestCase):
    COCKPIT = CarBox(200, 400, 900, 650, 0.8)   # 700 of 1280 pixels wide: "too wide"
    COCKPIT_EDGE = (200, 525)
    COCKPIT_MIDDLE = (550, 525)

    def setUp(self):
        self.explanation = explanation_with([[BOX] * 5, [self.COCKPIT] * 5])

    def draw(self):
        return draw_picture(black_picture(), 0.0, self.explanation, "built-in values")

    def test_dropped_box_is_drawn_grey(self):
        drawn = self.draw()
        self.assertTrue(is_grey(drawn.getpixel(self.COCKPIT_EDGE)), drawn.getpixel(self.COCKPIT_EDGE))
        self.assertEqual(drawn.getpixel(self.COCKPIT_MIDDLE), BLACK)
        # The kept box next to it keeps its colour.
        self.assertFalse(is_grey(drawn.getpixel(EDGE)))
        self.assertNotEqual(drawn.getpixel(EDGE), BLACK)

    def test_dropped_boxes_can_be_switched_off(self):
        with setting("SHOW_DROPPED_BOXES", False):
            drawn = self.draw()
        self.assertEqual(drawn.getpixel(self.COCKPIT_EDGE), BLACK)
        self.assertNotEqual(drawn.getpixel(EDGE), BLACK)   # the kept box is still there

    def test_dropped_boxes_show_without_the_kept_ones(self):
        with setting("SHOW_KEPT_BOXES", False):
            drawn = self.draw()
        self.assertTrue(is_grey(drawn.getpixel(self.COCKPIT_EDGE)))
        self.assertEqual(drawn.getpixel(EDGE), BLACK)

    def test_unsure_car_is_drawn_grey(self):
        unsure = explanation_with([[CarBox(100, 300, 300, 450, 0.6)] * 5])
        drawn = draw_picture(black_picture(), 0.0, unsure, "built-in values")
        self.assertTrue(is_grey(drawn.getpixel(EDGE)))


class DroppedEventsTest(unittest.TestCase):
    # Below the event line, where the dropped events are written.
    SECOND_LINE = (0, 46, 1000, 92)

    def setUp(self):
        # A car is overtaken at 01:40, but the whole video is warm up: the
        # overtaking is found and then dropped.
        self.dropped = explain(detections_of(overtaken_car()), gentle_driving(), VIDEO_SECONDS)
        self.kept = explain(detections_of(overtaken_car()), hard_driving(), VIDEO_SECONDS)

    def second_line(self, explanation, time_seconds=101.5):
        return draw_picture(black_picture(), time_seconds, explanation, "x").crop(self.SECOND_LINE)

    def test_dropped_event_line_is_drawn(self):
        self.assertNotEqual(self.second_line(self.dropped).getextrema(), ((0, 0), (0, 0), (0, 0)))

    def test_dropped_event_line_is_grey(self):
        colours = {colour for _, colour in self.second_line(self.dropped).getcolors()}
        self.assertTrue(all(red == green == blue for red, green, blue in colours), colours)

    def test_no_line_when_nothing_is_dropped(self):
        self.assertEqual(self.second_line(self.kept).getextrema(), ((0, 0), (0, 0), (0, 0)))
        # Nor at a moment the dropped event does not cover.
        self.assertEqual(self.second_line(self.dropped, 50.0).getextrema(), ((0, 0), (0, 0), (0, 0)))

    def test_dropped_events_can_be_switched_off(self):
        with setting("SHOW_DROPPED_EVENTS", False):
            self.assertEqual(self.second_line(self.dropped).getextrema(), ((0, 0), (0, 0), (0, 0)))


if __name__ == "__main__":
    unittest.main()
