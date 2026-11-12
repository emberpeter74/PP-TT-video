"""Checks for comparing a detected timeline with a reference."""

import unittest

from pp_tt_video.compare import compare_timelines, format_scores, to_intervals
from pp_tt_video.events import Event

REFERENCE = [
    Event(0, ("warm up",)),
    Event(104, ("clear",)),
    Event(151, ("offtrack",)),
    Event(153, ("clear",)),
    Event(325, ("overtaking",)),
    Event(332, ("clear",)),
]


def scores_by_label(reference, detected, tolerance=5):
    """Return the scores as {label: (correct, missed, false alarms)}."""
    scores = compare_timelines(reference, detected, tolerance)
    return {s.label: (s.correct, s.missed, s.false_alarms) for s in scores}


class IntervalsTest(unittest.TestCase):
    def test_clear_is_left_out_and_ends_are_filled_in(self):
        intervals = to_intervals([Event(0, ("clear",)), Event(10, ("sliding",)), Event(13, ("clear",))])
        self.assertEqual(intervals, {"sliding": [(10, 13)]})

    def test_label_over_two_lines_is_one_event(self):
        timeline = [Event(0, ("clear",)), Event(10, ("overtaken",)), Event(12, ("overtaken", "sliding")), Event(15, ("clear",))]
        self.assertEqual(to_intervals(timeline), {"overtaken": [(10, 15)], "sliding": [(12, 15)]})


class CompareTest(unittest.TestCase):
    def test_identical_timelines_are_all_correct(self):
        self.assertEqual(
            scores_by_label(REFERENCE, REFERENCE),
            {"warm up": (1, 0, 0), "offtrack": (1, 0, 0), "overtaking": (1, 0, 0)},
        )

    def test_shift_within_tolerance_still_counts(self):
        # The off-track moment is detected 4 seconds late.
        detected = [Event(0, ("warm up",)), Event(104, ("clear",)), Event(157, ("offtrack",)), Event(159, ("clear",)),
                    Event(325, ("overtaking",)), Event(332, ("clear",))]
        self.assertEqual(scores_by_label(REFERENCE, detected)["offtrack"], (1, 0, 0))

    def test_shift_beyond_tolerance_is_a_miss_and_a_false_alarm(self):
        # The off-track moment is detected 20 seconds late.
        detected = [Event(0, ("warm up",)), Event(104, ("clear",)), Event(173, ("offtrack",)), Event(175, ("clear",)),
                    Event(325, ("overtaking",)), Event(332, ("clear",))]
        self.assertEqual(scores_by_label(REFERENCE, detected)["offtrack"], (0, 1, 1))

    def test_missed_event(self):
        detected = [Event(0, ("warm up",)), Event(104, ("clear",)), Event(325, ("overtaking",)), Event(332, ("clear",))]
        self.assertEqual(scores_by_label(REFERENCE, detected)["offtrack"], (0, 1, 0))

    def test_false_alarm_and_wrong_label(self):
        # The overtake is reported as "overtaken", and a slide is invented.
        detected = [Event(0, ("warm up",)), Event(104, ("clear",)), Event(151, ("offtrack",)), Event(153, ("clear",)),
                    Event(200, ("sliding",)), Event(203, ("clear",)), Event(325, ("overtaken",)), Event(332, ("clear",))]
        scores = scores_by_label(REFERENCE, detected)
        self.assertEqual(scores["sliding"], (0, 0, 1))
        self.assertEqual(scores["overtaking"], (0, 1, 0))
        self.assertEqual(scores["overtaken"], (0, 0, 1))

    def test_one_detection_cannot_cover_two_events(self):
        reference = [Event(0, ("clear",)), Event(10, ("sliding",)), Event(12, ("clear",)), Event(14, ("sliding",)), Event(16, ("clear",))]
        detected = [Event(0, ("clear",)), Event(10, ("sliding",)), Event(12, ("clear",))]
        self.assertEqual(scores_by_label(reference, detected)["sliding"], (1, 1, 0))

    def test_table_has_a_total_line(self):
        table = format_scores(compare_timelines(REFERENCE, REFERENCE))
        self.assertIn("total", table.splitlines()[-1])


if __name__ == "__main__":
    unittest.main()
