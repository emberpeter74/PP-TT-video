"""Processes a set of videos, one after the other.

This is the function the main program will call later. Running the module by
hand (see __main__.py) uses the same function.

Every video gets three files: the GPS track (.gpx), the motion sensor data
(-sensors.csv) and the events file (-events.txt). They are made
independently: if one fails, the others are still written.

The events are detected with the video's driver and car profile, if it has
one (see profile.py): the one given with --profile, or the profile.toml in
the video's folder. Otherwise the built-in values of settings.py are used.
"""

import time
from dataclasses import dataclass
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.detections_file import (
    DetectionsError,
    detections_path_for,
    fits_settings,
    load_detections,
    save_detections,
)
from pp_tt_video.event_types import known_labels
from pp_tt_video.events import EventsFileError, events_path_for, write_events_file
from pp_tt_video.gps import GpsExtractionError, extract_gps, gpx_path_for
from pp_tt_video.profile import BUILT_IN, ProfileError, profile_for_video, using_profile
from pp_tt_video.sensor_file import sensors_path_for, write_sensor_file
from pp_tt_video.sensors import SensorError, read_sensors
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


def make_sensor_file(video, output_folder, overwrite, read=None):
    """Write the motion sensor data to a CSV file. Returns (ok, message).

    read: the function that reads a video's sensor data; read_sensors unless
    a check hands in a stand-in.
    """
    read = read or read_sensors
    path = sensors_path_for(video, output_folder)
    # Check first: reading the sensors takes about 5 seconds.
    if path.exists() and not overwrite:
        return True, "sensor file already exists, skipped"
    try:
        sensor_seconds = read(video)
    except SensorError as error:
        return False, str(error)
    if not sensor_seconds:
        # Not a GoPro file, or recorded without sensor data: nothing to write.
        return True, "no motion sensor data in this video"
    write_sensor_file(path, sensor_seconds)
    return True, f"sensor data written to {path.name}"


class EventsMaker:
    """Writes events files. Keeps the detection model loaded between videos."""

    def __init__(self):
        self.detector = None
        # The detections of the video worked on last, as (video, detections),
        # so the steps of one video share one pass over its pictures.
        self.last_detections = None

    def detections_for(self, video, output_folder, overwrite, on_progress=None, keep_file=False):
        """Return the car detections of a video: the slow part of the work.

        keep_file: with --check-video the detections are kept in a file. A
        file from an earlier run is used again instead of looking at the
        video once more, unless overwrite is set or the file does not fit
        (half-written, or made with other analysis settings).
        May raise ImportError or VideoError.
        """
        # Imported here so that the GPS part also works on a PC where the
        # detection libraries are not installed.
        from pp_tt_video import detect_events
        from pp_tt_video.detect_cars import CarDetector

        video = Path(video)
        if self.last_detections and self.last_detections[0] == video:
            return self.last_detections[1]

        path = detections_path_for(video, output_folder)
        detections = None
        if keep_file and path.exists() and not overwrite:
            try:
                saved = load_detections(path)
                if fits_settings(saved):
                    detections = saved
            except DetectionsError:
                pass   # not usable: detect again and replace it
        if detections is None:
            if self.detector is None:
                self.detector = CarDetector()   # loading the model takes a few seconds
            detections = detect_events.detect_boxes(video, self.detector, on_progress)
            if keep_file:
                save_detections(path, detections)
        self.last_detections = (video, detections)
        return detections

    def make_events_file(self, video, output_folder, overwrite, on_progress=None, profile=BUILT_IN,
                         keep_detections=False):
        """Detect the events and write the events file. Returns (ok, message).

        The rules run with the profile's values in force.
        """
        events_path = events_path_for(video, output_folder)
        # Check first: detection takes minutes, and an existing file (perhaps
        # corrected by hand) must not be replaced anyway.
        if events_path.exists() and not overwrite:
            return True, "events file already exists, skipped"
        if not Path(video).is_file():
            return False, f"Video file not found: {video}"
        try:
            from pp_tt_video import detect_events

            detections = self.detections_for(video, output_folder, overwrite, on_progress, keep_detections)
            # Inside this block the rules see the profile's values; after
            # it, the built-in values are back for the next video.
            with using_profile(profile):
                timeline = detect_events.timeline_from_detections(video, detections)
            write_events_file(events_path, timeline, known_labels(), overwrite=overwrite)
            return True, f"events written to {events_path.name}"
        except ImportError as error:
            return False, f"detection libraries are not installed ({error})"
        except (VideoError, EventsFileError) as error:
            return False, str(error)

    def keep_detections_file(self, video, output_folder, overwrite, on_progress=None):
        """Make sure the detections of a video are saved. Returns (ok, message).

        Needed when the events file already existed and was skipped: then no
        detection has run in this run, and the check video still needs one.
        """
        if not Path(video).is_file():
            return False, f"Video file not found: {video}"
        try:
            self.detections_for(video, output_folder, overwrite, on_progress, keep_file=True)
            return True, f"detections in {detections_path_for(video, output_folder).name}"
        except ImportError as error:
            return False, f"detection libraries are not installed ({error})"
        except VideoError as error:
            return False, str(error)


def process_video(video, overwrite=False, output_folder=None, events_maker=None,
                  with_events=True, on_progress=None, profile_option=None, check_video=False):
    """Process one video and return a FileResult. Never raises an error.

    profile_option: what was given with --profile, or None.
    check_video:    True with --check-video: keep what the check video needs.
    """
    started = time.monotonic()
    ok, message = make_gps_file(video, output_folder, overwrite)
    # The sensor file is made for every video, also with --gps-only.
    sensors_ok, sensors_message = make_sensor_file(video, output_folder, overwrite)
    ok = ok and sensors_ok
    message = f"{message}; {sensors_message}"
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
            video, output_folder, overwrite, on_progress, profile, keep_detections=check_video)
        ok = ok and events_ok
        message = f"{message}; {events_message}"
        if check_video:
            kept_ok, kept_message = events_maker.keep_detections_file(video, output_folder, overwrite, on_progress)
            ok = ok and kept_ok
            message = f"{message}; {kept_message}"
    return FileResult(Path(video), ok, message, time.monotonic() - started)


def process_videos(inputs, overwrite=False, output_folder=None, with_events=True,
                   on_start=None, on_progress=None, on_done=None, profile_option=None,
                   check_video=False):
    """Process every video and return one FileResult per video.

    Each video is handled on its own: a failure is recorded and the run
    continues with the next video.

    output_folder: where to write the files. By default next to each video.
    with_events:   set to False to extract only the GPS tracks.
    profile_option: a profile name or .toml file for every video (--profile);
                    None to use each folder's profile.toml, if it has one.
    check_video:   set to True to also keep the car detections of every
                   video in a file (-detections.json), for the check video.

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

        result = process_video(video, overwrite, output_folder, events_maker, with_events, report,
                               profile_option, check_video)
        results.append(result)
        if on_done:
            on_done(number, total, result)
    return results
