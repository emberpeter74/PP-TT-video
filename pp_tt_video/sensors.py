"""Reads the motion sensor data that the GoPro stores inside the video file.

The camera has an accelerometer (which forces act on it) and a gyroscope
(how fast it rotates). Both are measured about 200 times per second and are
stored in blocks of one second. The camera is fixed to the car, so these
are the forces on the car and the rotation of the car.

Unlike the GPS, the motion sensors need no satellites: the data is there for
the whole video.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from pp_tt_video import settings


class SensorError(Exception):
    """Raised when the motion sensor data of a video cannot be read."""


@dataclass
class SensorSecond:
    """The motion sensor data of one block (about one second) of video.

    Every measurement is a group of three numbers, one per axis of the
    camera. Which axis points where is written down in settings.py.
    """

    start_seconds: float   # position of the block in the video
    acceleration: list     # measurements in m/s², each a tuple of 3 numbers
    rotation: list         # measurements in radians per second, each a tuple of 3


def in_groups_of_three(text):
    """Turn "1 2 3 4 5 6" into [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]."""
    numbers = [float(part) for part in text.split()]
    return [tuple(numbers[i:i + 3]) for i in range(0, len(numbers) - 2, 3)]


def parse_sensor_text(text):
    """Turn what ExifTool printed (see sensors.fmt) into a list of SensorSecond."""
    seconds = []
    for line in text.splitlines():
        # Every line is "<letter>|<values>".
        kind, _, values = line.partition("|")
        if kind == "T":
            start = float(values.split("|")[0])
            seconds.append(SensorSecond(start, [], []))
        elif kind == "A" and seconds:
            seconds[-1].acceleration = in_groups_of_three(values)
        elif kind == "G" and seconds:
            seconds[-1].rotation = in_groups_of_three(values)
    # Blocks without measurements are of no use.
    return [second for second in seconds if second.acceleration and second.rotation]


def pieces_of_seconds(sensor_seconds, pieces_per_second):
    """Cut every sensor second into equal pieces.

    Some rules need a finer view than one value per second. Returns a list
    of (time, acceleration measurements, rotation measurements), one entry
    per piece, in order of time.
    """
    pieces = []
    for second in sensor_seconds:
        for number in range(pieces_per_second):
            def part_of(measurements):
                first = len(measurements) * number // pieces_per_second
                last = len(measurements) * (number + 1) // pieces_per_second
                return measurements[first:last]

            acceleration, rotation = part_of(second.acceleration), part_of(second.rotation)
            if acceleration and rotation:
                time = second.start_seconds + number / pieces_per_second
                pieces.append((time, acceleration, rotation))
    return pieces


def read_sensors(video_path):
    """Read the motion sensor data of one video. Returns a list of SensorSecond.

    The list is empty when the video holds no such data (not a GoPro file).
    """
    video_path = Path(video_path)
    if not video_path.is_file():
        raise SensorError(f"Video file not found: {video_path}")
    command = [
        str(settings.EXIFTOOL),
        "-q", "-q",   # no messages about blocks that lack one of the values
        "-ee",        # read the data embedded along the whole video
        "-n",         # plain numbers, no units
        "-b",         # print long lists of values in full
        "-p", str(settings.SENSOR_TEMPLATE),
        str(video_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True)
    except FileNotFoundError:
        raise SensorError(f"ExifTool not found: {settings.EXIFTOOL}")
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise SensorError(f"ExifTool failed for {video_path.name}: {message}")
    return parse_sensor_text(result.stdout.decode("utf-8", errors="replace"))
