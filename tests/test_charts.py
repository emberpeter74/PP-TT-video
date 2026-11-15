"""Checks for the charts of the sensor strip.

A chart must show what its rule looks at, with the rule's own threshold.
"""

import unittest

from pp_tt_video import settings
from pp_tt_video.charts import (
    CHARTS,
    Line,
    offtrack_chart,
    pace_chart,
    sliding_chart,
    turning_chart,
    window,
)
from pp_tt_video.offtrack import shake_over_time
from pp_tt_video.profile import Profile, using_profile
from pp_tt_video.sensors import SensorSecond
from tests.helpers import RACING, driving, repeat


def racing(seconds=120):
    return driving([(force, 0.0) for force in repeat(RACING, seconds)])


def second_of(start, sideways, turning, down=(-9.8,) * 10):
    """One second of ten measurements with the given cornering force and turning rate."""
    acceleration = [(value, sideways, 0.0) for value in down]
    rotation = [(turning, 0.0, 0.0)] * 10   # axis 0 is the turning rate
    return SensorSecond(float(start), acceleration, rotation)


def caught_slide():
    """A hard corner in which the car turns in, and then turns against the corner."""
    return [
        second_of(0, 0.0, 0.0),
        second_of(1, 8.0, 0.5),    # cornering hard, turning into the corner
        second_of(2, 8.0, -0.3),   # still pushed sideways, now turning the other way: the catch
        second_of(3, 0.0, 0.0),
    ]


def line_named(chart, name):
    (line,) = [line for line in chart.lines if line.name == name]
    return line


class PaceChartTest(unittest.TestCase):
    def test_lines_are_the_force_and_the_effort_of_every_second(self):
        chart = pace_chart(racing())
        force = line_named(chart, "force")
        self.assertEqual(force.times[:3], [0.0, 1.0, 2.0])
        self.assertEqual(force.values[:3], [4.0, 0.5, 3.5])
        self.assertEqual(len(line_named(chart, "effort").values), 120)
        self.assertTrue(force.from_rule)

    def test_thresholds_follow_the_profile(self):
        self.assertEqual(dict(pace_chart(racing()).thresholds),
                         {"pace": settings.PACE_MIN_EFFORT, "hard": settings.PACE_HARD_FORCE})
        with using_profile(Profile("x", None, {"PACE_MIN_EFFORT": 0.5, "PACE_HARD_FORCE": 1.2})):
            self.assertEqual(dict(pace_chart(racing()).thresholds), {"pace": 0.5, "hard": 1.2})


class SlidingChartsTest(unittest.TestCase):
    def test_cornering_force_and_its_thresholds(self):
        chart = sliding_chart(caught_slide())
        force = line_named(chart, "cornering force")
        self.assertEqual(len(force.values), 4 * settings.SLIDE_SAMPLES_PER_SECOND)
        self.assertEqual(force.values[15], 8.0)   # in the middle of second 1
        self.assertEqual(dict(chart.thresholds),
                         {"min": settings.SLIDE_MIN_CORNERING_FORCE, "-min": -settings.SLIDE_MIN_CORNERING_FORCE})

    def test_turning_has_its_own_chart(self):
        chart = turning_chart(caught_slide())
        self.assertEqual(line_named(chart, "turning").values[15], 0.5)
        self.assertEqual(dict(chart.thresholds),
                         {"min": settings.SLIDE_MIN_TURNING_BEFORE, "-min": -settings.SLIDE_MIN_TURNING_BEFORE})

    def test_marks_are_the_catch_moments(self):
        # The car turns against the corner during the whole of second 2.
        for chart in (sliding_chart(caught_slide()), turning_chart(caught_slide())):
            self.assertEqual(len(chart.marks), settings.SLIDE_SAMPLES_PER_SECOND)
            self.assertAlmostEqual(chart.marks[0], 2.0)
            self.assertLess(chart.marks[-1], 3.0)

    def test_no_marks_without_a_catch(self):
        self.assertEqual(sliding_chart(racing()).marks, [])


class OfftrackChartTest(unittest.TestCase):
    def setUp(self):
        # Second 1 shakes up and down only: the axis of gravity jumps
        # between -4.8 and -14.8, the other two axes are still.
        self.data = [second_of(0, 0.0, 0.0), second_of(1, 0.0, 0.0, down=(-4.8, -14.8) * 5), second_of(2, 0.0, 0.0)]
        self.chart = offtrack_chart(self.data)

    def test_one_rule_line_and_two_information_lines(self):
        self.assertEqual([(line.name, line.from_rule) for line in self.chart.lines],
                         [("shake", True), ("shake sideways", False), ("shake forward", False)])

    def test_rule_line_is_what_the_rule_measures(self):
        shake = line_named(self.chart, "shake")
        self.assertEqual(list(zip(shake.times, shake.values)), shake_over_time(self.data))
        self.assertEqual(max(shake.values), 5.0)   # jumping 5 either side of its average

    def test_information_lines_show_the_other_directions(self):
        self.assertEqual(max(line_named(self.chart, "shake sideways").values), 0.0)
        self.assertEqual(max(line_named(self.chart, "shake forward").values), 0.0)

    def test_threshold_follows_the_profile(self):
        self.assertEqual(self.chart.thresholds, [("min", settings.OFFTRACK_MIN_SHAKE)])
        with using_profile(Profile("x", None, {"OFFTRACK_MIN_SHAKE": 3.5})):
            self.assertEqual(offtrack_chart(self.data).thresholds, [("min", 3.5)])


class ShakeAxisTest(unittest.TestCase):
    def test_shake_of_another_axis(self):
        # Shaking sideways only: nothing for the rule, which looks up and down.
        shaking = [SensorSecond(0.0, [(-9.8, 3.0, 0.0), (-9.8, -3.0, 0.0)] * 5, [(0.0, 0.0, 0.0)] * 10)]
        self.assertEqual({shake for _, shake in shake_over_time(shaking)}, {0.0})
        sideways = shake_over_time(shaking, settings.ACCELERATION_AXIS_SIDEWAYS)
        self.assertEqual({shake for _, shake in sideways}, {3.0})


class ScaleTest(unittest.TestCase):
    def test_scale_reaches_twice_the_threshold(self):
        chart = pace_chart(driving([(0.2, 0.0)] * 300))   # all values far below the thresholds
        self.assertEqual((chart.low, chart.high), (0.0, 2 * settings.PACE_HARD_FORCE))

    def test_one_spike_does_not_stretch_the_scale(self):
        # 1000 quiet seconds and a single jolt of 400.
        chart = pace_chart(driving([(0.2, 0.0)] * 500 + [(400.0, 0.0)] + [(0.2, 0.0)] * 500))
        self.assertLess(chart.high, 50)

    def test_chart_with_values_on_both_sides_is_centred(self):
        chart = sliding_chart(caught_slide())
        self.assertEqual(chart.low, -chart.high)


class WindowTest(unittest.TestCase):
    def test_window(self):
        line = Line("x", [float(time) for time in range(10)], [time * 10 for time in range(10)], True)
        self.assertEqual(window(line, 2.5, 5.0), ([3.0, 4.0, 5.0], [30, 40, 50]))
        self.assertEqual(window(line, 20.0, 30.0), ([], []))
        self.assertEqual(window(line, -5.0, 0.5), ([0.0], [0]))


class ChartListTest(unittest.TestCase):
    def test_every_chart_can_be_made_by_name(self):
        self.assertEqual(sorted(CHARTS), ["offtrack", "pace", "sliding", "turning"])
        for make_chart in CHARTS.values():
            self.assertTrue(make_chart(racing()).lines)


if __name__ == "__main__":
    unittest.main()
