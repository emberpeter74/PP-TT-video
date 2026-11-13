"""Checks for dividing a video into out of session, warm up, cooling and crash."""

import unittest

from pp_tt_video import settings
from pp_tt_video.events import Event
from pp_tt_video.sensors import SensorSecond, read_sensors
from pp_tt_video.session import (
    detect_session, find_session_parts, seconds_before_joining, speed_at_start,
    start_of_final_standstill,
)
from pp_tt_video.timeline import build_timeline

EXAMPLE_FOLDER = settings.PROJECT_FOLDER / "example video  and output file"
EXAMPLE_10_32 = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 10-32.MP4"
EXAMPLE_12_17 = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 12-17.MP4"


def second(forward=0.0, sideways=0.0, turning=0.0, shake=2.5, gps=None):
    """Make one second of sensor data.

    forward:  minus is accelerating, plus is braking (m/s²).
    shake:    how much the up-and-down force jumps around.
    gps:      the GPS speed in km/h, or None when there is no fix.
    """
    acceleration = [(-9.8 + shake, sideways, forward), (-9.8 - shake, sideways, forward)]
    return SensorSecond(0.0, acceleration, [(turning, 0.0, 0.0)], [gps] if gps is not None else [])


def video(*pieces):
    """Join pieces (lists of seconds) into one video and number the seconds."""
    seconds = [item for piece in pieces for item in piece]
    for position, item in enumerate(seconds):
        item.start_seconds = float(position)
    return seconds


# --- Pieces of made-up driving ---------------------------------------------------

def pit_lane():
    """18 seconds: rolling, a slow tight turn, then accelerating onto the track."""
    return (
        [second() for _ in range(10)]
        + [second(sideways=-3.0, turning=-0.45) for _ in range(2)]   # about 24 km/h
        + [second(forward=-3.0) for _ in range(5)]
        + [second(forward=-0.5)]
    )


def slow_lap(length):
    """Gentle driving with brisk corners: a warm-up or cool-down lap."""
    seconds = []
    for position in range(length):
        forward = [0.5, -1.0, 0.5, -1.5, 0.5][position % 5]
        in_corner = position % 5 in (0, 3)
        seconds.append(second(forward, -8.0 if in_corner else 0.0, -0.4 if in_corner else 0.0))
    return seconds


def fast_laps(length):
    """Hard braking and accelerating."""
    forces = [4.0, 0.5, -3.5, -3.0, 0.5, 4.5, -1.0]
    return [second(forces[position % 7], -9.0, -0.5) for position in range(length)]


def into_the_pits():
    """30 seconds: a straight way in without real corners, then parked."""
    return [second(0.5) for _ in range(20)] + [second(shake=0.2) for _ in range(10)]


class StartTest(unittest.TestCase):
    def test_speed_from_gps_when_there_is_a_fix(self):
        self.assertEqual(speed_at_start([second(gps=35.0)]), 35.0)

    def test_speed_from_a_turn_without_gps(self):
        # 3.0 m/s² at 0.45 rad/s is 6.7 m/s, which is 24 km/h.
        seconds = [second(), second(sideways=-3.0, turning=-0.45)]
        self.assertAlmostEqual(speed_at_start(seconds), 24.0, delta=0.1)

    def test_speed_unknown_on_a_straight_without_gps(self):
        self.assertIsNone(speed_at_start([second() for _ in range(30)]))

    def test_slow_start_lasts_until_the_car_has_accelerated_onto_the_track(self):
        self.assertEqual(seconds_before_joining(video(pit_lane(), fast_laps(100))), 17)

    def test_fast_start_is_already_on_the_track(self):
        seconds = video([second(forward=-3.0, gps=80.0) for _ in range(5)], fast_laps(100))
        self.assertEqual(seconds_before_joining(seconds), 0)

    def test_unknown_speed_is_taken_as_on_the_track(self):
        seconds = video([second(forward=-3.0) for _ in range(5)], [second() for _ in range(50)])
        self.assertEqual(seconds_before_joining(seconds), 0)


class StandstillTest(unittest.TestCase):
    def test_parked_at_the_end(self):
        self.assertEqual(start_of_final_standstill(video(fast_laps(50), into_the_pits())), 70)

    def test_video_ends_while_driving(self):
        self.assertIsNone(start_of_final_standstill(video(fast_laps(50))))

    def test_one_calm_second_is_not_a_standstill(self):
        self.assertIsNone(start_of_final_standstill(video(fast_laps(50), [second(shake=0.2)])))


class SessionPartsTest(unittest.TestCase):
    def test_whole_session(self):
        seconds = video(pit_lane(), slow_lap(80), fast_laps(300), slow_lap(100), into_the_pits())
        parts = find_session_parts(seconds)
        self.assertEqual([label for _, _, label in parts],
                         ["out of session", "warm up", "cooling", "out of session"])
        (_, joined, _), (_, warm_up_end, _), (cooling_start, cooling_end, _), (left, end, _) = parts
        self.assertEqual(joined, 16)                         # the pit lane is 17 seconds
        self.assertAlmostEqual(warm_up_end, 97, delta=3)     # the fast laps start at 98
        self.assertAlmostEqual(cooling_start, 398, delta=3)  # the fast laps end at 397
        # The last corner is at second 496; "out of session" starts 10 s after it.
        self.assertAlmostEqual(left, 497 + settings.SESSION_LEAVE_SECONDS, delta=2)
        self.assertEqual(cooling_end, left - 1)
        self.assertEqual(end, len(seconds) - 1)

    def test_video_starts_and_ends_on_the_track(self):
        self.assertEqual(find_session_parts(video(fast_laps(300))), [])

    def test_straight_from_the_pit_lane_to_pace(self):
        parts = find_session_parts(video(pit_lane(), fast_laps(300)))
        self.assertEqual(parts, [(0, 16, "out of session")])

    def test_video_ends_before_the_car_leaves_the_track(self):
        parts = find_session_parts(video(fast_laps(300), slow_lap(100)))
        self.assertEqual([label for _, _, label in parts], ["cooling"])
        self.assertEqual(parts[0][1], 399)

    def test_standing_still_soon_after_pace_is_a_crash(self):
        # 20 seconds of rolling to a stop, no cool-down lap.
        parts = find_session_parts(video(fast_laps(300), into_the_pits()))
        self.assertEqual([label for _, _, label in parts], ["crash"])
        self.assertAlmostEqual(parts[0][0], 300, delta=3)
        self.assertEqual(parts[0][1], 329)

    def test_never_at_pace_is_warm_up(self):
        parts = find_session_parts(video(slow_lap(200)))
        self.assertEqual(parts, [(0, 199, "warm up")])


class StretchesTest(unittest.TestCase):
    def test_timeline_has_no_gaps_between_the_parts(self):
        seconds = video(pit_lane(), slow_lap(80), fast_laps(300), slow_lap(100), into_the_pits())
        timeline = build_timeline(detect_session(seconds, len(seconds)), len(seconds))
        self.assertEqual([event.labels[0] for event in timeline],
                         ["out of session", "warm up", "clear", "cooling", "out of session"])
        self.assertEqual(timeline[0], Event(0, ("out of session",)))
        self.assertEqual(timeline[1], Event(17, ("warm up",)))

    def test_no_sensor_data_gives_no_stretches(self):
        self.assertEqual(detect_session([], 300), [])


class ExampleTest(unittest.TestCase):
    """The times are those the author marked in the hand-made events files."""

    def found_in(self, video_path, duration):
        stretches = detect_session(read_sensors(video_path), duration)
        return [(stretch.label, stretch.start) for stretch in stretches]

    @unittest.skipUnless(EXAMPLE_10_32.is_file(), "example video not on this PC")
    def test_session_with_cooling_and_return_to_the_pits(self):
        found = self.found_in(EXAMPLE_10_32, 625)
        self.assertEqual([label for label, _ in found], ["out of session", "cooling", "out of session"])
        tolerance = settings.TIME_TOLERANCE_SECONDS
        self.assertAlmostEqual(found[1][1], 456, delta=tolerance)   # cooling from 07:36
        self.assertAlmostEqual(found[2][1], 524, delta=tolerance)   # out of session from 08:44

    @unittest.skipUnless(EXAMPLE_12_17.is_file(), "example video not on this PC")
    def test_breakdown_is_a_crash_until_the_end(self):
        found = self.found_in(EXAMPLE_12_17, 387)
        self.assertEqual([label for label, _ in found], ["out of session", "crash"])
        self.assertAlmostEqual(found[1][1], 300, delta=settings.TIME_TOLERANCE_SECONDS)   # crash from 05:00


if __name__ == "__main__":
    unittest.main()
