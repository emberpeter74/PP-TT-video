"""Detects the events in one video and returns them as a timeline.

This file connects the parts: it reads the reduced pictures, has the cars
found and followed, lets the rules decide, and builds the timeline.

Detected so far:
    from the pictures:       overtaking, overtaken and held up;
    from the motion sensors: out of session, warm up, cooling, crash,
                             sliding and offtrack.
"""

from pp_tt_video import settings
from pp_tt_video.car_events import events_of_tracks
from pp_tt_video.detect_cars import CarDetector
from pp_tt_video.event_types import load_event_types
from pp_tt_video.offtrack import detect_offtrack
from pp_tt_video.pace import outside_pace
from pp_tt_video.sensors import SensorError, read_sensors
from pp_tt_video.session import detect_session
from pp_tt_video.sliding import detect_sliding
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


def detect_from_sensors(video_path, duration_seconds):
    """Detect everything that is found from the motion sensors.

    Returns two lists of stretches: the large parts of the video ("out of
    session", "warm up", "cooling", "crash") and the events ("sliding",
    "offtrack").

    A video without usable sensor data gets neither: the rest of the
    detection still works without them.
    """
    try:
        sensor_seconds = read_sensors(video_path)
    except SensorError:
        return [], []
    pace_parts = detect_session(sensor_seconds, duration_seconds)
    events = detect_sliding(sensor_seconds) + detect_offtrack(sensor_seconds)
    return pace_parts, events


def combine_stretches(event_stretches, pace_parts):
    """Put the stretches of all detectors together.

    Events are only kept in the part at pace. In the paddock and the
    pit lane the car rules see parked cars as "overtaking" and passing cars
    as "overtaken", and rough ground shakes the car like grass beside the
    track does; none of that is an event on the track.
    """
    kept = [stretch for stretch in event_stretches if not outside_pace(stretch, pace_parts)]
    return sorted(pace_parts + kept, key=lambda stretch: stretch.start)


def detect_timeline(video_path, detector=None, on_progress=None):
    """Detect the events of one video and return the timeline for its events file."""
    detector = detector or CarDetector()
    info = read_video_info(video_path)
    # The sensors are read first: it takes seconds, the pictures take minutes.
    pace_parts, sensor_stretches = detect_from_sensors(video_path, info.duration_seconds)
    tracks, picture_height = track_cars(video_path, detector, on_progress)
    car_stretches = events_of_tracks(tracks, picture_height)
    stretches = combine_stretches(car_stretches + sensor_stretches, pace_parts)
    return build_timeline(stretches, info.duration_seconds, list(load_event_types()))
