"""Detects the events in one video and returns them as a timeline.

This file connects the parts: it reads the reduced pictures, has the cars
found and followed, lets the rules decide, and builds the timeline.

Detected so far:
    from the pictures:       overtaking, overtaken and held up (cars),
                             obstacle (knocked-over cones);
    from the motion sensors: out of session, warm up, cooling, crash,
                             sliding and offtrack.
"""

from pp_tt_video import settings
from pp_tt_video.car_events import events_of_tracks
from pp_tt_video.detect_cars import CarDetector, keep_car_boxes
from pp_tt_video.detections_file import Detections
from pp_tt_video.event_types import load_event_types
from pp_tt_video.object_events import events_of_objects
from pp_tt_video.offtrack import detect_offtrack
from pp_tt_video.pace import outside_pace
from pp_tt_video.sensors import SensorError, read_sensors
from pp_tt_video.session import detect_session
from pp_tt_video.sliding import detect_sliding
from pp_tt_video.timeline import build_timeline
from pp_tt_video.tracking import Tracker
from pp_tt_video.video import analysis_size, read_frames, read_video_info


def detect_boxes(video_path, detector, on_progress=None):
    """The slow part: have the model look at every reduced picture of a video.

    Returns the Detections: the raw vehicle boxes of every analysed picture,
    with nothing thrown away yet. They can be saved (detections_file.py) and
    used again without looking at the video a second time.
    on_progress(part), if given, is called with the part done so far (0 to 1).
    """
    info = read_video_info(video_path)
    width, height = analysis_size(info)
    pictures = []

    batch = []

    def handle_batch():
        # The model looks at several pictures at once, which is faster.
        for frame, boxes in zip(batch, detector.detect_raw(batch)):
            pictures.append((frame.time_seconds, boxes))
        if on_progress and info.duration_seconds:
            on_progress(min(1.0, batch[-1].time_seconds / info.duration_seconds))
        batch.clear()

    for frame in read_frames(video_path):
        batch.append(frame)
        if len(batch) == settings.DETECTION_BATCH_SIZE:
            handle_batch()
    if batch:
        handle_batch()

    return Detections(
        analysis_width=width,
        picture_height=height,
        frames_per_second=settings.ANALYSIS_FRAMES_PER_SECOND,
        min_confidence=settings.MIN_DETECTION_CONFIDENCE,
        pictures=pictures,
    )


def tracks_from_detections(detections):
    """The quick part: follow the cars through the detections of a video.

    Returns the tracks and the height of the analysed pictures.
    """
    tracker = Tracker()
    for time_seconds, boxes in detections.pictures:
        # Boxes that cannot be another car (the own cockpit) go first.
        tracker.add_picture(time_seconds, keep_car_boxes(boxes, detections.analysis_width))
    return tracker.finish(), detections.picture_height


def track_cars(video_path, detector, on_progress=None):
    """Find and follow the other cars through a whole video.

    Returns the tracks and the height of the analysed pictures.
    """
    return tracks_from_detections(detect_boxes(video_path, detector, on_progress))


def sensor_stretches(sensor_seconds, duration_seconds):
    """Detect everything that is found from the motion sensors.

    Returns two lists of stretches: the large parts of the video ("out of
    session", "warm up", "cooling", "crash") and the events ("sliding",
    "offtrack").
    """
    pace_parts = detect_session(sensor_seconds, duration_seconds)
    events = detect_sliding(sensor_seconds) + detect_offtrack(sensor_seconds)
    return pace_parts, events


def detect_from_sensors(video_path, duration_seconds):
    """Read the motion sensors of a video and detect what is found from them.

    A video without usable sensor data gets nothing: the rest of the
    detection still works without them.
    """
    try:
        sensor_seconds = read_sensors(video_path)
    except SensorError:
        return [], []
    return sensor_stretches(sensor_seconds, duration_seconds)


def combine_stretches(event_stretches, pace_parts):
    """Put the stretches of all detectors together.

    Events are only kept in the part at pace. In the paddock and the
    pit lane the car rules see parked cars as "overtaking" and passing cars
    as "overtaken", and rough ground shakes the car like grass beside the
    track does; none of that is an event on the track.
    """
    kept = [stretch for stretch in event_stretches if not outside_pace(stretch, pace_parts)]
    return sorted(pace_parts + kept, key=lambda stretch: stretch.start)


def timeline_from_detections(video_path, detections, objects=None):
    """Let the rules decide, and return the timeline for the events file.

    This is everything after the slow parts: it takes seconds. The video is
    only opened for its length and its motion sensor data.
    objects: the objects found in the video (find_objects.py), or None.
    """
    info = read_video_info(video_path)
    pace_parts, sensor_events = detect_from_sensors(video_path, info.duration_seconds)
    tracks, picture_height = tracks_from_detections(detections)
    car_stretches = events_of_tracks(tracks, picture_height)
    object_stretches = events_of_objects(objects)
    stretches = combine_stretches(car_stretches + sensor_events + object_stretches, pace_parts)
    return build_timeline(stretches, info.duration_seconds, list(load_event_types()))


def detect_timeline(video_path, detector=None, on_progress=None):
    """Detect the events of one video and return the timeline for its events file."""
    detector = detector or CarDetector()
    return timeline_from_detections(video_path, detect_boxes(video_path, detector, on_progress))
