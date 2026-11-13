"""Detects the events in one video and returns them as a timeline.

This file connects the parts: it reads the reduced pictures, has the cars
found and followed, lets the rules decide, and builds the timeline.

So far only the events that involve other cars are detected:
overtaking, overtaken and held up.
"""

from pp_tt_video import settings
from pp_tt_video.car_events import events_of_tracks
from pp_tt_video.detect_cars import CarDetector
from pp_tt_video.event_types import load_event_types
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


def detect_timeline(video_path, detector=None, on_progress=None):
    """Detect the events of one video and return the timeline for its events file."""
    detector = detector or CarDetector()
    info = read_video_info(video_path)
    tracks, picture_height = track_cars(video_path, detector, on_progress)
    stretches = events_of_tracks(tracks, picture_height)
    return build_timeline(stretches, info.duration_seconds, list(load_event_types()))
