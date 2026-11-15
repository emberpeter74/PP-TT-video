"""Checks for processing a set of videos."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pp_tt_video import settings
from pp_tt_video.pipeline import find_videos, make_sensor_file, process_videos
from pp_tt_video.sensors import SensorError, SensorSecond


class FindVideosTest(unittest.TestCase):
    def test_folder_gives_only_its_video_files(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ["b.MP4", "a.mp4", "notes.txt", "a.gpx"]:
                (Path(folder) / name).write_bytes(b"")
            names = [video.name for video in find_videos([folder])]
            self.assertEqual(names, ["a.mp4", "b.MP4"])


class ProgressTest(unittest.TestCase):
    def test_progress_is_reported_per_video_in_order(self):
        calls = []

        def on_start(number, total, video):
            calls.append(("start", number, total, video.name))

        def on_done(number, total, result):
            calls.append(("done", number, total, result.ok))

        # Files that do not exist fail at once, so no real video is needed.
        results = process_videos(["one.mp4", "two.mp4"], on_start=on_start, on_done=on_done)

        self.assertEqual(calls, [
            ("start", 1, 2, "one.mp4"),
            ("done", 1, 2, False),
            ("start", 2, 2, "two.mp4"),
            ("done", 2, 2, False),
        ])
        self.assertEqual(len(results), 2)

    def test_works_without_progress_functions(self):
        results = process_videos(["one.mp4"])
        self.assertFalse(results[0].ok)


class SensorFileInPipelineTest(unittest.TestCase):
    """The sensor file is made from a stand-in reader, so no real video is needed."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.video = self.folder / "x.mp4"
        self.video.write_bytes(b"")
        self.sensor_file = self.folder / "x-sensors.csv"

    @staticmethod
    def one_second(video):
        return [SensorSecond(0.0, [(-9.8, 0.0, 0.0)] * 4, [(0.0, 0.0, 0.0)] * 4)]

    def test_writes_the_file(self):
        ok, message = make_sensor_file(self.video, None, False, read=self.one_second)
        self.assertTrue(ok, message)
        self.assertIn("x-sensors.csv", message)
        self.assertEqual(len(self.sensor_file.read_text(encoding="utf-8").splitlines()), 1 + 4)

    def test_output_folder_is_used(self):
        out = self.folder / "out"
        out.mkdir()
        ok, _ = make_sensor_file(self.video, out, False, read=self.one_second)
        self.assertTrue(ok)
        self.assertTrue((out / "x-sensors.csv").is_file())
        self.assertFalse(self.sensor_file.exists())

    def test_existing_file_is_skipped_without_reading(self):
        self.sensor_file.write_text("mine\n", encoding="utf-8")

        def must_not_read(video):
            raise AssertionError("the video was read although the file exists")

        ok, message = make_sensor_file(self.video, None, False, read=must_not_read)
        self.assertTrue(ok)
        self.assertIn("skipped", message)
        self.assertEqual(self.sensor_file.read_text(encoding="utf-8"), "mine\n")

    def test_overwrite_replaces_the_file(self):
        self.sensor_file.write_text("mine\n", encoding="utf-8")
        ok, _ = make_sensor_file(self.video, None, True, read=self.one_second)
        self.assertTrue(ok)
        self.assertIn("time_seconds", self.sensor_file.read_text(encoding="utf-8"))

    def test_video_without_sensor_data_is_not_a_failure(self):
        ok, message = make_sensor_file(self.video, None, False, read=lambda video: [])
        self.assertTrue(ok)
        self.assertIn("no motion sensor data", message)
        self.assertFalse(self.sensor_file.exists())

    def test_sensor_error_is_a_failure(self):
        def broken(video):
            raise SensorError("ExifTool failed for x.mp4")

        ok, message = make_sensor_file(self.video, None, False, read=broken)
        self.assertFalse(ok)
        self.assertIn("ExifTool failed", message)

    def test_sensor_file_is_also_made_with_gps_only(self):
        with mock.patch("pp_tt_video.pipeline.read_sensors", self.one_second):
            process_videos([self.video], with_events=False)
        self.assertTrue(self.sensor_file.is_file())


class ProfileInPipelineTest(unittest.TestCase):
    """The profile must be in force exactly while a video's events are detected.

    The real detection takes minutes and needs the model, so it is replaced
    by a fake that only notes which pace value it saw. The GPX step fails on
    the empty video files, which does not matter here.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.seen = []   # the PACE_MIN_EFFORT the detection saw, per video

        def fake_detect_timeline(video, detector, on_progress=None):
            self.seen.append(settings.PACE_MIN_EFFORT)
            return []

        # The model is not loaded, the detection is the fake, and no events
        # file is written (the fake gives no real timeline).
        for target, replacement in [
            ("pp_tt_video.detect_cars.CarDetector", mock.MagicMock()),
            ("pp_tt_video.detect_events.detect_timeline", fake_detect_timeline),
            ("pp_tt_video.pipeline.write_events_file", mock.MagicMock()),
        ]:
            patcher = mock.patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def make_folder(self, name, profile_text=None):
        """A folder with one empty video file, and a profile.toml if given."""
        folder = self.folder / name
        folder.mkdir()
        (folder / f"{name.lower()}.mp4").write_bytes(b"")
        if profile_text is not None:
            (folder / "profile.toml").write_text(profile_text, encoding="utf-8")
        return folder

    def test_folder_profile_is_used_for_its_videos(self):
        built_in = settings.PACE_MIN_EFFORT
        folder = self.make_folder("A", "PACE_MIN_EFFORT = 0.5\n")
        process_videos([folder])
        self.assertEqual(self.seen, [0.5])
        self.assertEqual(settings.PACE_MIN_EFFORT, built_in)

    def test_second_folder_without_profile_gets_built_in_values(self):
        built_in = settings.PACE_MIN_EFFORT
        first = self.make_folder("A", "PACE_MIN_EFFORT = 0.5\n")
        second = self.make_folder("B")
        process_videos([first, second])
        self.assertEqual(self.seen, [0.5, built_in])

    def test_profile_option_wins(self):
        folder = self.make_folder("A", "PACE_MIN_EFFORT = 0.5\n")
        other = self.folder / "other.toml"
        other.write_text("PACE_MIN_EFFORT = 0.7\n", encoding="utf-8")
        process_videos([folder], profile_option=str(other))
        self.assertEqual(self.seen, [0.7])

    def test_broken_profile_fails_that_video_and_run_goes_on(self):
        built_in = settings.PACE_MIN_EFFORT
        first = self.make_folder("A", "PACE_MIN_EFORT = 0.5\n")
        second = self.make_folder("B")
        results = process_videos([first, second])
        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].ok)
        self.assertIn("PACE_MIN_EFORT", results[0].message)
        self.assertEqual(self.seen, [built_in])   # only B was detected

    def test_message_names_the_profile(self):
        folder = self.make_folder("A", "PACE_MIN_EFFORT = 0.5\n")
        results = process_videos([folder])
        self.assertIn("profile: A (profile.toml)", results[0].message)

    def test_message_names_built_in_values(self):
        folder = self.make_folder("B")
        results = process_videos([folder])
        self.assertIn("profile: built-in values", results[0].message)

    def test_gps_only_ignores_profiles(self):
        folder = self.make_folder("A", "PACE_MIN_EFORT = 0.5\n")
        results = process_videos([folder], with_events=False)
        self.assertNotIn("profile", results[0].message)
        self.assertEqual(self.seen, [])


if __name__ == "__main__":
    unittest.main()
