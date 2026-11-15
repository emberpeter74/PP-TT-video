"""Checks for writing the motion sensor data to a CSV file."""

import csv
import tempfile
import unittest
from pathlib import Path

from pp_tt_video.sensor_file import sensor_rows, sensors_path_for, write_sensor_file
from pp_tt_video.sensors import SensorSecond


def block(start, count, acceleration=(-9.8, 0.0, 0.0), rotation=(0.0, 0.0, 0.0)):
    """One block of sensor data with the same measurement repeated."""
    return SensorSecond(start, [acceleration] * count, [rotation] * count)


def times_of(rows):
    return [row[0] for row in rows]


class SensorsPathTest(unittest.TestCase):
    def test_path(self):
        self.assertEqual(sensors_path_for(Path("a") / "b" / "x.MP4"), Path("a") / "b" / "x-sensors.csv")
        self.assertEqual(sensors_path_for(Path("a") / "x.MP4", output_folder="out"), Path("out") / "x-sensors.csv")


class SensorRowsTest(unittest.TestCase):
    def test_times_are_spread_over_the_block(self):
        rows = sensor_rows([block(0.0, 4), block(1.0, 4)])
        self.assertEqual(times_of(rows), [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75])

    def test_block_length_follows_the_next_block(self):
        # The camera's blocks are about a second long, not exactly: the time
        # to the next block is the real length.
        rows = sensor_rows([block(0.0, 4), block(2.0, 4)])
        self.assertEqual(times_of(rows)[:4], [0.0, 0.5, 1.0, 1.5])

    def test_last_block_is_one_second_long(self):
        rows = sensor_rows([block(10.0, 2)])
        self.assertEqual(times_of(rows), [10.0, 10.5])

    def test_values_are_kept_as_read(self):
        rows = sensor_rows([block(0.0, 1, acceleration=(-9.8, 1.5, 0.25), rotation=(0.1, -0.2, 0.3))])
        self.assertEqual(rows, [(0.0, -9.8, 1.5, 0.25, 0.1, -0.2, 0.3)])

    def test_missing_rotation_values_are_left_empty(self):
        # A block with one rotation value fewer than acceleration values.
        second = SensorSecond(0.0, [(-9.8, 0.0, 0.0)] * 2, [(0.1, 0.2, 0.3)])
        rows = sensor_rows([second])
        self.assertEqual(rows[1], (0.5, -9.8, 0.0, 0.0, "", "", ""))


class WriteSensorFileTest(unittest.TestCase):
    def test_written_file_reads_back(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "x-sensors.csv"
            write_sensor_file(path, [block(0.0, 4, acceleration=(-9.8, 1.5, 0.25)), block(1.0, 4)])
            with open(path, newline="", encoding="utf-8") as file:
                lines = list(csv.reader(file))
            leftovers = [entry.name for entry in Path(folder).iterdir() if entry != path]
        self.assertEqual(lines[0], [
            "time_seconds", "acceleration_x", "acceleration_y", "acceleration_z",
            "rotation_x", "rotation_y", "rotation_z",
        ])
        self.assertEqual(len(lines), 1 + 8)
        self.assertEqual(lines[2], ["0.2500", "-9.8", "1.5", "0.25", "0.0", "0.0", "0.0"])
        # Nothing half-written is left next to the file.
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
