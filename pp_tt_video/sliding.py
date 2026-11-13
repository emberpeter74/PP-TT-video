"""Step 7, part 1: find the moments when the car slides.

In a normal corner two things go together: the car is pushed sideways (the
cornering force) and it turns. More force, more turning, both in the same
direction.

In a slide the rear of the car steps out and the driver catches it by
steering the other way. For a moment the car is still pushed sideways as
hard as before, but it has stopped turning into the corner, or even turns
the other way. That moment, the catch, is what this rule looks for:

    the cornering force is high,
    the car turned briskly into the corner a moment ago,
    and now it turns against the corner.

A kerb or a quick change of direction does not look like this: there the
force and the turning change together.

The rule only finds slides that are caught with a quick steering
correction. A car that slowly pushes wide over its front wheels shows no
such moment and is not found.
"""

from pp_tt_video import settings
from pp_tt_video.sensors import pieces_of_seconds
from pp_tt_video.stretch import Stretch


def average(values):
    return sum(values) / len(values)


def cornering_and_turning(sensor_seconds):
    """Return a list of (time, cornering force, turning rate), several per second."""
    force_axis = settings.ACCELERATION_AXIS_SIDEWAYS
    turn_axis = settings.ROTATION_AXIS_TURNING
    samples = []
    for time, acceleration, rotation in pieces_of_seconds(sensor_seconds, settings.SLIDE_SAMPLES_PER_SECOND):
        force = average([measurement[force_axis] for measurement in acceleration])
        turning = average([measurement[turn_axis] for measurement in rotation])
        samples.append((time, force, turning))
    return samples


def find_catch_times(samples):
    """Return the times at which the car turns against the corner it is in."""
    times = []
    for position, (time, force, turning) in enumerate(samples):
        if abs(force) < settings.SLIDE_MIN_CORNERING_FORCE:
            continue   # not cornering hard: nothing to slide from
        # +1 or -1: the direction of the corner.
        direction = 1 if force > 0 else -1
        if turning * direction >= 0:
            continue   # turning into the corner, as it should
        # Did the car turn briskly into this corner a moment ago?
        for earlier_time, _, earlier_turning in reversed(samples[:position]):
            if time - earlier_time > settings.SLIDE_LOOK_BACK_SECONDS:
                break
            if earlier_turning * direction >= settings.SLIDE_MIN_TURNING_BEFORE:
                times.append(time)
                break
    return times


def group_times(times, max_gap):
    """Group times that follow each other closely. Returns (first, last, count) per group."""
    groups = []
    for time in times:
        if groups and time - groups[-1][1] <= max_gap:
            first, _, count = groups[-1]
            groups[-1] = (first, time, count + 1)
        else:
            groups.append((time, time, 1))
    return groups


def slide_stretches(samples):
    """Return a "sliding" stretch for every catch found in the samples."""
    stretches = []
    for first, last, count in group_times(find_catch_times(samples), settings.SLIDE_GROUP_GAP_SECONDS):
        if count < settings.SLIDE_MIN_SAMPLES:
            continue   # a single odd measurement is not a slide
        # The catch is the end of a slide: the slide began a little earlier
        # and the car needs a moment to settle afterwards.
        start = max(0.0, first - settings.SLIDE_LEAD_SECONDS)
        stretches.append(Stretch(start, last + settings.SLIDE_TAIL_SECONDS, settings.SLIDING_LABEL))
    return stretches


def detect_sliding(sensor_seconds):
    """Return the "sliding" stretches of one video."""
    return slide_stretches(cornering_and_turning(sensor_seconds))
