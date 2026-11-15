"""Writes the motion sensor data of a video to a CSV file.

A CSV file is a plain table: one line per row, the values separated by
commas. It opens in Excel and is easy to read from other programs.

The file holds every measurement exactly as the camera stored it: the three
acceleration values (m/s²) and the three rotation values (radians per
second), along the camera's own axes. Which axis points where is written in
settings.py. The raw values are kept on purpose: if a camera is mounted
differently, only they will show it.
"""

import csv
from pathlib import Path

HEADER = [
    "time_seconds",
    "acceleration_x", "acceleration_y", "acceleration_z",
    "rotation_x", "rotation_y", "rotation_z",
]


def sensors_path_for(video_path, output_folder=None):
    """Return where the sensor file for a video belongs.

    Naming rule: "something.mp4" gives "something-sensors.csv".
    """
    video_path = Path(video_path)
    folder = Path(output_folder) if output_folder else video_path.parent
    return folder / (video_path.stem + "-sensors.csv")


def sensor_rows(sensor_seconds):
    """Return one row per measurement: (time, 3 acceleration values, 3 rotation values).

    The camera stores the measurements in blocks of about one second and
    only says when a block starts. The measurements of a block are spread
    evenly over it: a block lasts until the next one starts (the last one
    is taken to be one second long).
    """
    rows = []
    for number, second in enumerate(sensor_seconds):
        if number + 1 < len(sensor_seconds):
            length = sensor_seconds[number + 1].start_seconds - second.start_seconds
        else:
            length = 1.0
        count = len(second.acceleration)
        for position, acceleration in enumerate(second.acceleration):
            time = second.start_seconds + position * length / count
            # Now and then a block holds one rotation value fewer than
            # acceleration values; the missing ones are left empty.
            if position < len(second.rotation):
                rotation = second.rotation[position]
            else:
                rotation = ("", "", "")
            rows.append((time, *acceleration, *rotation))
    return rows


def write_sensor_file(path, sensor_seconds):
    """Write the sensor data to a CSV file.

    The file is written under a temporary name and renamed when it is
    complete, so an interrupted run never leaves half a file that the next
    run would take for a finished one.
    """
    path = Path(path)
    part = path.with_name(path.name + ".part")
    # newline="" lets the csv module decide the line endings itself.
    with open(part, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(HEADER)
        for time, *values in sensor_rows(sensor_seconds):
            writer.writerow([f"{time:.4f}", *values])
    part.replace(path)   # replace = rename, also over an existing file
