"""Detects the events in one video and returns them as a timeline.

This file connects the parts: it reads the reduced pictures, has the cars
found and followed, lets the rules decide, and builds the timeline.

Detected so far:
    from the pictures:       overtaking, overtaken and held up;
    from the motion sensors: warm up and cooling.
"""

from pp_tt_video import settings
from pp_tt_video.car_events import events_of_tracks
from pp_tt_video.detect_cars import CarDetector
from pp_tt_video.event_types import load_event_types
from pp_tt_video.pace import detect_pace, outside_pace
from pp_tt_video.sensors import SensorError, read_sensors
from pp_tt_video.timeline import build_timeline
from pp_tt_video.tracking import Tracker
from pp_tt_video.video import analysis_size, read_frames, read_video_info


def track_cars(video_path, detector, on_progress=None):
    """Find and follow the other cars through a whole video.

    Returns the tracks and the height of the analysed pictures.
    on_progress(part), if given, is called with the part done so far (0 to 1).
    """
    info = read_video_info(video_path)
    picture_height = analysis_size(info)[1]
    tracker = Tracker()

    batch = []

    def handle_batch():
        # The model looks at several pictures at once, which is faster.
        for frame, boxes in zip(batch, detector.detect(batch)):
            tracker.add_picture(frame.time_seconds, boxes)
        if on_progress and info.duration_seconds:
            on_progress(min(1.0, batch[-1].time_seconds / info.duration_seconds))
        batch.clear()

    for frame in read_frames(video_path):
        batch.append(frame)
        if len(batch) == settings.DETECTION_BATCH_SIZE:
            handle_batch()
    if batch:
        handle_batch()

    return tracker.finish(), picture_height


def find_pace(video_path, duration_seconds):
    """Return the "warm up" and "cooling" stretches of one video.

    A video without usable sensor data gets none: the rest of the detection
    still works, as it did before this step existed.
    """
    try:
        return detect_pace(read_sensors(video_path), duration_seconds)
    except SensorError:
        return []


def combine_stretches(car_stretches, pace_parts):
    """Put the stretches of all detectors together.

    Car events are dropped during warm up and cooling. In the paddock and
    the pit lane the car rules see parked cars as "overtaking" and passing
    cars as "overtaken"; none of that is an event on the track.
    """
    kept = [stretch for stretch in car_stretches if not outside_pace(stretch, pace_parts)]
    return sorted(pace_parts + kept, key=lambda stretch: stretch.start)


def detect_timeline(video_path, detector=None, on_progress=None):
    """Detect the events of one video and return the timeline for its events file."""
    detector = detector or CarDetector()
    info = read_video_info(video_path)
    # The sensors are read first: it takes seconds, the pictures take minutes.
    pace_parts = find_pace(video_path, info.duration_seconds)
    tracks, picture_height = track_cars(video_path, detector, on_progress)
    car_stretches = events_of_tracks(tracks, picture_height)
    stretches = combine_stretches(car_stretches, pace_parts)
    return build_timeline(stretches, info.duration_seconds, list(load_event_types()))
