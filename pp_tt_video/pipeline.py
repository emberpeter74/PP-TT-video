"""Processes a set of videos, one after the other.

This is the function the main program will call later. Running the module by
hand (see __main__.py) uses the same function.

Every video gets two files: the GPS track (.gpx) and the events file
(-events.txt). The two are made independently: if one fails, the other is
still written.

The events are detected with the video's driver and car profile, if it has
one (see profile.py): the one given with --profile, or the profile.toml in
the video's folder. Otherwise the built-in values of settings.py are used.
"""

import time
from dataclasses import dataclass
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.event_types import known_labels
from pp_tt_video.events import EventsFileError, events_path_for, write_events_file
from pp_tt_video.gps import GpsExtractionError, extract_gps, gpx_path_for
from pp_tt_video.profile import BUILT_IN, ProfileError, profile_for_video, using_profile
from pp_tt_video.video import VideoError


@dataclass
class FileResult:
    """What happened to one video."""

    video: Path
    ok: bool            # False only when something went wrong
    message: str        # a short text for the user
    seconds: float = 0  # how long the processing took


def find_videos(inputs):
    """Turn a list of files and folders into a list of video files.

    A folder stands for all video files directly inside it.
    """
    videos = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            for entry in sorted(path.iterdir()):
                if entry.is_file() and entry.suffix.lower() in settings.VIDEO_EXTENSIONS:
                    videos.append(entry)
        else:
            videos.append(path)
    return videos


def make_gps_file(video, output_folder, overwrite):
    """Write the GPX file. Returns (ok, message)."""
    try:
        gpx_path = extract_gps(video, output_folder=output_folder, overwrite=overwrite)
        return True, f"GPS written to {gpx_path.name}"
    except FileExistsError:
        return True, "GPX file already exists, skipped"
    except GpsExtractionError as error:
        return False, str(error)


class EventsMaker:
    """Writes events files. Keeps the detection model loaded between videos."""

    def __init__(self):
        self.detector = None

    def make_events_file(self, video, output_folder, overwrite, on_progress=None, profile=BUILT_IN):
        """Detect the events and write the events file. Returns (ok, message).

        The detection runs with the profile's values in force.
        """
        events_path = events_path_for(video, output_folder)
        # Check first: detection takes minutes, and an existing file (perhaps
        # corrected by hand) must not be replaced anyway.
        if events_path.exists() and not overwrite:
            return True, "events file already exists, skipped"
        if not Path(video).is_file():
            return False, f"Video file not found: {video}"
        try:
            # Imported here so that the GPS part also works on a PC where the
            # detection libraries are not installed.
            from pp_tt_video.detect_cars import CarDetector
            from pp_tt_video.detect_events import detect_timeline

            if self.detector is None:
                self.detector = CarDetector()   # loading the model takes a few seconds
            # Inside this block the rules see the profile's values; after
            # it, the built-in values are back for the next video.
            with using_profile(profile):
                timeline = detect_timeline(video, self.detector, on_progress)
            write_events_file(events_path, timeline, known_labels(), overwrite=overwrite)
            return True, f"events written to {events_path.name}"
        except ImportError as error:
            return False, f"detection libraries are not installed ({error})"
        except (VideoError, EventsFileError) as error:
            return False, str(error)


def process_video(video, overwrite=False, output_folder=None, events_maker=None,
                  with_events=True, on_progress=None, profile_option=None):
    """Process one video and return a FileResult. Never raises an error.

    profile_option: what was given with --profile, or None.
    """
    started = time.monotonic()
    ok, message = make_gps_file(video, output_folder, overwrite)
    if with_events:
        try:
            profile = profile_for_video(video, profile_option)
        except ProfileError as error:
            # A broken profile stops the events of this video only. The GPX
            # file is written anyway, and the run goes on with the next video.
            return FileResult(Path(video), False, f"{message}; {error}", time.monotonic() - started)
        message = f"{message}; profile: {profile.description}"
        events_maker = events_maker or EventsMaker()
        events_ok, events_message = events_maker.make_events_file(
            video, output_folder, overwrite, on_progress, profile)
        ok = ok and events_ok
        message = f"{message}; {events_message}"
    return FileResult(Path(video), ok, message, time.monotonic() - started)


def process_videos(inputs, overwrite=False, output_folder=None, with_events=True,
                   on_start=None, on_progress=None, on_done=None, profile_option=None):
    """Process every video and return one FileResult per video.

    Each video is handled on its own: a failure is recorded and the run
    continues with the next video.

    output_folder: where to write the files. By default next to each video.
    with_events:   set to False to extract only the GPS tracks.
    profile_option: a profile name or .toml file for every video (--profile);
                    None to use each folder's profile.toml, if it has one.

    To follow the progress, the caller can pass three functions:
      on_start(number, total, video)     before a video is processed,
      on_progress(number, total, part)   during detection; part runs from 0 to 1,
      on_done(number, total, result)     as soon as a video is finished.
    """
    videos = find_videos(inputs)
    total = len(videos)
    events_maker = EventsMaker()
    results = []
    # enumerate numbers the videos: 1, 2, 3, ...
    for number, video in enumerate(videos, start=1):
        if on_start:
            on_start(number, total, video)

        def report(part, number=number):
            if on_progress:
                on_progress(number, total, part)

        result = process_video(video, overwrite, output_folder, events_maker, with_events, report, profile_option)
        results.append(result)
        if on_done:
            on_done(number, total, result)
    return results
