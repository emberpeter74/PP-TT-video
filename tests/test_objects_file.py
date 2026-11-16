"""Checks for saving the objects found in a video and loading them again."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pp_tt_video import settings
from pp_tt_video.objects_file import (
    ObjectBox,
    Objects,
    ObjectsError,
    fits_settings,
    load_objects,
    objects_path_for,
    save_objects,
)


def some_objects():
    """Two searched pictures: one with two cones, one with nothing."""
    return Objects(
        analysis_width=settings.ANALYSIS_WIDTH,
        picture_height=720,
        frames_per_second=settings.OBJECT_FRAMES_PER_SECOND,
        min_confidence=settings.OBJECT_MIN_CONFIDENCE,
        model=settings.OBJECT_MODEL,
        words=dict(settings.OBJECT_WORDS),
        pictures=[
            # 0.1 + 0.2 is 0.30000000000000004 in a computer: an awkward
            # number that must come back exactly as it was saved.
            (0.0, [ObjectBox("cone", 100.5, 200.25, 130.75, 0.1 + 0.2, 0.43),
                   ObjectBox("cone", 1.0, 2.0, 3.0, 4.0, 0.2)]),
            (0.2, []),
        ],
    )


class ObjectBoxTest(unittest.TestCase):
    def test_size_and_centre(self):
        box = ObjectBox("cone", 10, 20, 40, 30, 0.5)
        self.assertEqual(box.width, 30)
        self.assertEqual(box.height, 10)
        self.assertEqual(box.centre, (25, 25))


class ObjectsFileTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.path = self.folder / "x-objects.json"

    def test_path(self):
        self.assertEqual(objects_path_for(Path("a") / "x.MP4"), Path("a") / "x-objects.json")
        self.assertEqual(objects_path_for(Path("a") / "x.MP4", "out"), Path("out") / "x-objects.json")

    def test_save_and_load_give_the_same_boxes(self):
        save_objects(self.path, some_objects())
        loaded = load_objects(self.path)
        self.assertEqual(loaded, some_objects())
        self.assertEqual(loaded.pictures[0][1][0].bottom, 0.1 + 0.2)
        self.assertEqual(loaded.pictures[0][1][0].kind, "cone")
        self.assertEqual(loaded.pictures[1], (0.2, []))
        self.assertEqual(loaded.model, settings.OBJECT_MODEL)
        self.assertEqual(loaded.words, settings.OBJECT_WORDS)

    def test_no_part_file_is_left_behind(self):
        save_objects(self.path, some_objects())
        self.assertEqual([entry.name for entry in self.folder.iterdir()], ["x-objects.json"])

    def test_fits_settings(self):
        objects = some_objects()
        self.assertTrue(fits_settings(objects))
        # Objects found with another picture size, picture rate, lowest
        # score, model or words are not what a search would give today.
        for name, value in [("ANALYSIS_WIDTH", 640), ("OBJECT_FRAMES_PER_SECOND", 2),
                            ("OBJECT_MIN_CONFIDENCE", 0.3), ("OBJECT_MODEL", "another model"),
                            ("OBJECT_WORDS", {"cone": "a traffic cone", "person": "a person"})]:
            with mock.patch.object(settings, name, value):
                self.assertFalse(fits_settings(objects), name)

    def test_broken_file_is_refused(self):
        self.path.write_text('{"analysis_width": 1280, "pictures": [', encoding="utf-8")
        with self.assertRaises(ObjectsError):
            load_objects(self.path)

    def test_file_with_missing_parts_is_refused(self):
        self.path.write_text('{"analysis_width": 1280}', encoding="utf-8")
        with self.assertRaises(ObjectsError):
            load_objects(self.path)

    def test_missing_file_is_refused(self):
        with self.assertRaises(ObjectsError):
            load_objects(self.folder / "nothing-objects.json")


if __name__ == "__main__":
    unittest.main()
