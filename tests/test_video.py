"""Checks for reading a video in reduced form."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.video import VideoError, VideoInfo, analysis_size, read_frames, read_video_info

EXAMPLE_FOLDER = settings.PROJECT_FOLDER / "example video  and output file"
EXAMPLE_VIDEO = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 12-17.MP4"
TOOLS_PRESENT = settings.FFMPEG.exists() and settings.FFPROBE.exists()


class AnalysisSizeTest(unittest.TestCase):
    def test_wide_video_keeps_its_shape(self):
        info = VideoInfo(5312, 2988, 29.97, 387.0, "hevc")
        self.assertEqual(analysis_size(info, 1280), (1280, 720))

    def test_other_shape_gets_an_even_height(self):
        info = VideoInfo(4000, 3001, 30.0, 10.0, "hevc")
        width, height = analysis_size(info, 1280)
        self.assertEqual(width, 1280)
        self.assertEqual(height % 2, 0)
        self.assertAlmostEqual(height, 1280 * 3001 / 4000, delta=1)


class MissingFileTest(unittest.TestCase):
    def test_missing_video_is_reported(self):
        with self.assertRaises(VideoError):
            read_video_info("this file does not exist.mp4")


@unittest.skipUnless(TOOLS_PRESENT, "ffmpeg is not in the executables folder")
class SmallVideoTest(unittest.TestCase):
    """Uses a tiny test video made by ffmpeg, so no real footage is needed."""

    @classmethod
    def setUpClass(cls):
        # Runs once before the checks in this class: make a 2 second video.
        cls.temporary = tempfile.TemporaryDirectory()
        cls.video = Path(cls.temporary.name) / "small.mp4"
        subprocess.run(
            [str(settings.FFMPEG), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "testsrc=duration=2:size=640x360:rate=30", "-pix_fmt", "yuv420p", str(cls.video)],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_video_info(self):
        info = read_video_info(self.video)
        self.assertEqual((info.width, info.height), (640, 360))
        self.assertAlmostEqual(info.frames_per_second, 30, places=1)
        self.assertAlmostEqual(info.duration_seconds, 2, delta=0.1)

    def test_frames_are_reduced_in_size_and_number(self):
        frames = list(read_frames(self.video, frames_per_second=10, width=320, use_graphics_card=False))
        # 2 seconds at 10 per second.
        self.assertEqual(len(frames), 20)
        for frame in frames:
            self.assertEqual((frame.width, frame.height), (320, 180))
            self.assertEqual(len(frame.pixels), 320 * 180 * 3)
        self.assertAlmostEqual(frames[0].time_seconds, 0.0)
        self.assertAlmostEqual(frames[1].time_seconds, 0.1)
        # The test picture is colourful, so the pixels are not all the same.
        self.assertGreater(len(set(frames[0].pixels)), 10)

    def test_part_of_the_video(self):
        frames = list(read_frames(self.video, start_seconds=1, duration_seconds=0.5,
                                  frames_per_second=10, width=320, use_graphics_card=False))
        self.assertEqual(len(frames), 5)
        self.assertAlmostEqual(frames[0].time_seconds, 1.0)

    def test_stopping_early_is_safe(self):
        for frame in read_frames(self.video, frames_per_second=10, width=320, use_graphics_card=False):
            break   # take one frame and stop
        self.assertEqual(frame.width, 320)

    def test_file_that_is_not_a_video(self):
        not_a_video = Path(self.temporary.name) / "fake.mp4"
        not_a_video.write_bytes(b"not a real video")
        with self.assertRaises(VideoError):
            list(read_frames(not_a_video))


@unittest.skipUnless(TOOLS_PRESENT and EXAMPLE_VIDEO.exists(), "example video is not on this PC")
class ExampleVideoTest(unittest.TestCase):
    def test_example_video_info(self):
        info = read_video_info(EXAMPLE_VIDEO)
        self.assertEqual((info.width, info.height, info.codec), (5312, 2988, "hevc"))
        self.assertAlmostEqual(info.frames_per_second, 29.97, places=2)
        self.assertAlmostEqual(info.duration_seconds, 387.1, delta=0.5)

    @unittest.skipUnless(settings.USE_GRAPHICS_CARD, "graphics card decoding is switched off")
    def test_example_frames_from_the_graphics_card(self):
        frames = list(read_frames(EXAMPLE_VIDEO, start_seconds=10, duration_seconds=2))
        self.assertEqual(len(frames), 2 * settings.ANALYSIS_FRAMES_PER_SECOND)
        self.assertEqual((frames[0].width, frames[0].height), (1280, 720))
        self.assertEqual(len(frames[0].pixels), 1280 * 720 * 3)
        self.assertAlmostEqual(frames[0].time_seconds, 10.0)
        # A real picture has many different brightness values.
        self.assertGreater(len(set(frames[0].pixels)), 50)


if __name__ == "__main__":
    unittest.main()
