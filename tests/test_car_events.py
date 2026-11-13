"""Checks for the rules that turn car tracks into events."""

import unittest

from pp_tt_video import settings
from pp_tt_video.car_events import Stretch, events_of_track, smooth
from pp_tt_video.detect_cars import CarBox
from pp_tt_video.events import Event
from pp_tt_video.timeline import build_timeline
from pp_tt_video.tracking import Sighting, Track

PICTURE_HEIGHT = 720
STEP = 0.2   # seconds between pictures


def track_with_heights(heights, start=100.0, confidence=0.99):
    """Make a track of a car whose height in pixels follows the given list."""
    sightings = []
    for position, height in enumerate(heights):
        box = CarBox(500, 300, 500 + height * 1.5, 300 + height, confidence)
        sightings.append(Sighting(start + position * STEP, box))
    return Track(sightings)


def labels_of(track):
    return [stretch.label for stretch in events_of_track(track, PICTURE_HEIGHT)]


def steps(first, last, count):
    """Evenly spaced values from first to last."""
    return [first + (last - first) * i / (count - 1) for i in range(count)]


class SmoothTest(unittest.TestCase):
    def test_single_wrong_value_is_removed(self):
        self.assertEqual(smooth([30, 31, 200, 32, 33]), [30, 31, 32, 33, 33])

    def test_lasting_change_is_kept(self):
        self.assertEqual(smooth([30, 30, 90, 90, 90]), [30, 30, 90, 90, 90])


class PassingTest(unittest.TestCase):
    def test_growing_then_gone_is_overtaking(self):
        # From far (25 px) to right beside us (130 px) in 4 seconds, then gone.
        track = track_with_heights(steps(25, 130, 20))
        stretches = events_of_track(track, PICTURE_HEIGHT)
        self.assertEqual([s.label for s in stretches], ["overtaking"])
        # The overtake ends where the car was last seen.
        self.assertAlmostEqual(stretches[0].end, track.end)
        self.assertGreater(stretches[0].start, track.start)

    def test_appearing_large_then_shrinking_is_overtaken(self):
        track = track_with_heights(steps(170, 25, 20))
        stretches = events_of_track(track, PICTURE_HEIGHT)
        self.assertEqual([s.label for s in stretches], ["overtaken"])
        # It starts the lead time before the car first appears.
        self.assertAlmostEqual(stretches[0].start, track.start - settings.OVERTAKEN_LEAD_SECONDS)
        # It ends when the car has pulled away, before the track ends.
        self.assertLess(stretches[0].end, track.end)

    def test_car_seen_large_only_briefly_gives_nothing(self):
        # Large from the first to the last picture: no way to tell who passed whom.
        self.assertEqual(labels_of(track_with_heights([150, 160, 150])), [])

    def test_one_large_picture_gives_nothing(self):
        self.assertEqual(labels_of(track_with_heights([30, 31, 32, 33, 150])), [])

    def test_unsure_detection_gives_nothing(self):
        track = track_with_heights(steps(25, 130, 20), confidence=0.7)
        self.assertEqual(labels_of(track), [])


class HeldUpTest(unittest.TestCase):
    def test_close_for_a_long_time_is_held_up(self):
        # About 60 px tall for 10 seconds, then it falls back out of view.
        track = track_with_heights([60] * 50 + [40, 30, 25])
        stretches = events_of_track(track, PICTURE_HEIGHT)
        self.assertEqual([s.label for s in stretches], ["held up"])
        self.assertAlmostEqual(stretches[0].start, track.start)

    def test_close_for_two_seconds_is_not_held_up(self):
        track = track_with_heights([30] * 10 + [60] * 10 + [30] * 10)
        self.assertEqual(labels_of(track), [])

    def test_car_at_a_distance_is_not_held_up(self):
        # A quicker car that stays 35 px tall for 20 seconds: the track is clear.
        self.assertEqual(labels_of(track_with_heights([35] * 100)), [])

    def test_held_up_then_overtaking(self):
        # Close behind for 10 seconds, then the pass.
        track = track_with_heights([55] * 50 + steps(60, 130, 8))
        stretches = events_of_track(track, PICTURE_HEIGHT)
        self.assertEqual(sorted(s.label for s in stretches), ["held up", "overtaking"])
        held_up = next(s for s in stretches if s.label == "held up")
        overtaking = next(s for s in stretches if s.label == "overtaking")
        # The two do not overlap: held up stops where the overtake starts.
        self.assertLess(held_up.end, overtaking.start)


class TimelineTest(unittest.TestCase):
    def test_gaps_are_filled_with_clear(self):
        timeline = build_timeline([Stretch(120.2, 122.4, "overtaking")], 300)
        self.assertEqual(timeline, [Event(0, ("clear",)), Event(120, ("overtaking",)), Event(123, ("clear",))])

    def test_overlapping_stretches_are_combined_in_list_order(self):
        stretches = [Stretch(10, 20, "sliding"), Stretch(15, 25, "overtaken")]
        timeline = build_timeline(stretches, 60, ["sliding", "overtaken"])
        self.assertEqual(
            timeline,
            [Event(0, ("clear",)), Event(10, ("sliding",)), Event(15, ("sliding", "overtaken")),
             Event(21, ("overtaken",)), Event(26, ("clear",))],
        )

    def test_no_stretches_is_all_clear(self):
        self.assertEqual(build_timeline([], 60), [Event(0, ("clear",))])

    def test_stretch_from_the_start(self):
        timeline = build_timeline([Stretch(0, 3, "held up")], 60)
        self.assertEqual(timeline[0], Event(0, ("held up",)))


if __name__ == "__main__":
    unittest.main()
