"""Checks for processing a set of videos."""

import tempfile
import unittest
from pathlib import Path

from pp_tt_video.pipeline import find_videos, process_videos


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


if __name__ == "__main__":
    unittest.main()
