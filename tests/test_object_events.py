"""Checks for the rules on the objects found in a video: knocked-over cones."""

import unittest
from unittest import mock

from pp_tt_video import object_events, settings
from pp_tt_video.object_events import events_of_objects, is_lying_cone, lying_cones
from pp_tt_video.stretch import Stretch
from tests.helpers import cone_box, objects_of

WIDTH = 1280   # the pictures are 1280 pixels wide


def lying(box):
    """Whether the box counts as a lying cone when it is alone in its picture."""
    return is_lying_cone(box, [box], WIDTH)


def lying_at(*times):
    """Objects with one knocked-over cone at each of the given times, and empty pictures between."""
    pictures = []
    for number in range(int(max(times) * 5) + 6):
        time = round(number * 0.2, 3)
        pictures.append((time, [cone_box(600, 30, 15, 0.4)] if time in times else []))
    return objects_of(pictures)


class IsLyingConeTest(unittest.TestCase):
    def test_wide_cone_is_lying(self):
        self.assertTrue(lying(cone_box(600, 30, 15, 0.4)))

    def test_upright_cone_is_not(self):
        self.assertFalse(lying(cone_box(600, 15, 30, 0.4)))

    def test_barely_wider_is_not(self):
        # 1.4 times as wide as tall: a standing cone seen at a slant can look like this.
        self.assertFalse(lying(cone_box(600, 28, 20, 0.4)))

    def test_unsure_cone_is_not(self):
        self.assertFalse(lying(cone_box(600, 30, 15, 0.29)))

    def test_tiny_cone_is_not(self):
        self.assertFalse(lying(cone_box(600, 9, 5, 0.4)))

    def test_wide_box_around_other_cones_is_not(self):
        # A far row of standing cones that the model also boxed as one wide object.
        row = cone_box(600, 60, 20, 0.4)
        single = cone_box(590, 12, 20, 0.3)
        self.assertFalse(is_lying_cone(row, [row, single], WIDTH))

    def test_double_box_of_the_same_cone_does_not_hide_it(self):
        # The model often gives two boxes for one cone, at almost the same place.
        cone = cone_box(600, 30, 15, 0.4)
        double = cone_box(601, 28, 14, 0.3)
        self.assertTrue(is_lying_cone(cone, [cone, double], WIDTH))

    def test_box_without_height_is_not(self):
        self.assertFalse(lying(cone_box(600, 30, 0, 0.4)))

    def test_other_kinds_are_ignored(self):
        self.assertFalse(lying(cone_box(600, 30, 15, 0.4, kind="person")))

    def test_values_come_from_the_settings(self):
        with mock.patch.object(settings, "OBSTACLE_MIN_WIDTH_RATIO", 1.3):
            self.assertTrue(lying(cone_box(600, 28, 20, 0.4)))


class LyingConesTest(unittest.TestCase):
    def test_one_sighting_gives_one_stretch(self):
        self.assertEqual(lying_cones(lying_at(10.0)), [Stretch(10.0, 12.0, "obstacle")])

    def test_sightings_close_together_are_one_event(self):
        self.assertEqual(lying_cones(lying_at(10.0, 10.4, 12.4)), [Stretch(10.0, 14.4, "obstacle")])

    def test_sightings_far_apart_are_two_events(self):
        # The same cone, seen again a lap later: reported on every lap.
        self.assertEqual(lying_cones(lying_at(10.0, 46.0)),
                         [Stretch(10.0, 12.0, "obstacle"), Stretch(46.0, 48.0, "obstacle")])

    def test_upright_cones_give_nothing(self):
        pictures = [(round(number * 0.2, 3), [cone_box(600, 15, 30, 0.6)]) for number in range(50)]
        self.assertEqual(lying_cones(objects_of(pictures)), [])

    def test_no_pictures_gives_nothing(self):
        self.assertEqual(lying_cones(objects_of([])), [])


class EventsOfObjectsTest(unittest.TestCase):
    def test_none_gives_nothing(self):
        self.assertEqual(events_of_objects(None), [])

    def test_lying_cone_gives_an_obstacle(self):
        self.assertEqual(events_of_objects(lying_at(10.0)), [Stretch(10.0, 12.0, "obstacle")])

    def test_every_rule_in_the_list_is_asked(self):
        def first(objects):
            return [Stretch(1.0, 2.0, "obstacle")]

        def second(objects):
            return [Stretch(5.0, 6.0, "other event")]

        with mock.patch.object(object_events, "OBJECT_RULES", [first, second]):
            self.assertEqual(events_of_objects(objects_of([])),
                             [Stretch(1.0, 2.0, "obstacle"), Stretch(5.0, 6.0, "other event")])


if __name__ == "__main__":
    unittest.main()
