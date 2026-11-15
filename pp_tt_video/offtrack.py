"""Step 7, part 2: find the moments when the car leaves the track.

Grass and gravel are far rougher than tarmac. With wheels off the track the
whole car is thrown up and down, harder than on any kerb, and for longer.

The rule measures how much the up-and-down force jumps around within a
fifth of a second (the "shake") and reports "offtrack" where the shake stays
high for over a second.

Only slow shaking counts. A camera on its mount can vibrate very fast (about
87 times per second was measured), which jumps around just as much as rough
ground does. So the measurements are smoothed first: each one is averaged
with the few that follow it. A fast vibration goes up and down within those
few measurements and cancels out; the slower bumps of rough ground stay.

A wheel on the grass for a moment shakes the car no more than a kerb does,
and is not reported: a false alarm is worse than a missed event.
"""

from statistics import pstdev

from pp_tt_video import settings
from pp_tt_video.sensors import pieces_of_seconds
from pp_tt_video.stretch import Stretch


def smoothed(values, count):
    """Return the average of every `count` neighbouring values.

    [1, 2, 3, 4] smoothed over 2 is [1.5, 2.5, 3.5]: one value fewer for
    every extra neighbour. With a count of 1 or less, or with fewer values
    than the count, the values come back unchanged.
    """
    if count <= 1 or len(values) < count:
        return values
    return [sum(values[position:position + count]) / count for position in range(len(values) - count + 1)]


def shake_over_time(sensor_seconds, smoothing=None):
    """Return a list of (time, shake), several per second.

    The shake is the standard deviation of the smoothed up-and-down force: a
    number that says how far the values lie from their own average.

    smoothing: over how many measurements to smooth. Not given: the setting
    the rule uses. 1 gives the shake without smoothing, which the check
    video shows for information.

    Each piece is smoothed on its own, never across two pieces. A piece
    with too few measurements to smooth counts as calm (shake 0): without
    smoothing, normal driving would lie above the rule's threshold.
    """
    if smoothing is None:
        smoothing = settings.OFFTRACK_SMOOTHING_MEASUREMENTS
    axis = settings.ACCELERATION_AXIS_DOWN
    samples = []
    for time, acceleration, _ in pieces_of_seconds(sensor_seconds, settings.OFFTRACK_SAMPLES_PER_SECOND):
        down = [measurement[axis] for measurement in acceleration]
        if smoothing > 1 and len(down) < smoothing:
            shake = 0.0
        else:
            shake = pstdev(smoothed(down, smoothing))
        samples.append((time, shake))
    return samples


def offtrack_stretches(samples):
    """Return an "offtrack" stretch for every lasting, high shake."""
    step = 1 / settings.OFFTRACK_SAMPLES_PER_SECOND
    # The length is counted in pieces, not worked out from the times: times
    # like 100.6 cannot be stored exactly, and the same six pieces would pass
    # or fail depending on where in the second they start.
    pieces_needed = round(settings.OFFTRACK_MIN_SECONDS * settings.OFFTRACK_SAMPLES_PER_SECOND)
    stretches = []
    run = []   # the times of the pieces of the run of high shake we are in

    def close_run():
        if len(run) >= max(1, pieces_needed):
            # A run counts from the start of its first piece to the end of its last.
            start = max(0.0, run[0] - settings.OFFTRACK_LEAD_SECONDS)
            end = run[-1] + step + settings.OFFTRACK_TAIL_SECONDS
            stretches.append(Stretch(start, end, settings.OFFTRACK_LABEL))
        run.clear()

    for time, shake in samples:
        if shake >= settings.OFFTRACK_MIN_SHAKE:
            run.append(time)
        else:
            close_run()
    close_run()
    return stretches


def detect_offtrack(sensor_seconds):
    """Return the "offtrack" stretches of one video."""
    return offtrack_stretches(shake_over_time(sensor_seconds))
