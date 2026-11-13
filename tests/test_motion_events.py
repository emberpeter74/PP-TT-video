"""Checks for the events found from the motion sensors: sliding and offtrack."""

import unittest

from pp_tt_video import settings
from pp_tt_video.detect_events import combine_stretches
from pp_tt_video.offtrack import detect_offtrack, offtrack_stretches
from pp_tt_video.sensors import SensorSecond, pieces_of_seconds, read_sensors
from pp_tt_video.sliding import detect_sliding, find_catch_times, slide_stretches
from pp_tt_video.stretch import Stretch

EXAMPLE_FOLDER = settings.PROJECT_FOLDER / "example video  and output file"
EXAMPLE_VIDEO = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 10-32.MP4"


def samples_from(values, start=100.0):
    """Give a list of values their times, 10 per second: (time, a, b) or (time, a)."""
    return [(start + position / 10, *value) for position, value in enumerate(values)]


# (cornering force, turning rate) in a right-hand corner: both negative.
CORNER = (-11.0, -0.6)
CATCH = (-10.0, 0.3)      # still pushed sideways, but turning the other way
STRAIGHT = (0.0, 0.0)


class PiecesTest(unittest.TestCase):
    def test_second_is_cut_into_equal_pieces(self):
        acceleration = [(i, 0, 0) for i in range(10)]
        rotation = [(i, 0, 0) for i in range(10)]
        pieces = pieces_of_seconds([SensorSecond(5.0, acceleration, rotation)], 5)
        self.assertEqual([time for time, _, _ in pieces], [5.0, 5.2, 5.4, 5.6, 5.8])
        self.assertEqual(pieces[0][1], [(0, 0, 0), (1, 0, 0)])
        self.assertEqual(pieces[4][2], [(8, 0, 0), (9, 0, 0)])


class SlidingTest(unittest.TestCase):
    def test_catch_after_hard_cornering_is_a_slide(self):
        samples = samples_from([CORNER] * 20 + [CATCH] * 3 + [CORNER] * 10)
        stretches = slide_stretches(samples)
        self.assertEqual([stretch.label for stretch in stretches], ["sliding"])
        # The catch is at 102.0 s; the slide starts the lead time before it.
        self.assertAlmostEqual(stretches[0].start, 102.0 - settings.SLIDE_LEAD_SECONDS)
        self.assertAlmostEqual(stretches[0].end, 102.2 + settings.SLIDE_TAIL_SECONDS)

    def test_left_hand_corner_works_the_same(self):
        samples = samples_from([(11.0, 0.6)] * 20 + [(10.0, -0.3)] * 3)
        self.assertEqual(len(slide_stretches(samples)), 1)

    def test_normal_corner_is_no_slide(self):
        samples = samples_from([STRAIGHT] * 10 + [CORNER] * 30 + [STRAIGHT] * 10)
        self.assertEqual(slide_stretches(samples), [])

    def test_quick_change_of_direction_is_no_slide(self):
        # Right, then left: force and turning change sign together.
        samples = samples_from([CORNER] * 15 + [(-2.0, 0.1)] + [(9.0, 0.5)] * 15)
        self.assertEqual(slide_stretches(samples), [])

    def test_turning_the_other_way_at_low_force_is_no_slide(self):
        samples = samples_from([CORNER] * 20 + [(-3.0, 0.3)] * 3)
        self.assertEqual(slide_stretches(samples), [])

    def test_single_odd_sample_is_no_slide(self):
        samples = samples_from([CORNER] * 20 + [CATCH] + [CORNER] * 10)
        self.assertEqual(find_catch_times(samples), [102.0])
        self.assertEqual(slide_stretches(samples), [])

    def test_without_hard_turning_before_it_is_no_slide(self):
        # Pushed sideways, but the car was hardly turning before.
        samples = samples_from([(-8.0, -0.1)] * 20 + [(-8.0, 0.1)] * 3)
        self.assertEqual(slide_stretches(samples), [])


class OfftrackTest(unittest.TestCase):
    def shakes(self, values):
        return [(100.0 + position / 5, value) for position, value in enumerate(values)]

    def test_long_hard_shaking_is_offtrack(self):
        # 2 seconds of hard shaking, starting at 102.0 s.
        stretches = offtrack_stretches(self.shakes([2.5] * 10 + [11.0] * 10 + [2.5] * 10))
        self.assertEqual([stretch.label for stretch in stretches], ["offtrack"])
        self.assertAlmostEqual(stretches[0].start, 102.0 - settings.OFFTRACK_LEAD_SECONDS)
        self.assertAlmostEqual(stretches[0].end, 104.0 + settings.OFFTRACK_TAIL_SECONDS)

    def test_kerb_is_not_offtrack(self):
        # A kerb: strong but short, and not as strong as grass.
        self.assertEqual(offtrack_stretches(self.shakes([2.5] * 10 + [6.0] * 4 + [2.5] * 10)), [])

    def test_short_hard_bump_is_not_offtrack(self):
        self.assertEqual(offtrack_stretches(self.shakes([2.5] * 10 + [12.0] * 2 + [2.5] * 10)), [])

    def test_shake_is_measured_from_the_up_and_down_force(self):
        # One second: calm in the first half, jumping up and down in the second.
        calm = [(-9.8, 0, 0)] * 100
        rough = [(-9.8 + 12, 0, 0), (-9.8 - 12, 0, 0)] * 50
        seconds = [SensorSecond(float(n), rough, [(0, 0, 0)] * 200) for n in range(3)]
        seconds.insert(0, SensorSecond(-1.0, calm, [(0, 0, 0)] * 100))
        self.assertEqual([stretch.label for stretch in detect_offtrack(seconds)], ["offtrack"])


class OutsidePaceTest(unittest.TestCase):
    def test_shaking_in_the_paddock_is_dropped(self):
        pace_parts = [Stretch(0, 103, "warm up"), Stretch(680, 787, "cooling")]
        paddock = Stretch(21, 24, "offtrack")
        on_track = Stretch(675, 679, "offtrack")
        combined = combine_stretches([paddock, on_track], pace_parts)
        self.assertNotIn(paddock, combined)
        self.assertIn(on_track, combined)


@unittest.skipUnless(EXAMPLE_VIDEO.is_file(), "example video not on this PC")
class ExampleTest(unittest.TestCase):
    def test_all_four_marked_slides_are_found_and_nothing_else(self):
        # The hand-made events file: sliding at 01:42, 04:54, 05:28 and 06:42.
        marked = [102, 294, 328, 402]
        stretches = detect_sliding(read_sensors(EXAMPLE_VIDEO))
        self.assertEqual(len(stretches), len(marked))
        for stretch, start in zip(stretches, marked):
            self.assertAlmostEqual(stretch.start, start, delta=settings.TIME_TOLERANCE_SECONDS)


if __name__ == "__main__":
    unittest.main()
