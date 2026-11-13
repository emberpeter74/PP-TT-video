"""Divides a video into its large parts, in this order:

    out of session   before the car joins the track (paddock, pit lane)
    warm up          on the track, not yet at pace
    (at pace)        where the events are looked for; no stretch is made
    cooling          on the track, no longer at pace
    out of session   after the car has left the track

A part that does not occur is left out: a video may start on the track, or
end before the car leaves it.

If the car stands still soon after it stopped driving at pace, there was no
cool-down lap. Everything after the pace part is then "crash".

The part at pace is found in pace.py. This file finds the rest.
"""

from statistics import pstdev

from pp_tt_video import settings
from pp_tt_video.pace import average, find_pace_part, forward_force_per_second
from pp_tt_video.stretch import Stretch


def value_per_second(sensor_seconds, measurements_of, axis):
    """Average one axis of the measurements of every second."""
    return [
        average([measurement[axis] for measurement in measurements_of(second)])
        for second in sensor_seconds
    ]


def speed_at_start(sensor_seconds):
    """Return the first speed (km/h) known at the start of the video, or None.

    The GPS speed is used when the camera has a fix. Without it, the speed
    can still be worked out in a turn: the cornering force of a turn is the
    speed times the turning rate, so the speed is the force divided by the
    turning rate.
    """
    for second in sensor_seconds[:settings.SESSION_START_LOOK_SECONDS]:
        if second.gps_speeds:
            return average(second.gps_speeds)
        force = average([m[settings.ACCELERATION_AXIS_SIDEWAYS] for m in second.acceleration])
        turning = average([m[settings.ROTATION_AXIS_TURNING] for m in second.rotation])
        if abs(turning) >= settings.SESSION_MIN_TURNING_FOR_SPEED:
            return abs(force / turning) * 3.6   # from metres per second to km/h
    return None


def seconds_before_joining(sensor_seconds):
    """Return how many seconds at the start of the video are before the track.

    0 when the video starts on the track, or when that cannot be told.
    """
    speed = speed_at_start(sensor_seconds)
    if speed is None or speed >= settings.SESSION_SLOW_SPEED:
        return 0   # no sign that the car is anywhere but on the track
    # Leaving the pit lane, the car accelerates onto the track. The session
    # starts when that first acceleration is over. (Minus is accelerating.)
    forward = value_per_second(sensor_seconds, lambda s: s.acceleration, settings.ACCELERATION_AXIS_FORWARD)
    accelerating = False
    for position, force in enumerate(forward):
        if -force >= settings.SESSION_JOIN_FORCE:
            accelerating = True
        elif accelerating and -force < settings.SESSION_JOIN_END_FORCE:
            return position
        elif force >= settings.SESSION_JOIN_FORCE:
            # Braking this hard is not done in a pit lane: the car is on
            # the track already, and the moment it joined was not seen.
            return 0
    return 0


def start_of_final_standstill(sensor_seconds):
    """Return the second from which the car stands still until the end.

    None when the video ends with the car still moving.
    """
    axis = settings.ACCELERATION_AXIS_DOWN
    position = len(sensor_seconds)
    while position > 0:
        shake = pstdev([m[axis] for m in sensor_seconds[position - 1].acceleration])
        if shake > settings.STANDSTILL_MAX_SHAKE:
            break
        position -= 1
    if len(sensor_seconds) - position < settings.STANDSTILL_MIN_SECONDS:
        return None
    return position


def second_of_leaving(sensor_seconds, standstill):
    """Return the second from which the car has left the track.

    The car is taken to be on the track up to its last real corner before
    it parks, plus a few seconds for the way into the pit lane.
    """
    sideways = value_per_second(sensor_seconds, lambda s: s.acceleration, settings.ACCELERATION_AXIS_SIDEWAYS)
    last_corner = standstill
    while last_corner > 0 and abs(sideways[last_corner - 1]) < settings.SESSION_TRACK_CORNER_FORCE:
        last_corner -= 1
    # last_corner is now the first second after the last corner.
    return min(standstill, last_corner + settings.SESSION_LEAVE_SECONDS)


def find_session_parts(sensor_seconds):
    """Return the large parts of a video as a list of (first, last, label).

    first and last are positions in the list of sensor seconds; last is
    included. The part at pace is not in the list.
    """
    end = len(sensor_seconds) - 1
    pace_part = find_pace_part(forward_force_per_second(sensor_seconds))
    parts = []

    # --- Before the pace part ---------------------------------------------------
    joined = seconds_before_joining(sensor_seconds)
    pace_first = pace_part[0] if pace_part else end + 1
    if pace_part and joined > pace_first:
        # The car goes to pace straight out of the pit lane. The pace part
        # starts where the car has joined the track.
        pace_first = joined
    if joined > 0:
        parts.append((0, joined - 1, settings.OUT_OF_SESSION_LABEL))
    if pace_first > joined:
        # Never at pace: the car has not got beyond warming up.
        parts.append((joined, pace_first - 1, settings.WARM_UP_LABEL))
    if pace_part is None or pace_part[1] == end:
        return parts

    # --- After the pace part ----------------------------------------------------
    after_pace = pace_part[1] + 1
    standstill = start_of_final_standstill(sensor_seconds)
    if standstill is None:
        # The video ends with the car still driving.
        parts.append((after_pace, end, settings.COOLING_LABEL))
    elif standstill - after_pace < settings.CRASH_MAX_SECONDS:
        parts.append((after_pace, end, settings.CRASH_LABEL))
    else:
        left = max(after_pace, second_of_leaving(sensor_seconds, standstill))
        if left > after_pace:
            parts.append((after_pace, left - 1, settings.COOLING_LABEL))
        parts.append((left, end, settings.OUT_OF_SESSION_LABEL))
    return parts


def detect_session(sensor_seconds, duration_seconds):
    """Return the stretches for the large parts of one video.

    Returns an empty list when there is no sensor data to judge from.
    """
    if not sensor_seconds:
        return []
    parts = find_session_parts(sensor_seconds)
    stretches = []
    for first, last, label in parts:
        start = sensor_seconds[first].start_seconds
        if last == len(sensor_seconds) - 1:
            end = duration_seconds   # the last part runs to the very end
        else:
            # A stretch includes its last second, so it ends one second
            # before the next part starts.
            end = sensor_seconds[last + 1].start_seconds - 1
        stretches.append(Stretch(start, end, label))
    return stretches
