"""The charts of the sensor strip: what each sensor rule looks at.

Every chart holds the values a rule decides on, over the whole video, and
the rule's own thresholds. Nothing is worked out here: the values come from
the functions the rules use themselves, and the thresholds from settings.py
at the moment the chart is made. So a chart made while a profile is in
force shows the profile's thresholds.
"""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from pp_tt_video import settings
from pp_tt_video.offtrack import shake_over_time
from pp_tt_video.pace import effort_per_second, forward_force_per_second
from pp_tt_video.sliding import cornering_and_turning, find_catch_times


@dataclass
class Line:
    """One line of a chart: a value over time."""

    name: str
    times: list       # seconds since the beginning of the video, in order
    values: list
    from_rule: bool   # False: shown for information only, no rule decides on it


@dataclass
class Chart:
    """One row of the sensor strip."""

    title: str
    lines: list        # Line
    thresholds: list   # (label, value): the rule's thresholds, drawn as level lines
    marks: list        # times at which the rule noticed something
    low: float = 0.0   # the value at the bottom edge of the row
    high: float = 1.0  # the value at the top edge of the row


def percentile(values, percent):
    """The value that the given percent of the values do not exceed."""
    ordered = sorted(values)
    return ordered[round(percent / 100 * (len(ordered) - 1))]


def with_scale(chart):
    """Set the scale of a chart: which values lie at its bottom and top edge.

    The scale is the same for the whole video, so a value has the same
    height at every moment. It reaches twice the largest threshold, or the
    level only 0.5% of the values exceed, whichever is more. The very largest
    value is not used: a single jolt would flatten everything else.

    Only the lines a rule decides on set the scale. A line shown for
    information may be far larger; it would squeeze the rule's line and its
    threshold to the bottom. Beyond the scale it is drawn at the edge.
    A chart without a rule's line uses all its lines.
    """
    scale_lines = [line for line in chart.lines if line.from_rule] or chart.lines
    sizes = [abs(value) for line in scale_lines for value in line.values]
    high = max(
        [2 * abs(value) for _, value in chart.thresholds]
        + ([percentile(sizes, 99.5)] if sizes else [])
        + [1e-9]   # never zero, so the drawing can always divide by it
    )
    below_zero = any(value < 0 for line in chart.lines for value in line.values) or \
        any(value < 0 for _, value in chart.thresholds)
    chart.high = high
    chart.low = -high if below_zero else 0.0   # zero in the middle if values go both ways
    return chart


def pace_chart(sensor_seconds):
    """What the pace rule looks at: the braking and accelerating force.

    The order matters: the overview picture (overview.py) takes the force
    as the first line, the effort as the second, and the pace threshold as
    the first threshold.
    """
    times = [second.start_seconds for second in sensor_seconds]
    forces = forward_force_per_second(sensor_seconds)
    return with_scale(Chart(
        title="pace",
        lines=[
            Line("force", times, forces, True),
            Line("effort", times, effort_per_second(forces), True),
        ],
        thresholds=[("pace", settings.PACE_MIN_EFFORT), ("hard", settings.PACE_HARD_FORCE)],
        marks=[],
    ))


def sliding_chart(sensor_seconds):
    """What the sliding rule looks at, part 1: the cornering force."""
    samples = cornering_and_turning(sensor_seconds)
    return with_scale(Chart(
        title="sliding",
        lines=[Line("cornering force", [time for time, _, _ in samples], [force for _, force, _ in samples], True)],
        thresholds=[("min", settings.SLIDE_MIN_CORNERING_FORCE), ("-min", -settings.SLIDE_MIN_CORNERING_FORCE)],
        marks=find_catch_times(samples),
    ))


def turning_chart(sensor_seconds):
    """What the sliding rule looks at, part 2: how fast the car turns.

    A chart of its own, because turning is measured in another unit than
    the cornering force and is far smaller: on one scale it would be flat.
    """
    samples = cornering_and_turning(sensor_seconds)
    return with_scale(Chart(
        title="turning",
        lines=[Line("turning", [time for time, _, _ in samples], [turning for _, _, turning in samples], True)],
        thresholds=[("min", settings.SLIDE_MIN_TURNING_BEFORE), ("-min", -settings.SLIDE_MIN_TURNING_BEFORE)],
        marks=find_catch_times(samples),
    ))


def offtrack_chart(sensor_seconds):
    """What the offtrack rule looks at: how hard the car shakes up and down.

    The rule's line is the shake after smoothing, so a fast vibration of
    the camera does not show in it (see offtrack.py). A second line shows
    the shake without smoothing, for information: where it is high and the
    rule's line is not, the camera vibrates.
    """
    def line(name, smoothing, from_rule):
        samples = shake_over_time(sensor_seconds, smoothing)
        return Line(name, [time for time, _ in samples], [shake for _, shake in samples], from_rule)

    return with_scale(Chart(
        title="offtrack",
        lines=[
            line("shake", None, True),               # None: the smoothing the rule uses
            line("shake unsmoothed", 1, False),
        ],
        thresholds=[("min", settings.OFFTRACK_MIN_SHAKE)],
        marks=[],
    ))


# The charts by the names used in check_video_settings.STRIP_CHARTS.
CHARTS = {
    "pace": pace_chart,
    "sliding": sliding_chart,
    "turning": turning_chart,
    "offtrack": offtrack_chart,
}


def window(line, start, end):
    """Return the (times, values) of a line between two moments, both included.

    This is asked for every line of every picture of the check video, so it
    does not walk through the whole line: bisect finds a place in a sorted
    list in a few steps.
    """
    first = bisect_left(line.times, start)
    last = bisect_right(line.times, end)
    return line.times[first:last], line.values[first:last]
