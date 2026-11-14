"""Checks for measuring a driver and making a profile from the measurement."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pp_tt_video import settings
from pp_tt_video.make_profile import (
    driver_levels,
    percentile,
    profile_text,
    scaled_values,
)
from pp_tt_video.profile import load_profile
from pp_tt_video.sensors import SensorSecond


def driving(seconds_of_force):
    """Made-up sensor data: one SensorSecond per (forward force, sideways force).

    Every second holds ten identical measurements. The axes follow
    settings.py: 0 is down (gravity), 1 is sideways, 2 is forward.
    """
    return [
        SensorSecond(float(number), [(-9.8, sideways, forward)] * 10, [(0.0, 0.0, 0.0)] * 10)
        for number, (forward, sideways) in enumerate(seconds_of_force)
    ]


def references(effort, cornering):
    """Pretend the user's own levels are these, for the length of a check."""
    return mock.patch.multiple(settings, REFERENCE_EFFORT=effort, REFERENCE_CORNERING=cornering)


class PercentileTest(unittest.TestCase):
    def test_percentile(self):
        self.assertEqual(percentile(list(range(101)), 95), 95)
        self.assertEqual(percentile([3.0], 95), 3.0)

    def test_order_does_not_matter(self):
        self.assertEqual(percentile([5.0, 1.0, 3.0], 50), 3.0)

    def test_empty_list_is_refused(self):
        with self.assertRaises(ValueError):
            percentile([], 95)


class DriverLevelsTest(unittest.TestCase):
    def test_levels_of_steady_driving(self):
        video = driving([(2.0, -8.0)] * 300)
        self.assertEqual(driver_levels([video]), (2.0, 8.0))

    def test_slow_parts_do_not_pull_the_level_down(self):
        # 200 seconds rolling gently, then 100 seconds braking hard.
        video = driving([(0.3, 0.0)] * 200 + [(2.0, 0.0)] * 100)
        braking, _ = driver_levels([video])
        self.assertEqual(braking, 2.0)

    def test_videos_are_pooled(self):
        # Two videos: the hard one is a third of all seconds, well over 5%.
        gentle = driving([(0.3, 1.0)] * 200)
        hard = driving([(2.0, 9.0)] * 100)
        self.assertEqual(driver_levels([gentle, hard]), (2.0, 9.0))


class ScaledValuesTest(unittest.TestCase):
    # The built-in values are PACE_MIN_EFFORT 1.3, PACE_HARD_FORCE 3.0,
    # SLIDE_MIN_CORNERING_FORCE 7.0 and SESSION_TRACK_CORNER_FORCE 5.0.

    def test_driver_at_reference_keeps_built_in_values(self):
        with references(2.0, 10.0):
            values = scaled_values(2.0, 10.0)
        self.assertEqual(values, {
            "PACE_MIN_EFFORT": 1.3,
            "PACE_HARD_FORCE": 3.0,
            "SLIDE_MIN_CORNERING_FORCE": 7.0,
            "SESSION_TRACK_CORNER_FORCE": 5.0,
        })

    def test_gentle_driver_gets_lower_values(self):
        with references(2.0, 10.0):
            values = scaled_values(1.0, 5.0)
        self.assertEqual(values, {
            "PACE_MIN_EFFORT": 0.65,
            "PACE_HARD_FORCE": 1.5,
            "SLIDE_MIN_CORNERING_FORCE": 3.5,
            "SESSION_TRACK_CORNER_FORCE": 2.5,
        })

    def test_braking_and_cornering_scale_separately(self):
        # Braking at a third of the user's, cornering as hard as the user.
        with references(3.0, 10.0):
            values = scaled_values(1.0, 10.0)
        self.assertEqual(values["PACE_MIN_EFFORT"], 0.43)    # 1.3 / 3, rounded
        self.assertEqual(values["PACE_HARD_FORCE"], 1.0)
        self.assertEqual(values["SLIDE_MIN_CORNERING_FORCE"], 7.0)


class ProfileTextTest(unittest.TestCase):
    def test_written_text_loads_back(self):
        with references(2.0, 10.0):
            text = profile_text(["a.MP4"], 1.0, 5.0)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profile.toml"
            path.write_text(text, encoding="utf-8")
            profile = load_profile(path)
        self.assertEqual(profile.values, {
            "PACE_MIN_EFFORT": 0.65,
            "PACE_HARD_FORCE": 1.5,
            "SLIDE_MIN_CORNERING_FORCE": 3.5,
            "SESSION_TRACK_CORNER_FORCE": 2.5,
        })
        self.assertIn("a.MP4", text)
        # The car and camera values are there to be switched on by hand.
        self.assertIn("# OFFTRACK_MIN_SHAKE = 7.0", text)


if __name__ == "__main__":
    unittest.main()
