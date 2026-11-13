"""Checks for reading and writing events files."""

import tempfile
import unittest
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.event_types import known_labels, load_event_types
from pp_tt_video.events import (
    Event,
    EventsFileError,
    events_path_for,
    find_problems,
    format_time,
    parse_time,
    read_events_file,
    write_events_file,
)

EXAMPLE_FOLDER = settings.PROJECT_FOLDER / "example video  and output file"
REFERENCE_EVENTS = EXAMPLE_FOLDER / "RaceBox Track Sessionon 30-05-2026 09-41-events.txt"


class TimeTest(unittest.TestCase):
    def test_format_time(self):
        self.assertEqual(format_time(0), "00:00")
        self.assertEqual(format_time(104), "01:44")
        self.assertEqual(format_time(3599), "59:59")
        self.assertEqual(format_time(3600), "1:00:00")
        self.assertEqual(format_time(4510), "1:15:10")

    def test_parse_time(self):
        self.assertEqual(parse_time("01:44"), 104)
        self.assertEqual(parse_time("1:15:10"), 4510)

    def test_parse_time_rejects_other_text(self):
        for text in ["", "abc", "12", "1:2:3:4", "01:4x"]:
            with self.assertRaises(ValueError):
                parse_time(text)


class NameTest(unittest.TestCase):
    def test_events_file_keeps_the_video_name(self):
        self.assertEqual(events_path_for(Path("a/something.MP4")), Path("a/something-events.txt"))


class ReadWriteTest(unittest.TestCase):
    def setUp(self):
        # A fresh temporary folder for every check; removed afterwards.
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_write_gives_the_agreed_format(self):
        timeline = [Event(0, ("warm up",)), Event(104, ("clear",)), Event(325, ("overtaken", "sliding"))]
        path = write_events_file(self.folder / "x-events.txt", timeline)
        self.assertEqual(path.read_bytes(), b"00:00 warm up\r\n01:44 clear\r\n05:25 overtaken, sliding\r\n")

    def test_read_returns_what_was_written(self):
        timeline = [Event(0, ("clear",)), Event(4510, ("overtaken", "sliding")), Event(4520, ("clear",))]
        path = write_events_file(self.folder / "x-events.txt", timeline)
        self.assertEqual(read_events_file(path), timeline)

    def test_read_tolerates_upper_case_and_extra_spaces(self):
        path = self.folder / "x-events.txt"
        path.write_text("00:00 Clear\n\n02:27 obstacle \n03:00 Overtaken ,  Sliding\n")
        self.assertEqual(
            read_events_file(path),
            [Event(0, ("clear",)), Event(147, ("obstacle",)), Event(180, ("overtaken", "sliding"))],
        )

    def test_read_reports_a_line_without_time(self):
        path = self.folder / "x-events.txt"
        path.write_text("00:00 clear\nsliding\n")
        with self.assertRaises(EventsFileError):
            read_events_file(path)

    def test_existing_file_is_not_replaced(self):
        path = self.folder / "x-events.txt"
        path.write_text("corrected by hand")
        with self.assertRaises(FileExistsError):
            write_events_file(path, [Event(0, ("clear",))])
        self.assertEqual(path.read_text(), "corrected by hand")

    def test_broken_timeline_is_not_written(self):
        path = self.folder / "x-events.txt"
        with self.assertRaises(EventsFileError):
            write_events_file(path, [Event(5, ("clear",))])
        self.assertFalse(path.exists())

    @unittest.skipUnless(REFERENCE_EVENTS.exists(), "example events file is not on this PC")
    def test_reference_file_is_reproduced_exactly(self):
        timeline = read_events_file(REFERENCE_EVENTS)
        path = write_events_file(self.folder / "copy-events.txt", timeline, known_labels())
        self.assertEqual(path.read_bytes(), REFERENCE_EVENTS.read_bytes())


class ProblemsTest(unittest.TestCase):
    def test_good_timeline_has_no_problems(self):
        timeline = [Event(0, ("warm up",)), Event(10, ("clear",))]
        self.assertEqual(find_problems(timeline, {"warm up", "clear"}), [])

    def test_problems_are_found(self):
        timeline = [Event(3, ("clear",)), Event(2, ("sliding",)), Event(2, ("crash",))]
        problems = find_problems(timeline, {"clear", "sliding"})
        # Not starting at 00:00, two times out of order, one unknown label.
        self.assertEqual(len(problems), 4)

    def test_empty_timeline(self):
        self.assertEqual(find_problems([]), ["the timeline is empty"])


class EventTypesTest(unittest.TestCase):
    def test_list_contains_the_agreed_labels(self):
        labels = set(load_event_types())
        expected = {"out of session", "warm up", "clear", "offtrack", "sliding", "overtaking", "overtaken", "held up", "obstacle", "crash", "cooling"}
        self.assertEqual(labels, expected)

    def test_other_event_is_always_known(self):
        self.assertIn("other event", known_labels())

    def test_every_type_has_a_description_and_no_comma_in_its_label(self):
        for label, description in load_event_types().items():
            self.assertTrue(description, label)
            self.assertNotIn(",", label)


if __name__ == "__main__":
    unittest.main()
