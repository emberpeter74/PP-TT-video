"""Step 7, part 2: find the moments when the car leaves the track.

Grass and gravel are far rougher than tarmac. With wheels off the track the
whole car shakes up and down, much harder than on any kerb, and for longer.

The rule measures how much the up-and-down force jumps around within a
fifth of a second (the "shake") and reports "offtrack" where the shake stays
very high for a second or more.

This finds the clear cases. Two wheels on the grass for a moment shake the
car no more than a kerb does, and are not reported: a false alarm is worse
than a missed event.
"""

from statistics import pstdev

from pp_tt_video import settings
from pp_tt_video.sensors import pieces_of_seconds
from pp_tt_video.stretch import Stretch


def shake_over_time(sensor_seconds, axis=None):
    """Return a list of (time, shake), several per second.

    The shake is the standard deviation of the up-and-down force: a number
    that says how far the measurements lie from their own average.

    axis: the rule looks up and down, which is what is measured when no axis
    is given. The check video also shows the shake along the other two axes.
    """
    if axis is None:
        axis = settings.ACCELERATION_AXIS_DOWN
    samples = []
    for time, acceleration, _ in pieces_of_seconds(sensor_seconds, settings.OFFTRACK_SAMPLES_PER_SECOND):
        samples.append((time, pstdev([measurement[axis] for measurement in acceleration])))
    return samples


def offtrack_stretches(samples):
    """Return an "offtrack" stretch for every lasting, very high shake."""
    step = 1 / settings.OFFTRACK_SAMPLES_PER_SECOND
    stretches = []
    first = last = None

    def close_run():
        # A run counts from the start of its first piece to the end of its last.
        if first is not None and last + step - first >= settings.OFFTRACK_MIN_SECONDS:
            start = max(0.0, first - settings.OFFTRACK_LEAD_SECONDS)
            end = last + step + settings.OFFTRACK_TAIL_SECONDS
            stretches.append(Stretch(start, end, settings.OFFTRACK_LABEL))

    for time, shake in samples:
        if shake >= settings.OFFTRACK_MIN_SHAKE:
            if first is None:
                first = time
            last = time
        else:
            close_run()
            first = last = None
    close_run()
    return stretches


def detect_offtrack(sensor_seconds):
    """Return the "offtrack" stretches of one video."""
    return offtrack_stretches(shake_over_time(sensor_seconds))
