"""Checks for the overview picture: one picture of a whole video.

Text and bars cannot be read back from a picture, so these checks look at
its size and compare two drawings with each other.
"""

import tempfile
import unittest
from dataclasses import replace   # replace(thing, field=value): a copy with one field changed
from pathlib import Path

from PIL import Image, ImageChops

from pp_tt_video.explain import DroppedStretch, explain
from pp_tt_video.overview import WIDTH, draw_overview, overview_path_for, write_overview
from pp_tt_video.stretch import Stretch
from tests.helpers import detections_of
from tests.test_explain import VIDEO_SECONDS, gentle_driving, hard_driving, overtaken_car


def same_picture(picture, other):
    """True when two pictures of the same size are equal pixel for pixel."""
    # difference() gives a black picture where the two are equal; getbbox()
    # returns None for a picture that is black all over.
    return picture.size == other.size and ImageChops.difference(picture, other).getbbox() is None


def at_pace():
    """A video driven at pace from start to end, with one car that is passed."""
    return explain(detections_of(overtaken_car()), hard_driving(), VIDEO_SECONDS)


def draw(explanation, profile_name="built-in values"):
    return draw_overview(explanation, profile_name, "x.mp4")


class OverviewPathTest(unittest.TestCase):
    def test_path(self):
        self.assertEqual(overview_path_for(Path("videos") / "x.mp4"), Path("videos") / "x-overview.png")
        self.assertEqual(overview_path_for(Path("videos") / "x.mp4", "out"), Path("out") / "x-overview.png")


class DrawOverviewTest(unittest.TestCase):
    def test_size(self):
        picture = draw(at_pace())
        self.assertEqual(picture.width, WIDTH)
        self.assertEqual(WIDTH, 2000)
        self.assertGreater(picture.height, 200)

    def test_every_label_gets_a_row(self):
        explanation = at_pace()
        more = replace(explanation, kept_stretches=explanation.kept_stretches + [Stretch(10, 20, "sliding")])
        self.assertGreater(draw(more).height, draw(explanation).height)

    def test_dropped_and_kept_bars_differ(self):
        explanation = replace(at_pace(), kept_stretches=[], dropped_stretches=[])
        stretch = Stretch(100, 130, "sliding")
        kept = draw(replace(explanation, kept_stretches=[stretch]))
        dropped = draw(replace(explanation, dropped_stretches=[DroppedStretch(stretch, "outside the part at pace")]))
        self.assertEqual(kept.size, dropped.size)
        self.assertFalse(same_picture(kept, dropped))

    def test_a_very_short_event_is_still_drawn(self):
        explanation = replace(at_pace(), kept_stretches=[], dropped_stretches=[])
        without = draw(replace(explanation, kept_stretches=[Stretch(50, 60, "sliding")]))
        # The same row, with one more event that lasts a tenth of a second.
        short = draw(replace(explanation, kept_stretches=[Stretch(50, 60, "sliding"), Stretch(200, 200.1, "sliding")]))
        self.assertFalse(same_picture(without, short))

    def test_the_cars_are_drawn(self):
        with_car = at_pace()
        without = explain(detections_of([]), hard_driving(), VIDEO_SECONDS)
        without = replace(without, kept_stretches=with_car.kept_stretches)   # the same rows
        self.assertFalse(same_picture(draw(with_car), draw(without)))

    def test_the_session_parts_are_drawn(self):
        # Gentle driving is one long warm up, hard driving has none.
        gentle = explain(detections_of([]), gentle_driving(), VIDEO_SECONDS)
        self.assertTrue(gentle.session_parts)
        self.assertFalse(same_picture(draw(gentle), draw(replace(gentle, session_parts=[]))))

    def test_the_profile_name_is_written(self):
        explanation = at_pace()
        self.assertFalse(same_picture(draw(explanation, "built-in values"), draw(explanation, "son")))

    def test_no_sensor_data_does_not_fail(self):
        explanation = explain(detections_of(overtaken_car()), [], VIDEO_SECONDS)
        self.assertEqual(draw(explanation).width, WIDTH)

    def test_nothing_at_all_does_not_fail(self):
        self.assertEqual(draw(explain(detections_of([]), [], 0.0)).width, WIDTH)

    def test_very_short_video_does_not_fail(self):
        explanation = explain(detections_of(overtaken_car(start=0.0)), hard_driving()[:5], 5.0)
        self.assertEqual(draw(explanation).width, WIDTH)

    def test_long_video_does_not_fail(self):
        # Two hours: the minute marks must thin out instead of running into each other.
        explanation = replace(at_pace(), duration_seconds=7200.0)
        self.assertEqual(draw(explanation).width, WIDTH)


class WriteOverviewTest(unittest.TestCase):
    def test_writes_a_picture_and_leaves_nothing_else(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "x-overview.png"
            write_overview(path, at_pace(), "built-in values", "x.mp4")
            with Image.open(path) as picture:
                self.assertEqual(picture.width, WIDTH)
            self.assertEqual([entry.name for entry in Path(folder).iterdir()], ["x-overview.png"])


if __name__ == "__main__":
    unittest.main()
