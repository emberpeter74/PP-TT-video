"""Checks for writing a whole check video."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pp_tt_video import check_video_settings, settings
from pp_tt_video.check_video import check_video_path_for, write_check_video
from pp_tt_video.detect_cars import CarBox
from pp_tt_video.draw import picture_size
from pp_tt_video.explain import explain
from pp_tt_video.video import VideoWriter, read_frames, read_video_info
from tests.helpers import detections_of, pictures_of

TOOLS_PRESENT = settings.FFMPEG.exists() and settings.FFPROBE.exists()


class CheckVideoPathTest(unittest.TestCase):
    def test_path(self):
        self.assertEqual(check_video_path_for(Path("a") / "x.MP4"), Path("a") / "x-check.mp4")
        self.assertEqual(check_video_path_for(Path("a") / "x.MP4", "out"), Path("out") / "x-check.mp4")


@unittest.skipUnless(TOOLS_PRESENT, "ffmpeg is not in the executables folder")
class WriteCheckVideoTest(unittest.TestCase):
    """Makes a tiny black source video, then a check video of it.

    Everything runs on the processor and at a small picture size, so the
    check takes a second and needs no graphics card.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.source = self.folder / "source.mp4"
        black = bytes(320 * 180 * 3)
        with VideoWriter(self.source, 320, 180, 10, use_graphics_card=False) as writer:
            for _ in range(20):   # 2 seconds
                writer.write(black)
        for name, value in [("ANALYSIS_WIDTH", 320), ("USE_GRAPHICS_CARD", False)]:
            patcher = mock.patch.object(settings, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(check_video_settings, "FRAMES_PER_SECOND", 10)
        patcher.start()
        self.addCleanup(patcher.stop)
        # One car, seen in every analysed picture of the two seconds.
        box = CarBox(40, 60, 120, 120, 0.95)
        detections = detections_of(pictures_of([[box] * 10]), picture_height=180)
        detections.analysis_width = 320
        self.explanation = explain(detections, [], 2.0)

    def test_check_video_has_the_size_and_length_of_the_source(self):
        output = self.folder / "source-check.mp4"
        progress = []
        write_check_video(self.source, output, self.explanation, "built-in values", progress.append)
        info = read_video_info(output)
        self.assertEqual((info.width, info.height), picture_size(320, 180, 0))
        self.assertAlmostEqual(info.duration_seconds, 2.0, delta=0.3)
        self.assertAlmostEqual(progress[-1], 1.0, delta=0.1)
        self.assertEqual(sorted(entry.name for entry in self.folder.iterdir()), ["source-check.mp4", "source.mp4"])

    def test_the_box_is_in_the_video(self):
        output = self.folder / "source-check.mp4"
        write_check_video(self.source, output, self.explanation, "built-in values")
        frame = next(read_frames(output, start_seconds=1, frames_per_second=10, width=320))

        def brightness(x, y):
            position = (y * frame.width + x) * 3
            return sum(frame.pixels[position:position + 3])

        # On the left edge of the box the picture is no longer black; in the
        # middle of the box it still is. (Video compression blurs a little,
        # so "black" means "dark".)
        self.assertGreater(brightness(40, 90), 150)
        self.assertLess(brightness(80, 90), 60)


if __name__ == "__main__":
    unittest.main()
