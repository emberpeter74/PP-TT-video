"""Collects what the rules did with one video: what was kept, what was
thrown away, and why.

The events file only shows the final answer. The check video needs the
steps in between: which boxes the model found, which of them were thrown
away, which car is which, and which events were found but dropped.

Nothing is decided here. This file runs the same functions the detection
runs (the tracker, the car rules, the sensor rules) and writes down what
they did. So the check video always shows what the rules really use, with
the values of the profile that is in force.
"""

from bisect import bisect_right
from dataclasses import dataclass, field

from pp_tt_video import settings
from pp_tt_video.car_events import events_of_tracks, smooth
from pp_tt_video.charts import CHARTS
from pp_tt_video.detect_cars import keep_car_boxes
from pp_tt_video.detect_events import combine_stretches, sensor_stretches
from pp_tt_video.event_types import load_event_types
from pp_tt_video.object_events import events_of_objects, is_lying_cone
from pp_tt_video.pace import outside_pace
from pp_tt_video.timeline import build_timeline
from pp_tt_video.tracking import Tracker, drop_double_boxes

# Why a box was thrown away.
TOO_WIDE = "too wide"                 # the own cockpit, not a car
DOUBLE = "double"                     # a second box around the same car
NEVER_SURE = "never sure enough"      # the model was never sure this is a car

# Why an event was thrown away.
OUTSIDE_PACE = "outside the part at pace"


@dataclass
class ShownBox:
    """One box of one analysed picture, with what the rules made of it."""

    box: object          # the CarBox the model found
    track_number: int    # which car it is (1, 2, ...); None if it belongs to none
    height_part: float   # its height as a part of the picture, as the car rule sees it
    state: str           # "far", "close" or "passing"
    reason: str          # "" for a kept box, else why it was thrown away


@dataclass
class PictureBoxes:
    """The boxes of one analysed picture."""

    time_seconds: float
    kept: list      # ShownBox: the cars the rules work with
    dropped: list   # ShownBox: what was thrown away


@dataclass
class DroppedStretch:
    """An event that was found and then thrown away."""

    stretch: object   # the Stretch
    reason: str


@dataclass
class Explanation:
    """Everything the check video shows about one video."""

    pictures: list            # PictureBoxes, one per analysed picture, in order of time
    picture_times: list       # the time of each of those pictures, for looking one up quickly
    frames_per_second: float  # how many pictures per second were analysed
    tracks: list              # the cars that were followed
    timeline: list            # the Events, as they go into the events file
    kept_stretches: list      # the event Stretches that made it into the timeline
    dropped_stretches: list   # DroppedStretch
    session_parts: list       # Stretches: out of session, warm up, cooling, crash
    duration_seconds: float
    sensor_seconds: list      # the motion sensor data; empty if the video has none
    charts: dict              # name -> Chart for the sensor strip; empty without sensor data
    # The objects found (cones): one (time, [(ObjectBox, is_obstacle), ...])
    # per searched picture. is_obstacle is True for a box the rule took for
    # a knocked-over cone. All empty when the video has no objects file.
    object_pictures: list = field(default_factory=list)
    object_times: list = field(default_factory=list)   # the time of each, for looking one up quickly
    object_frames_per_second: float = 0                # how many pictures per second were searched


def state_of(height_part):
    """How the car rules see a car of this height: far, close or passing."""
    if height_part >= settings.PASSING_CAR_HEIGHT:
        return "passing"
    if height_part >= settings.CLOSE_CAR_HEIGHT:
        return "close"
    return "far"


def is_in(box, boxes):
    """True when this very box object is in the list (not just an equal one)."""
    return any(box is other for other in boxes)


def explain(detections, sensor_seconds, duration_seconds, objects=None):
    """Run the rules on the detections and sensor data of a video and return
    the Explanation.

    sensor_seconds: the motion sensor data, or an empty list.
    objects:        the objects found in the video (cones), or None.
    """
    picture_height = detections.picture_height

    # --- Follow the cars, and note which boxes are thrown away on the way ---
    tracker = Tracker()
    thrown_away = []   # per picture: a list of (box, reason)
    for time_seconds, boxes in detections.pictures:
        not_wide = keep_car_boxes(boxes, detections.analysis_width)
        single = drop_double_boxes(not_wide)
        thrown_away.append(
            [(box, TOO_WIDE) for box in boxes if not is_in(box, not_wide)]
            + [(box, DOUBLE) for box in not_wide if not is_in(box, single)]
        )
        # The tracker drops double boxes itself; here that has been done
        # already, so it finds none and follows exactly the same cars.
        tracker.add_picture(time_seconds, single)
    tracks = tracker.finish()

    # --- What the car rules make of every box of every car ------------------
    # id(box) is a number that stands for this very box object.
    shown_by_box = {}
    for number, track in enumerate(tracks, start=1):
        # The car rules smooth the heights before they compare them (one box
        # drawn far too large must not count). The same smoothing is used
        # here, so the picture shows the height the rule decides on.
        heights = smooth([sighting.box.height / picture_height for sighting in track.sightings])
        # A car the model was never sure of is skipped by the car rules.
        reason = NEVER_SURE if track.best_confidence < settings.CAR_MIN_CONFIDENCE else ""
        for sighting, height in zip(track.sightings, heights):
            shown_by_box[id(sighting.box)] = ShownBox(sighting.box, number, height, state_of(height), reason)

    pictures = []
    for (time_seconds, boxes), dropped_here in zip(detections.pictures, thrown_away):
        kept, dropped = [], []
        for box in boxes:
            shown = shown_by_box.get(id(box))
            if shown is None:
                continue   # thrown away before the tracker; handled below
            (dropped if shown.reason else kept).append(shown)
        for box, reason in dropped_here:
            dropped.append(ShownBox(box, None, box.height / picture_height, "far", reason))
        pictures.append(PictureBoxes(time_seconds, kept, dropped))

    # --- The events ----------------------------------------------------------
    car_stretches = events_of_tracks(tracks, picture_height)
    if sensor_seconds:
        session_parts, sensor_events = sensor_stretches(sensor_seconds, duration_seconds)
    else:
        session_parts, sensor_events = [], []
    events = car_stretches + sensor_events + events_of_objects(objects)
    stretches = combine_stretches(events, session_parts)

    # --- The objects, with what the rule made of each ---------------------------
    object_pictures = []
    if objects is not None:
        for time_seconds, boxes in objects.pictures:
            shown = [(box, is_lying_cone(box, boxes, objects.analysis_width)) for box in boxes]
            object_pictures.append((time_seconds, shown))
    dropped_stretches = [
        DroppedStretch(stretch, OUTSIDE_PACE)
        for stretch in sorted(events, key=lambda stretch: stretch.start)
        if outside_pace(stretch, session_parts)
    ]
    kept_stretches = [stretch for stretch in stretches if not is_in(stretch, session_parts)]
    timeline = build_timeline(stretches, duration_seconds, list(load_event_types()))

    return Explanation(
        pictures=pictures,
        picture_times=[picture.time_seconds for picture in pictures],
        frames_per_second=detections.frames_per_second,
        tracks=tracks,
        timeline=timeline,
        kept_stretches=kept_stretches,
        dropped_stretches=dropped_stretches,
        session_parts=session_parts,
        duration_seconds=duration_seconds,
        sensor_seconds=sensor_seconds,
        # Made here, while the profile is in force: the charts take the
        # rules' thresholds from the settings at this moment.
        charts={name: make_chart(sensor_seconds) for name, make_chart in CHARTS.items()} if sensor_seconds else {},
        object_pictures=object_pictures,
        object_times=[time_seconds for time_seconds, _ in object_pictures],
        object_frames_per_second=objects.frames_per_second if objects is not None else 0,
    )


def boxes_at(explanation, time_seconds):
    """Return the boxes to show at a moment of the video, or None.

    Only a few pictures per second are analysed. A moment in between shows
    the boxes of the last analysed picture before it, as long as that one
    is no older than the time between two analysed pictures.
    """
    # bisect_right finds, in a sorted list, how many values are <= the given one.
    position = bisect_right(explanation.picture_times, time_seconds) - 1
    if position < 0:
        return None
    picture = explanation.pictures[position]
    if time_seconds - picture.time_seconds >= 1 / explanation.frames_per_second:
        return None
    return picture


def objects_at(explanation, time_seconds):
    """Return the objects to show at a moment of the video: a list of (ObjectBox, is_obstacle).

    Like boxes_at: a moment between two searched pictures shows the objects
    of the last searched picture before it, as long as that one is no older
    than the time between two searched pictures. Otherwise, and in a video
    without objects, the list is empty.
    """
    position = bisect_right(explanation.object_times, time_seconds) - 1
    if position < 0:
        return []
    time, shown = explanation.object_pictures[position]
    if time_seconds - time >= 1 / explanation.object_frames_per_second:
        return []
    return shown


def labels_at(explanation, time_seconds):
    """Return the labels the events file has for a moment of the video."""
    labels = (settings.CLEAR_LABEL,)
    for event in explanation.timeline:
        if event.start > time_seconds:
            break
        labels = event.labels
    return labels


def dropped_at(explanation, time_seconds):
    """Return the thrown-away events that cover a moment of the video."""
    return [
        dropped for dropped in explanation.dropped_stretches
        if dropped.stretch.start <= time_seconds <= dropped.stretch.end
    ]
