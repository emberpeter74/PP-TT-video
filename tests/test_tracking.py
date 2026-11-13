"""Checks for following cars from picture to picture."""

import unittest

from pp_tt_video.detect_cars import CarBox, keep_car_boxes
from pp_tt_video.tracking import Tracker, drop_double_boxes, overlap


def box(left, top, width, height, confidence=0.99):
    """A short way to make a CarBox from its corner and size."""
    return CarBox(left, top, left + width, top + height, confidence)


class OverlapTest(unittest.TestCase):
    def test_same_box_overlaps_fully(self):
        self.assertEqual(overlap(box(0, 0, 10, 10), box(0, 0, 10, 10)), 1.0)

    def test_boxes_apart_do_not_overlap(self):
        self.assertEqual(overlap(box(0, 0, 10, 10), box(50, 50, 10, 10)), 0.0)

    def test_half_shifted_box(self):
        # Shared area 50, covered together 150.
        self.assertAlmostEqual(overlap(box(0, 0, 10, 10), box(5, 0, 10, 10)), 1 / 3)


class BoxFilterTest(unittest.TestCase):
    def test_cockpit_sized_box_is_dropped(self):
        boxes = [box(0, 100, 1200, 500), box(400, 300, 100, 60)]
        self.assertEqual(keep_car_boxes(boxes, 1280), [boxes[1]])

    def test_box_inside_a_surer_box_is_dropped(self):
        whole_car = box(1000, 300, 280, 150, 0.99)
        part_of_it = box(1000, 340, 60, 80, 0.58)
        self.assertEqual(drop_double_boxes([part_of_it, whole_car]), [whole_car])

    def test_two_cars_side_by_side_are_both_kept(self):
        boxes = [box(100, 300, 100, 60), box(300, 300, 100, 60)]
        self.assertEqual(len(drop_double_boxes(boxes)), 2)


class TrackerTest(unittest.TestCase):
    def test_one_car_gives_one_track(self):
        tracker = Tracker()
        for step in range(10):
            # The car moves right and grows a little in every picture.
            tracker.add_picture(step * 0.2, [box(100 + step * 10, 300, 50 + step * 5, 30 + step * 3)])
        tracks = tracker.finish()
        self.assertEqual(len(tracks), 1)
        self.assertEqual(len(tracks[0].sightings), 10)
        self.assertAlmostEqual(tracks[0].start, 0.0)
        self.assertAlmostEqual(tracks[0].end, 1.8)

    def test_two_cars_give_two_tracks(self):
        tracker = Tracker()
        for step in range(5):
            tracker.add_picture(step * 0.2, [box(100, 300, 60, 40), box(800, 320, 80, 50)])
        tracks = tracker.finish()
        self.assertEqual(len(tracks), 2)
        self.assertEqual([len(track.sightings) for track in tracks], [5, 5])

    def test_car_missing_in_one_picture_stays_the_same_track(self):
        tracker = Tracker()
        tracker.add_picture(0.0, [box(100, 300, 60, 40)])
        tracker.add_picture(0.2, [])
        tracker.add_picture(0.4, [box(105, 300, 60, 40)])
        self.assertEqual(len(tracker.finish()), 1)

    def test_car_seen_again_much_later_is_a_new_track(self):
        tracker = Tracker()
        tracker.add_picture(0.0, [box(100, 300, 60, 40)])
        tracker.add_picture(5.0, [box(100, 300, 60, 40)])
        self.assertEqual(len(tracker.finish()), 2)

    def test_sudden_size_change_is_a_different_car(self):
        tracker = Tracker()
        tracker.add_picture(0.0, [box(100, 300, 50, 30)])
        tracker.add_picture(0.2, [box(90, 250, 300, 160)])   # five times taller
        self.assertEqual(len(tracker.finish()), 2)

    def test_box_far_away_is_a_different_car(self):
        tracker = Tracker()
        tracker.add_picture(0.0, [box(100, 300, 60, 40)])
        tracker.add_picture(0.2, [box(900, 300, 60, 40)])
        self.assertEqual(len(tracker.finish()), 2)


if __name__ == "__main__":
    unittest.main()
