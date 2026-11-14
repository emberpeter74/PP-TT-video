"""Makes a driver and car profile from a folder of one driver's videos.

The driver is measured from the camera's motion sensors: how hard they
typically brake and accelerate, and how hard they typically corner. These
two levels are compared with the reference driver (the user, measured on
the three examples), and the values that depend on the driver are scaled
by the same ratio. A driver who brakes half as hard gets half the pace
thresholds.

Values that depend on the car or the camera cannot be measured this way.
They are written into the file as built-in values, switched off, to be
changed by hand if needed.
"""

from pp_tt_video import settings
from pp_tt_video.pace import effort_per_second, forward_force_per_second
from pp_tt_video.profile import PROFILE_VALUES
from pp_tt_video.session import value_per_second

# What each profile value does, written as a comment above it in the file.
EXPLANATIONS = {
    "PACE_MIN_EFFORT": "Average braking or accelerating force (m/s²) from which the car counts as at pace.",
    "PACE_HARD_FORCE": "Braking or accelerating this hard (m/s²) marks the first and last moment at pace.",
    "SLIDE_MIN_CORNERING_FORCE": "Slides are looked for only in corners with at least this cornering force (m/s²).",
    "SESSION_TRACK_CORNER_FORCE": "A corner of the track has at least this cornering force (m/s²); pit lane turns have less.",
    "OFFTRACK_MIN_SHAKE": "How hard the car must shake up and down (m/s²) to count as off the track.",
    "STANDSTILL_MAX_SHAKE": "The car stands still when it shakes less than this (m/s²).",
    "PASSING_CAR_HEIGHT": "Another car taller than this part of the picture is right next to us.",
    "CLOSE_CAR_HEIGHT": "A car ahead taller than this part of the picture is close enough to hold us up.",
    "MAX_CAR_WIDTH_FRACTION": "A find wider than this part of the picture is the own cockpit, not a car.",
}


def percentile(values, percent):
    """Return the value that the given percent of the values do not exceed.

    The 95th percentile of a list is the value only the top 5% reach. Raises
    ValueError for an empty list: there is nothing to measure.
    """
    if not values:
        raise ValueError("no values to measure")
    ordered = sorted(values)
    return ordered[round(percent / 100 * (len(ordered) - 1))]


def braking_values(sensor_seconds):
    """The pace effort of every second of one video, as the pace rule sees it."""
    return effort_per_second(forward_force_per_second(sensor_seconds))


def cornering_values(sensor_seconds):
    """The cornering force of every second of one video, without its sign."""
    sideways = value_per_second(sensor_seconds, lambda second: second.acceleration,
                                settings.ACCELERATION_AXIS_SIDEWAYS)
    return [abs(force) for force in sideways]


def driver_levels(videos_sensor_seconds):
    """Return (braking level, cornering level) over all videos together.

    videos_sensor_seconds: one list of SensorSecond per video. The effort is
    worked out per video and the seconds are put together afterwards, so the
    long averaging window of the pace rule never spans two videos.
    """
    braking, cornering = [], []
    for sensor_seconds in videos_sensor_seconds:
        braking.extend(braking_values(sensor_seconds))
        cornering.extend(cornering_values(sensor_seconds))
    return (percentile(braking, settings.PROFILE_PERCENTILE),
            percentile(cornering, settings.PROFILE_PERCENTILE))


def ratios(braking, cornering):
    """How the driver compares with the reference driver: (braking, cornering)."""
    return braking / settings.REFERENCE_EFFORT, cornering / settings.REFERENCE_CORNERING


def scaled_values(braking, cornering):
    """Return the driver's values: each built-in value times the driver's ratio.

    Only the values that depend on the driver are in the result.
    """
    braking_ratio, cornering_ratio = ratios(braking, cornering)
    ratio_for = {"driver braking": braking_ratio, "driver cornering": cornering_ratio}
    values = {}
    for name, depends_on in PROFILE_VALUES.items():
        if depends_on in ratio_for:
            values[name] = round(getattr(settings, name) * ratio_for[depends_on], 2)
    return values


def profile_text(video_names, braking, cornering):
    """Return the text of a profile file for the measured driver."""
    braking_ratio, cornering_ratio = ratios(braking, cornering)
    values = scaled_values(braking, cornering)
    lines = [
        f"# Driver and car profile, made by make_profile from {len(video_names)} videos:",
        f"# {', '.join(video_names)}",
        f"# Braking level {braking:.2f} (reference driver: {settings.REFERENCE_EFFORT:.2f}), ratio {braking_ratio:.2f}",
        f"# Cornering level {cornering:.2f} (reference driver: {settings.REFERENCE_CORNERING:.2f}), ratio {cornering_ratio:.2f}",
        "",
        "# --- Driver: scaled from the measurement above ---",
    ]
    for name, value in values.items():
        lines += [f"# {EXPLANATIONS[name]}", f"{name} = {value}", ""]
    lines.append("# --- Car and camera: built-in values, remove the # to change one ---")
    for name in PROFILE_VALUES:
        if name not in values:
            lines += [f"# {EXPLANATIONS[name]}", f"# {name} = {getattr(settings, name)}", ""]
    return "\n".join(lines)
