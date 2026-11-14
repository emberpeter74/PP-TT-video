"""Checks for reading a driver and car profile and applying it."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pp_tt_video import settings
from pp_tt_video.profile import (
    BUILT_IN,
    Profile,
    ProfileError,
    find_profile,
    load_profile,
    profile_for_video,
    using_profile,
)


def write_file(folder, name, content):
    """Write a profile file into a folder and return its path.

    content may be text or raw bytes (for the file with a BOM).
    """
    path = Path(folder) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


class LoadProfileTest(unittest.TestCase):
    def setUp(self):
        # A fresh empty folder for every test, removed again afterwards.
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def load(self, name, content):
        return load_profile(write_file(self.folder.name, name, content))

    def test_reads_values(self):
        profile = self.load("son.toml", "PACE_MIN_EFFORT = 0.5\nOFFTRACK_MIN_SHAKE = 6\n")
        self.assertEqual(profile.values, {"PACE_MIN_EFFORT": 0.5, "OFFTRACK_MIN_SHAKE": 6.0})
        self.assertIsInstance(profile.values["OFFTRACK_MIN_SHAKE"], float)
        self.assertEqual(profile.name, "son")

    def test_folder_file_is_named_after_its_folder(self):
        profile = self.load("practice driver/profile.toml", "PACE_MIN_EFFORT = 0.5\n")
        self.assertEqual(profile.name, "practice driver")

    def test_comments_and_empty_file_are_fine(self):
        profile = self.load("son.toml", "# only a comment\n\n# PACE_MIN_EFFORT = 0.5\n")
        self.assertEqual(profile.values, {})

    def test_file_saved_with_bom(self):
        # Windows Notepad may put three invisible bytes (a "BOM") at the start.
        profile = self.load("son.toml", b"\xef\xbb\xbfPACE_MIN_EFFORT = 0.5\n")
        self.assertEqual(profile.values, {"PACE_MIN_EFFORT": 0.5})

    def test_unknown_name_is_refused(self):
        with self.assertRaises(ProfileError) as caught:
            self.load("son.toml", "PACE_MIN_EFORT = 0.5\n")
        self.assertIn("PACE_MIN_EFORT", str(caught.exception))
        self.assertIn("son.toml", str(caught.exception))

    def test_name_that_is_a_setting_but_not_a_profile_value_is_refused(self):
        # A real setting, but not one a profile may change.
        with self.assertRaises(ProfileError) as caught:
            self.load("son.toml", "ANALYSIS_WIDTH = 640\n")
        self.assertIn("ANALYSIS_WIDTH", str(caught.exception))

    def test_text_value_is_refused(self):
        with self.assertRaises(ProfileError) as caught:
            self.load("son.toml", 'PACE_MIN_EFFORT = "low"\n')
        self.assertIn("PACE_MIN_EFFORT", str(caught.exception))

    def test_true_false_is_refused(self):
        with self.assertRaises(ProfileError):
            self.load("son.toml", "PACE_MIN_EFFORT = true\n")

    def test_broken_file_is_refused(self):
        with self.assertRaises(ProfileError) as caught:
            self.load("son.toml", "PACE_MIN_EFFORT = \n")
        self.assertIn("son.toml", str(caught.exception))

    def test_missing_file_is_refused(self):
        missing = Path(self.folder.name) / "nobody.toml"
        with self.assertRaises(ProfileError) as caught:
            load_profile(missing)
        self.assertIn("nobody.toml", str(caught.exception))


class FindProfileTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        # The named profiles live in a temporary folder during these checks,
        # not in the real "profiles" folder of the project.
        self.profiles = self.folder / "profiles"
        patcher = mock.patch.object(settings, "PROFILES_FOLDER", self.profiles)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.video = self.folder / "videos" / "a.MP4"
        self.video.parent.mkdir()

    def test_option_name_means_profiles_folder(self):
        self.assertEqual(find_profile(self.video, "son"), self.profiles / "son.toml")

    def test_option_ending_in_toml_is_a_path(self):
        self.assertEqual(find_profile(self.video, "some/where/x.TOML"), Path("some/where/x.TOML"))

    def test_option_wins_over_folder_file(self):
        write_file(self.video.parent, "profile.toml", "PACE_MIN_EFFORT = 0.5\n")
        self.assertEqual(find_profile(self.video, "son"), self.profiles / "son.toml")

    def test_folder_file_is_found(self):
        path = write_file(self.video.parent, "profile.toml", "PACE_MIN_EFFORT = 0.5\n")
        self.assertEqual(find_profile(self.video, None), path)

    def test_nothing_gives_none(self):
        self.assertIsNone(find_profile(self.video, None))

    def test_profile_for_video_reads_the_folder_file(self):
        write_file(self.video.parent, "profile.toml", "PACE_MIN_EFFORT = 0.5\n")
        profile = profile_for_video(self.video, None)
        self.assertEqual(profile.values, {"PACE_MIN_EFFORT": 0.5})
        self.assertEqual(profile.name, "videos")

    def test_profile_for_video_without_profile_is_built_in(self):
        self.assertEqual(profile_for_video(self.video, None), BUILT_IN)

    def test_missing_named_profile_says_where_it_looked(self):
        with self.assertRaises(ProfileError) as caught:
            profile_for_video(self.video, "son")
        self.assertIn("son.toml", str(caught.exception))


class DescriptionTest(unittest.TestCase):
    def test_built_in(self):
        self.assertEqual(BUILT_IN.description, "built-in values")

    def test_file_profile(self):
        profile = Profile("son", Path("profiles") / "son.toml", {})
        self.assertEqual(profile.description, "son (son.toml)")


class UsingProfileTest(unittest.TestCase):
    def test_values_set_inside_and_restored_after(self):
        before = settings.PACE_MIN_EFFORT
        with using_profile(Profile("x", None, {"PACE_MIN_EFFORT": 0.5})):
            self.assertEqual(settings.PACE_MIN_EFFORT, 0.5)
        self.assertEqual(settings.PACE_MIN_EFFORT, before)

    def test_restored_after_an_error(self):
        before = settings.PACE_MIN_EFFORT
        with self.assertRaises(ValueError):
            with using_profile(Profile("x", None, {"PACE_MIN_EFFORT": 0.5})):
                raise ValueError("something went wrong inside")
        self.assertEqual(settings.PACE_MIN_EFFORT, before)

    def test_values_not_in_the_profile_are_left_alone(self):
        before = settings.SLIDE_MIN_CORNERING_FORCE
        with using_profile(Profile("x", None, {"PACE_MIN_EFFORT": 0.5})):
            self.assertEqual(settings.SLIDE_MIN_CORNERING_FORCE, before)

    def test_built_in_changes_nothing(self):
        before = settings.PACE_MIN_EFFORT
        with using_profile(BUILT_IN):
            self.assertEqual(settings.PACE_MIN_EFFORT, before)


if __name__ == "__main__":
    unittest.main()
