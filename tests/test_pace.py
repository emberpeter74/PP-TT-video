"""Checks for finding warm up and cooling."""

import unittest

from pp_tt_video import settings
from pp_tt_video.detect_events import combine_stretches
from pp_tt_video.events import Event
from pp_tt_video.pace import (
    detect_pace, find_pace_part, forward_force_per_second, outside_pace, pace_stretches,
)
from pp_tt_video.sensors import SensorSecond, read_sensors
from pp_tt_video.stretch import Stretch
from pp_tt_video.timeline import build_timeline

EXAMPLE_FOLDER = settings.PROJECT_FOLDER / "example video  and output file"
EXAMPLE_VIDEO = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 10-32.MP4"

# Made-up driving, one force value per second (m/s²).
ROLLING = [0.5, 1.0, 0.5, 1.5, 0.5]            # gentle: pit lane or a slow lap
RACING = [4.0, 0.5, 3.5, 3.0, 0.5, 4.5, 1.0]   # hard braking and accelerating


def repeat(pattern, seconds):
    """Repeat a pattern until it is the given number of seconds long."""
    return [pattern[i % len(pattern)] for i in range(seconds)]


class FindPacePartTest(unittest.TestCase):
    def test_warm_up_then_pace_then_cooling(self):
        forces = repeat(ROLLING, 100) + repeat(RACING, 300) + repeat(ROLLING, 120)
        first, last = find_pace_part(forces)
        # The edges are found within a few seconds.
        self.assertAlmostEqual(first, 100, delta=3)
        self.assertAlmostEqual(last, 399, delta=3)

    def test_video_that_starts_and_ends_at_pace(self):
        forces = repeat(RACING, 300)
        self.assertEqual(find_pace_part(forces), (0, 299))

    def test_never_at_pace(self):
        self.assertIsNone(find_pace_part(repeat(ROLLING, 300)))

    def test_short_burst_in_the_pit_lane_is_not_pace(self):
        # Pulling away briskly for 4 seconds, then rolling on.
        forces = repeat(ROLLING, 60) + [3.2, 3.2, 3.2, 3.2] + repeat(ROLLING, 200)
        self.assertIsNone(find_pace_part(forces))

    def test_slow_moment_in_the_middle_stays_inside(self):
        forces = repeat(RACING, 200) + repeat(ROLLING, 60) + repeat(RACING, 200)
        self.assertEqual(find_pace_part(forces), (0, 459))


class PaceStretchesTest(unittest.TestCase):
    def test_warm_up_and_cooling_around_the_pace_part(self):
        stretches = pace_stretches((104, 679), 787)
        self.assertEqual(stretches, [Stretch(0, 103, "warm up"), Stretch(680, 787, "cooling")])

    def test_no_warm_up_when_the_video_starts_at_pace(self):
        self.assertEqual(pace_stretches((0, 455), 625), [Stretch(456, 625, "cooling")])

    def test_nothing_when_at_pace_throughout(self):
        self.assertEqual(pace_stretches((0, 299), 300), [])

    def test_never_at_pace_is_all_warm_up(self):
        self.assertEqual(pace_stretches(None, 300), [Stretch(0, 300, "warm up")])

    def test_timeline_has_the_lines_of_the_events_file(self):
        timeline = build_timeline(pace_stretches((104, 679), 787), 787)
        self.assertEqual(timeline, [
            Event(0, ("warm up",)),
            Event(104, ("clear",)),
            Event(680, ("cooling",)),
        ])


class SensorsToPaceTest(unittest.TestCase):
    def test_force_is_averaged_and_loses_its_sign(self):
        # Two measurements: braking with 4 and with 2 m/s² (down, sideways, forward).
        braking = SensorSecond(0, [(-9.8, 0, 4.0), (-9.8, 0, 2.0)], [(0, 0, 0)])
        accelerating = SensorSecond(1, [(-9.8, 0, -3.0)], [(0, 0, 0)])
        self.assertEqual(forward_force_per_second([braking, accelerating]), [3.0, 3.0])

    def test_no_sensor_data_gives_no_stretches(self):
        self.assertEqual(detect_pace([], 300), [])


class CarEventsOutsidePaceTest(unittest.TestCase):
    PACE_PARTS = [Stretch(0, 103, "warm up"), Stretch(680, 787, "cooling")]

    def test_car_event_in_the_pit_lane_is_dropped(self):
        parked_car = Stretch(20, 23, "overtaking")
        self.assertTrue(outside_pace(parked_car, self.PACE_PARTS))
        self.assertEqual(combine_stretches([parked_car], self.PACE_PARTS), self.PACE_PARTS)

    def test_car_event_at_pace_is_kept(self):
        overtake = Stretch(325, 332, "overtaking")
        self.assertFalse(outside_pace(overtake, self.PACE_PARTS))
        self.assertIn(overtake, combine_stretches([overtake], self.PACE_PARTS))

    def test_without_pace_parts_everything_is_kept(self):
        overtake = Stretch(20, 23, "overtaking")
        self.assertEqual(combine_stretches([overtake], []), [overtake])


@unittest.skipUnless(EXAMPLE_VIDEO.is_file(), "example video not on this PC")
class ExampleTest(unittest.TestCase):
    def test_cooling_is_found_where_the_author_marked_it(self):
        # The hand-made events file: no warm up, cooling from 07:36 (456 s).
        info_duration = 625
        stretches = detect_pace(read_sensors(EXAMPLE_VIDEO), info_duration)
        self.assertEqual([stretch.label for stretch in stretches], ["cooling"])
        self.assertAlmostEqual(stretches[0].start, 456, delta=settings.TIME_TOLERANCE_SECONDS)


if __name__ == "__main__":
    unittest.main()
