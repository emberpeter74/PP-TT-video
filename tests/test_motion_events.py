"""Checks for the events found from the motion sensors: sliding and offtrack."""

import unittest
from unittest import mock

from pp_tt_video import settings
from pp_tt_video.detect_events import combine_stretches
from pp_tt_video.offtrack import detect_offtrack, offtrack_stretches, shake_over_time, smoothed
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


# Up-and-down values, repeated to fill a second of 200 measurements.
FAST = [12, -12]              # changes with every measurement: the camera's vibration
SLOW = [6] * 10 + [-6] * 10   # ten measurements up, ten down: rough ground


class SmoothedTest(unittest.TestCase):
    def test_smoothed_averages_neighbours(self):
        self.assertEqual(smoothed([1, 2, 3, 4, 5], 2), [1.5, 2.5, 3.5, 4.5])

    def test_smoothing_of_one_changes_nothing(self):
        for count in (1, 0, -3):
            self.assertEqual(smoothed([1, 2, 3], count), [1, 2, 3])

    def test_too_few_values_are_left_alone(self):
        self.assertEqual(smoothed([1, 2], 4), [1, 2])


class OfftrackTest(unittest.TestCase):
    def shakes(self, values, start=100.0):
        return [(start + position / 5, value) for position, value in enumerate(values)]

    def seconds_of(self, pattern, count=3, measurements=200):
        """Seconds in which the up-and-down force follows the pattern, over and over."""
        down = [pattern[i % len(pattern)] for i in range(measurements)]
        return [SensorSecond(float(n), [(-9.8 + d, 0, 0) for d in down], [(0, 0, 0)] * measurements)
                for n in range(count)]

    def test_long_hard_shaking_is_offtrack(self):
        # 2 seconds of hard shaking, starting at 102.0 s.
        stretches = offtrack_stretches(self.shakes([1.0] * 10 + [5.0] * 10 + [1.0] * 10))
        self.assertEqual([stretch.label for stretch in stretches], ["offtrack"])
        self.assertAlmostEqual(stretches[0].start, 102.0 - settings.OFFTRACK_LEAD_SECONDS)
        self.assertAlmostEqual(stretches[0].end, 104.0 + settings.OFFTRACK_TAIL_SECONDS)

    def test_kerb_is_not_offtrack(self):
        # A kerb: short, and not as rough as grass.
        self.assertEqual(offtrack_stretches(self.shakes([1.0] * 10 + [1.8] * 4 + [1.0] * 10)), [])

    def test_short_hard_bump_is_not_offtrack(self):
        self.assertEqual(offtrack_stretches(self.shakes([1.0] * 10 + [6.0] * 2 + [1.0] * 10)), [])

    def test_shaking_just_under_the_time_is_not_offtrack(self):
        # Five pieces are 1.0 second, six are 1.2 seconds.
        self.assertEqual(offtrack_stretches(self.shakes([1.0] * 10 + [4.0] * 5 + [1.0] * 10)), [])
        self.assertEqual(len(offtrack_stretches(self.shakes([1.0] * 10 + [4.0] * 6 + [1.0] * 10))), 1)

    def test_six_pieces_are_enough_wherever_they_start(self):
        # Times like 100.6 cannot be stored exactly; the answer must not depend on that.
        for start in (100.0, 100.2, 100.4, 100.6, 100.8):
            with self.subTest(start=start):
                six = self.shakes([1.0] * 3 + [4.0] * 6 + [1.0] * 3, start)
                five = self.shakes([1.0] * 3 + [4.0] * 5 + [1.0] * 3, start)
                self.assertEqual(len(offtrack_stretches(six)), 1)
                self.assertEqual(offtrack_stretches(five), [])

    def test_shaking_until_the_end_of_the_video_is_reported(self):
        self.assertEqual(len(offtrack_stretches(self.shakes([1.0] * 10 + [4.0] * 10))), 1)

    def test_fast_vibration_is_not_offtrack(self):
        seconds = self.seconds_of(FAST)
        self.assertEqual(detect_offtrack(seconds), [])
        for _, shake in shake_over_time(seconds):
            self.assertLess(shake, 0.1)

    def test_fast_vibration_shows_without_smoothing(self):
        for _, shake in shake_over_time(self.seconds_of(FAST), smoothing=1):
            self.assertAlmostEqual(shake, 12.0)

    def test_slow_rough_shaking_is_offtrack(self):
        stretches = detect_offtrack(self.seconds_of(SLOW))
        self.assertEqual([stretch.label for stretch in stretches], ["offtrack"])

    def test_smoothing_setting_is_read_when_the_rule_runs(self):
        with mock.patch.object(settings, "OFFTRACK_SMOOTHING_MEASUREMENTS", 1):
            self.assertEqual(len(detect_offtrack(self.seconds_of(FAST))), 1)

    def test_smoothing_of_zero_or_less_means_no_smoothing(self):
        for count in (0, -2):
            with mock.patch.object(settings, "OFFTRACK_SMOOTHING_MEASUREMENTS", count):
                for _, shake in shake_over_time(self.seconds_of(FAST)):
                    self.assertAlmostEqual(shake, 12.0)

    def test_piece_with_few_measurements_counts_as_calm(self):
        # A camera that measures 10 times per second: 2 measurements per
        # piece, too few to smooth. Unsmoothed, this would be a false alarm.
        seconds = self.seconds_of(FAST, measurements=10)
        self.assertEqual({shake for _, shake in shake_over_time(seconds)}, {0.0})
        self.assertEqual(detect_offtrack(seconds), [])


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


@unittest.skipUnless(EXAMPLE_VIDEO.is_file(), "example videos not on this PC")
class OfftrackOnExamplesTest(unittest.TestCase):
    def starts(self, name):
        return [stretch.start for stretch in detect_offtrack(read_sensors(EXAMPLE_FOLDER / name))]

    def test_09_41_has_its_two_offtracks(self):
        first, second = self.starts("RaceBox Track Sessionon 30-05-2026 09-41.MP4")
        self.assertAlmostEqual(first, 151, delta=2)    # 02:31 in the hand-made file
        self.assertAlmostEqual(second, 675, delta=2)   # 11:15

    def test_the_other_examples_have_none(self):
        for name in ("RaceBox Track Sessionon 30-05-2026 10-32.MP4", "RaceBox Track Sessionon 30-05-2026 12-17.MP4"):
            self.assertEqual(self.starts(name), [])


if __name__ == "__main__":
    unittest.main()
