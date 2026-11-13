"""Checks for reading the motion sensor data."""

import tempfile
import unittest
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.sensors import SensorError, in_groups_of_three, parse_sensor_text, read_sensors

EXAMPLE_FOLDER = settings.PROJECT_FOLDER / "example video  and output file"
EXAMPLE_VIDEO = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 12-17.MP4"


class ParseTest(unittest.TestCase):
    def test_numbers_are_grouped_per_measurement(self):
        self.assertEqual(in_groups_of_three("1 2 3 4.5 5 6"), [(1.0, 2.0, 3.0), (4.5, 5.0, 6.0)])

    def test_blocks_are_read_in_order(self):
        text = (
            "T|0|1.001\n"
            "A|-9.8 0 1 -9.8 0 3\n"
            "G|0.1 0 0 0.3 0 0\n"
            "T|1.001|1.001\n"
            "A|-9.8 2 0\n"
            "G|0 0 0\n"
        )
        seconds = parse_sensor_text(text)
        self.assertEqual(len(seconds), 2)
        self.assertEqual(seconds[0].start_seconds, 0)
        self.assertEqual(seconds[0].acceleration, [(-9.8, 0.0, 1.0), (-9.8, 0.0, 3.0)])
        self.assertEqual(seconds[0].rotation, [(0.1, 0.0, 0.0), (0.3, 0.0, 0.0)])
        self.assertEqual(seconds[1].start_seconds, 1.001)

    def test_block_without_measurements_is_left_out(self):
        text = "T|0|1.001\nT|1.001|1.001\nA|-9.8 0 0\nG|0 0 0\n"
        seconds = parse_sensor_text(text)
        self.assertEqual([second.start_seconds for second in seconds], [1.001])

    def test_other_lines_are_ignored(self):
        self.assertEqual(parse_sensor_text("something else\n\n"), [])


class ReadSensorsTest(unittest.TestCase):
    def test_missing_video_is_reported(self):
        with self.assertRaises(SensorError):
            read_sensors("this file does not exist.mp4")

    def test_file_without_sensor_data_gives_an_empty_list(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "something.mp4"
            video.write_bytes(b"not a real video")
            self.assertEqual(read_sensors(video), [])

    @unittest.skipUnless(EXAMPLE_VIDEO.is_file(), "example video not on this PC")
    def test_example_has_sensor_data_for_the_whole_video(self):
        seconds = read_sensors(EXAMPLE_VIDEO)
        # The video is 6:27 long: one block per second.
        self.assertEqual(len(seconds), 387)
        # About 200 measurements per second, from both sensors.
        self.assertGreater(len(seconds[100].acceleration), 150)
        self.assertGreater(len(seconds[100].rotation), 150)
        # Standing still at the end: only gravity, pointing down.
        down = [m[settings.ACCELERATION_AXIS_DOWN] for m in seconds[-1].acceleration]
        self.assertAlmostEqual(sum(down) / len(down), -9.8, delta=0.5)


if __name__ == "__main__":
    unittest.main()
