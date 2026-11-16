"""Checks for processing a set of videos."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pp_tt_video import check_video_settings, settings
from pp_tt_video.detect_cars import CarBox
from pp_tt_video.detections_file import Detections, load_detections
from pp_tt_video.objects_file import load_objects
from pp_tt_video.pipeline import find_videos, make_sensor_file, process_videos
from pp_tt_video.sensors import SensorError, SensorSecond
from pp_tt_video.video import VideoInfo
from tests.helpers import cone_box, objects_of


def small_detections():
    """What a detection pass over a very short video could return: one car, 15 pictures."""
    pictures = [(number * 0.2, [CarBox(600, 300, 680, 360, 0.95)]) for number in range(15)]
    return Detections(
        analysis_width=settings.ANALYSIS_WIDTH,
        picture_height=720,
        frames_per_second=settings.ANALYSIS_FRAMES_PER_SECOND,
        min_confidence=settings.MIN_DETECTION_CONFIDENCE,
        pictures=pictures,
    )


def small_objects(lying_cone_at=None):
    """What a search for objects over a very short video could return.

    15 pictures, each with a standing cone; with lying_cone_at, the picture
    at that time also has a cone lying on its side.
    """
    pictures = []
    for number in range(15):
        time = round(number * 0.2, 3)
        boxes = [cone_box(300, 15, 30, 0.6)]
        if time == lying_cone_at:
            boxes.append(cone_box(700, 30, 15, 0.4))
        pictures.append((time, boxes))
    objects = objects_of(pictures)
    objects.analysis_width = settings.ANALYSIS_WIDTH
    return objects


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
        self.seen = []   # the PACE_MIN_EFFORT the rules saw, per video

        def fake_timeline_from_detections(video, detections, objects=None):
            self.seen.append(settings.PACE_MIN_EFFORT)
            return []

        # The models are not loaded, the slow passes over the pictures and
        # the rules are fakes, and no events file is written (the fake gives
        # no real timeline).
        for target, replacement in [
            ("pp_tt_video.detect_cars.CarDetector", mock.MagicMock()),
            ("pp_tt_video.find_objects.ObjectDetector", mock.MagicMock()),
            ("pp_tt_video.find_objects.find_objects", lambda video, detector, on_progress=None: small_objects()),
            ("pp_tt_video.detect_events.detect_boxes", lambda video, detector, on_progress=None: small_detections()),
            ("pp_tt_video.detect_events.timeline_from_detections", fake_timeline_from_detections),
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


class DetectionsInPipelineTest(unittest.TestCase):
    """With --check-video the detections are saved once and reused.

    The slow pass over the pictures is a fake that counts how often it is
    called. The rules are the real ones, working on the fake's detections,
    with a made-up video length and no sensor data.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.video = self.folder / "x.mp4"
        self.video.write_bytes(b"")
        self.detection_runs = 0
        self.drawn = []   # per check video drawn: (profile name, pace value in force, explanation)

        def fake_detect_boxes(video, detector, on_progress=None):
            self.detection_runs += 1
            return small_detections()

        def fake_write_check_video(video, output_path, explanation, profile_name, on_progress=None):
            # Stands in for the drawing: notes what it was given and leaves a file.
            self.drawn.append((profile_name, settings.PACE_MIN_EFFORT, explanation))
            Path(output_path).write_bytes(b"a check video")

        info = VideoInfo(width=5312, height=2988, frames_per_second=29.97, duration_seconds=3.0, codec="hevc")
        for target, replacement in [
            ("pp_tt_video.detect_cars.CarDetector", mock.MagicMock()),
            ("pp_tt_video.find_objects.ObjectDetector", mock.MagicMock()),
            ("pp_tt_video.find_objects.find_objects", lambda video, detector, on_progress=None: small_objects()),
            ("pp_tt_video.detect_events.detect_boxes", fake_detect_boxes),
            ("pp_tt_video.detect_events.read_video_info", lambda video: info),
            ("pp_tt_video.detect_events.read_sensors", lambda video: []),
            ("pp_tt_video.pipeline.read_sensors", lambda video: []),
            ("pp_tt_video.pipeline.read_video_info", lambda video: info),
            ("pp_tt_video.check_video.write_check_video", fake_write_check_video),
        ]:
            patcher = mock.patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_module(self, output_name, **options):
        output = self.folder / output_name
        output.mkdir(exist_ok=True)
        process_videos([self.video], output_folder=output, **options)
        return output

    def test_without_the_option_nothing_is_saved(self):
        output = self.run_module("plain")
        self.assertTrue((output / "x-events.txt").is_file())
        self.assertFalse((output / "x-detections.json").exists())

    def test_with_the_option_the_detections_are_saved(self):
        output = self.run_module("check", check_video=True)
        self.assertEqual(load_detections(output / "x-detections.json"), small_detections())
        self.assertEqual(self.detection_runs, 1)   # one pass serves the events and the saving

    def test_saved_detections_are_reused(self):
        output = self.run_module("check", check_video=True)
        (output / "x-events.txt").unlink()   # so the events are made again
        self.run_module("check", check_video=True)
        self.assertTrue((output / "x-events.txt").is_file())
        self.assertEqual(self.detection_runs, 1)

    def test_detections_are_made_when_the_events_file_already_exists(self):
        output = self.run_module("check")                      # events only
        self.assertEqual(self.detection_runs, 1)
        self.run_module("check", check_video=True)             # events skipped
        self.assertTrue((output / "x-detections.json").is_file())
        self.assertEqual(self.detection_runs, 2)

    def test_detections_from_other_settings_are_not_reused(self):
        output = self.run_module("check", check_video=True)
        (output / "x-events.txt").unlink()
        with mock.patch.object(settings, "ANALYSIS_FRAMES_PER_SECOND", 10):
            self.run_module("check", check_video=True)
        self.assertEqual(self.detection_runs, 2)

    def test_half_written_detections_are_not_reused(self):
        output = self.run_module("check", check_video=True)
        (output / "x-events.txt").unlink()
        (output / "x-detections.json").write_text('{"pictures": [', encoding="utf-8")
        self.run_module("check", check_video=True)
        self.assertEqual(self.detection_runs, 2)
        self.assertEqual(load_detections(output / "x-detections.json"), small_detections())

    def test_overwrite_detects_again_but_only_once(self):
        self.run_module("check", check_video=True)
        self.run_module("check", check_video=True, overwrite=True)
        self.assertEqual(self.detection_runs, 2)

    def test_without_the_option_no_check_video_is_made(self):
        output = self.run_module("plain")
        self.assertEqual(self.drawn, [])
        self.assertFalse((output / "x-check.mp4").exists())

    def test_check_video_is_written(self):
        output = self.run_module("check", check_video=True)
        self.assertTrue((output / "x-check.mp4").is_file())
        self.assertEqual(len(self.drawn), 1)
        profile_name, _, explanation = self.drawn[0]
        self.assertEqual(profile_name, "built-in values")
        # The drawing is given the car of the detections, with its number.
        self.assertEqual(explanation.pictures[0].kept[0].track_number, 1)
        self.assertEqual(explanation.duration_seconds, 3.0)
        self.assertEqual(self.detection_runs, 1)   # one pass for events and check video

    def test_check_video_is_given_the_objects(self):
        from pp_tt_video.explain import objects_at
        self.run_module("check", check_video=True)
        _, _, explanation = self.drawn[0]
        # small_objects has a standing cone in every picture.
        self.assertEqual([lying for _, lying in objects_at(explanation, 0.0)], [False])

    def test_check_video_is_skipped_when_it_exists(self):
        self.run_module("check", check_video=True)
        self.run_module("check", check_video=True)
        self.assertEqual(len(self.drawn), 1)
        self.assertEqual(self.detection_runs, 1)

    def test_check_video_is_drawn_again_from_the_saved_detections(self):
        output = self.run_module("check", check_video=True)
        (output / "x-check.mp4").unlink()
        self.run_module("check", check_video=True)
        self.assertEqual(len(self.drawn), 2)
        self.assertEqual(self.detection_runs, 1)

    def test_check_video_uses_the_profile(self):
        (self.folder / "profile.toml").write_text("PACE_MIN_EFFORT = 0.5\n", encoding="utf-8")
        built_in = settings.PACE_MIN_EFFORT
        self.run_module("check", check_video=True)
        profile_name, pace_value, _ = self.drawn[0]
        self.assertEqual(profile_name, self.folder.name)
        self.assertEqual(pace_value, 0.5)
        self.assertEqual(settings.PACE_MIN_EFFORT, built_in)

    def test_video_without_sensor_data_still_gets_a_check_video(self):
        def no_sensors(video):
            raise SensorError("ExifTool failed")

        with mock.patch("pp_tt_video.pipeline.read_sensors", no_sensors):
            self.run_module("check", check_video=True)
        self.assertEqual(len(self.drawn), 1)
        self.assertEqual(self.drawn[0][2].sensor_seconds, [])

    def test_overview_is_written_with_the_check_video(self):
        output = self.run_module("check", check_video=True)
        self.assertTrue((output / "x-overview.png").is_file())

    def test_overview_uses_the_profile(self):
        (self.folder / "profile.toml").write_text("PACE_MIN_EFFORT = 0.5\n", encoding="utf-8")
        written = []   # per overview: (profile name, pace value in force, video name)

        def fake_write_overview(path, explanation, profile_name, video_name):
            written.append((profile_name, settings.PACE_MIN_EFFORT, video_name))

        with mock.patch("pp_tt_video.overview.write_overview", fake_write_overview):
            self.run_module("check", check_video=True)
        self.assertEqual(written, [(self.folder.name, 0.5, "x.mp4")])

    def test_without_the_option_no_overview_is_made(self):
        output = self.run_module("plain")
        self.assertFalse((output / "x-overview.png").exists())

    def test_overview_can_be_switched_off(self):
        with mock.patch.object(check_video_settings, "WRITE_OVERVIEW", False):
            output = self.run_module("check", check_video=True)
        self.assertTrue((output / "x-check.mp4").is_file())
        self.assertFalse((output / "x-overview.png").exists())

    def test_missing_overview_is_made_without_drawing_the_video_again(self):
        output = self.run_module("check", check_video=True)
        (output / "x-overview.png").unlink()
        self.run_module("check", check_video=True)
        self.assertTrue((output / "x-overview.png").is_file())
        self.assertEqual(len(self.drawn), 1)       # the check video was left alone
        self.assertEqual(self.detection_runs, 1)   # and the saved detections were used

    def test_existing_overview_is_kept(self):
        output = self.run_module("check", check_video=True)
        (output / "x-overview.png").write_bytes(b"kept")
        (output / "x-check.mp4").unlink()
        self.run_module("check", check_video=True)
        self.assertEqual((output / "x-overview.png").read_bytes(), b"kept")
        self.assertEqual(len(self.drawn), 2)

    def test_overwrite_replaces_the_overview(self):
        output = self.run_module("check", check_video=True)
        (output / "x-overview.png").write_bytes(b"old")
        self.run_module("check", check_video=True, overwrite=True)
        self.assertNotEqual((output / "x-overview.png").read_bytes(), b"old")

    def test_events_file_is_the_same_with_and_without_the_option(self):
        plain = self.run_module("plain")
        check = self.run_module("check", check_video=True)
        self.assertEqual((plain / "x-events.txt").read_bytes(), (check / "x-events.txt").read_bytes())
        # And once more from the saved detections.
        (check / "x-events.txt").unlink()
        self.run_module("check", check_video=True)
        self.assertEqual((plain / "x-events.txt").read_bytes(), (check / "x-events.txt").read_bytes())


class ObjectsInPipelineTest(unittest.TestCase):
    """The search for objects is saved in a file on every run and reused.

    The slow search is a fake that counts how often it is called; the car
    pass is a fake too. The rules are the real ones, with a made-up video
    length and no sensor data (so the whole video counts as at pace).
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.video = self.folder / "x.mp4"
        self.video.write_bytes(b"")
        self.searches = 0
        self.lying_cone_at = 1.0
        self.searching = []   # the progress the search reported

        def fake_find_objects(video, detector, on_progress=None):
            self.searches += 1
            detector.detect([])   # as the real search does: this loads the model
            if on_progress:
                on_progress(1.0)
            return small_objects(self.lying_cone_at)

        info = VideoInfo(width=5312, height=2988, frames_per_second=29.97, duration_seconds=3.0, codec="hevc")
        for target, replacement in [
            ("pp_tt_video.detect_cars.CarDetector", mock.MagicMock()),
            ("pp_tt_video.find_objects.ObjectDetector", mock.MagicMock()),
            ("pp_tt_video.find_objects.find_objects", fake_find_objects),
            ("pp_tt_video.detect_events.detect_boxes", lambda video, detector, on_progress=None: small_detections()),
            ("pp_tt_video.detect_events.read_video_info", lambda video: info),
            ("pp_tt_video.detect_events.read_sensors", lambda video: []),
        ]:
            patcher = mock.patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_module(self, output_name="out", **options):
        output = self.folder / output_name
        output.mkdir(exist_ok=True)
        results = process_videos([self.video], output_folder=output,
                                 on_searching=lambda number, total, part: self.searching.append(part), **options)
        return output, results

    def test_objects_are_saved_on_every_run(self):
        output, _ = self.run_module()
        self.assertEqual(load_objects(output / "x-objects.json"), small_objects(1.0))
        self.assertEqual(self.searches, 1)

    def test_lying_cone_gives_an_obstacle_in_the_events_file(self):
        output, results = self.run_module()
        self.assertIn("events written", results[0].message)   # the GPS step fails on the empty video file
        self.assertIn("obstacle", (output / "x-events.txt").read_text(encoding="utf-8"))

    def test_no_lying_cone_gives_no_obstacle(self):
        self.lying_cone_at = None
        output, _ = self.run_module()
        self.assertNotIn("obstacle", (output / "x-events.txt").read_text(encoding="utf-8"))

    def test_saved_objects_are_reused(self):
        output, _ = self.run_module()
        (output / "x-events.txt").unlink()   # so the events are made again
        self.run_module()
        self.assertTrue((output / "x-events.txt").is_file())
        self.assertEqual(self.searches, 1)

    def test_objects_from_other_settings_are_not_reused(self):
        output, _ = self.run_module()
        (output / "x-events.txt").unlink()
        with mock.patch.object(settings, "OBJECT_MIN_CONFIDENCE", 0.2):
            self.run_module()
        self.assertEqual(self.searches, 2)

    def test_damaged_objects_file_is_replaced(self):
        output, _ = self.run_module()
        (output / "x-events.txt").unlink()
        (output / "x-objects.json").write_text('{"pictures": [', encoding="utf-8")
        _, results = self.run_module()
        self.assertIn("events written", results[0].message)   # the GPS step fails on the empty video file
        self.assertEqual(self.searches, 2)
        self.assertEqual(load_objects(output / "x-objects.json"), small_objects(1.0))

    def test_overwrite_searches_again_but_only_once(self):
        self.run_module(check_video=False)
        with mock.patch("pp_tt_video.check_video.write_check_video",
                        lambda video, path, *rest, **options: Path(path).write_bytes(b"")), \
                mock.patch("pp_tt_video.pipeline.read_sensors", lambda video: []), \
                mock.patch("pp_tt_video.pipeline.read_video_info",
                           lambda video: VideoInfo(5312, 2988, 29.97, 3.0, "hevc")):
            self.run_module(overwrite=True, check_video=True)
        self.assertEqual(self.searches, 2)

    def test_existing_events_file_means_no_search(self):
        output, _ = self.run_module()
        self.run_module()   # the events file exists: skipped
        self.assertEqual(self.searches, 1)

    def test_gps_only_makes_no_objects_file(self):
        output, _ = self.run_module(with_events=False)
        self.assertFalse((output / "x-objects.json").exists())
        self.assertEqual(self.searches, 0)

    def test_search_progress_is_reported(self):
        self.run_module()
        self.assertEqual(self.searching, [1.0])

    def test_missing_library_fails_that_video_and_run_goes_on(self):
        second = self.folder / "y.mp4"
        second.write_bytes(b"")

        def no_library(*arguments, **options):
            raise ImportError("No module named 'transformers'")

        output = self.folder / "out"
        output.mkdir()
        with mock.patch("pp_tt_video.find_objects.ObjectDetector", no_library):
            results = process_videos([self.video, second], output_folder=output)
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertFalse(result.ok)
            self.assertIn("detection libraries are not installed", result.message)


if __name__ == "__main__":
    unittest.main()
