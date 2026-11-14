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

Run it from a terminal, in the project folder:
    .venv\\Scripts\\python.exe -m pp_tt_video.make_profile "<folder with one driver's videos>"
"""

import argparse
import sys
from pathlib import Path

from pp_tt_video import settings
from pp_tt_video.pace import effort_per_second, forward_force_per_second
from pp_tt_video.pipeline import find_videos
from pp_tt_video.profile import PROFILE_VALUES
from pp_tt_video.sensors import SensorError, read_sensors
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


def levels_line(label, braking, cornering):
    """One line of the report: the two levels and the ratios to the reference."""
    braking_ratio, cornering_ratio = ratios(braking, cornering)
    return (f"{label}: braking level {braking:.2f} (ratio {braking_ratio:.2f}), "
            f"cornering level {cornering:.2f} (ratio {cornering_ratio:.2f})")


def make_profile(folder, name=None, overwrite=False, print_only=False, read=read_sensors, on_video=None):
    """Measure the driver in a folder of videos and write a profile file.

    folder:     the folder with one driver's videos (and no one else's).
    name:       None writes profile.toml into the folder; a name writes
                <name>.toml into the profiles folder.
    print_only: measure and report, but write no file.
    read:       the function that reads a video's sensor data. The checks
                hand in a stand-in, so they need no real video.
    on_video:   if given, on_video(text) is called after each video is read,
                to show progress (reading takes about 5 seconds per video).

    Returns (ok, message).
    """
    folder = Path(folder)
    if not folder.is_dir():
        return False, f"Folder not found: {folder}"
    target = settings.PROFILES_FOLDER / f"{name}.toml" if name else folder / settings.PROFILE_FILE_NAME
    # Check first, before minutes of reading: an existing profile may have
    # been changed by hand, and must not be lost by accident.
    if target.exists() and not overwrite and not print_only:
        return False, f"{target.name} already exists; use --overwrite to replace it"

    used_names, used_sensors, report = [], [], []
    for video in find_videos([folder]):
        try:
            sensor_seconds = read(video)
        except SensorError as error:
            sensor_seconds, reason = [], str(error)
        else:
            reason = "no motion sensor data"
        if not sensor_seconds:
            line = f"{video.name}: skipped, {reason}"
        else:
            used_names.append(video.name)
            used_sensors.append(sensor_seconds)
            line = levels_line(video.name, *driver_levels([sensor_seconds]))
        report.append(line)
        if on_video:
            on_video(line)

    if not used_sensors:
        report.append("No video with motion sensor data found: no profile written.")
        return False, "\n".join(report)

    braking, cornering = driver_levels(used_sensors)
    report.append(levels_line(f"All videos together ({len(used_names)} in total)", braking, cornering))
    if print_only:
        return True, "\n".join(report)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(profile_text(used_names, braking, cornering), encoding="utf-8")
    report.append(f"Profile written to {target}")
    return True, "\n".join(report)


def main():
    parser = argparse.ArgumentParser(
        prog="pp_tt_video.make_profile",
        description="Make a driver and car profile from a folder of one driver's videos.",
    )
    parser.add_argument("folder", help="the folder with the driver's videos")
    parser.add_argument("--name", help="write profiles/<name>.toml instead of profile.toml in the folder")
    parser.add_argument("--overwrite", action="store_true", help="replace a profile that already exists")
    parser.add_argument("--print-only", action="store_true", help="measure and show the levels, write nothing")
    arguments = parser.parse_args()

    shown = []   # the lines already printed while the videos were read

    def show(line):
        # flush=True shows the line at once instead of waiting for more output.
        print(line, flush=True)
        shown.append(line)

    ok, message = make_profile(arguments.folder, arguments.name, arguments.overwrite,
                               arguments.print_only, on_video=show)
    # The report starts with the per-video lines, which are on the screen
    # already; print only what comes after them.
    for line in message.splitlines()[len(shown):]:
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
