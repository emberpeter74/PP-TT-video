"""Checks for the GPS extraction.

Run all checks from the project folder with:
    py -V:3.13 -m unittest -v
"""

import tempfile
import unittest
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.gps import GpsExtractionError, extract_gps, gpx_path_for

# The example video is 5.3 GB and is not in Git, so it only exists on the
# author's PC. The check that needs it is skipped everywhere else.
EXAMPLE_FOLDER = settings.PROJECT_FOLDER / "example video  and output file"
EXAMPLE_VIDEO = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 09-41.MP4"
REFERENCE_GPX = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 09-41.gpx"


class GpxNameTest(unittest.TestCase):
    def test_gpx_keeps_the_video_name(self):
        self.assertEqual(gpx_path_for(Path("folder/something.mp4")), Path("folder/something.gpx"))

    def test_upper_case_extension_and_spaces(self):
        self.assertEqual(gpx_path_for(Path("My Session 09-41.MP4")), Path("My Session 09-41.gpx"))

    def test_other_output_folder(self):
        self.assertEqual(gpx_path_for(Path("a/something.mp4"), "b"), Path("b/something.gpx"))


class ExtractGpsTest(unittest.TestCase):
    def test_missing_video_is_reported(self):
        with self.assertRaises(GpsExtractionError):
            extract_gps("this file does not exist.mp4")

    def test_existing_gpx_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "something.mp4"
            gpx = Path(folder) / "something.gpx"
            video.write_bytes(b"not a real video")
            gpx.write_text("keep me")
            with self.assertRaises(FileExistsError):
                extract_gps(video)
            self.assertEqual(gpx.read_text(), "keep me")

    def test_file_without_gps_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "something.mp4"
            video.write_bytes(b"not a real video")
            with self.assertRaises(GpsExtractionError):
                extract_gps(video)
            self.assertFalse((Path(folder) / "something.gpx").exists())

    @unittest.skipUnless(EXAMPLE_VIDEO.exists(), "example video is not on this PC")
    def test_example_matches_the_reference_file(self):
        with tempfile.TemporaryDirectory() as folder:
            gpx = extract_gps(EXAMPLE_VIDEO, output_folder=folder)
            self.assertEqual(gpx.read_bytes(), REFERENCE_GPX.read_bytes())


if __name__ == "__main__":
    unittest.main()
