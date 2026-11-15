"""Made-up data that several check files use."""

from pp_tt_video import settings
from pp_tt_video.detect_cars import CarBox
from pp_tt_video.detections_file import Detections
from pp_tt_video.sensors import SensorSecond

# Made-up driving, one braking or accelerating force per second (m/s²).
ROLLING = [0.5, 1.0, 0.5, 1.5, 0.5]            # gentle: pit lane or a slow lap
RACING = [4.0, 0.5, 3.5, 3.0, 0.5, 4.5, 1.0]   # hard braking and accelerating


def repeat(pattern, seconds):
    """Repeat a pattern until it is the given number of seconds long."""
    return [pattern[i % len(pattern)] for i in range(seconds)]


def driving(seconds_of_force):
    """Made-up sensor data: one SensorSecond per (forward force, sideways force).

    Every second holds ten identical measurements. The axes follow
    settings.py: 0 is down (gravity), 1 is sideways, 2 is forward.
    """
    return [
        SensorSecond(float(number), [(-9.8, sideways, forward)] * 10, [(0.0, 0.0, 0.0)] * 10)
        for number, (forward, sideways) in enumerate(seconds_of_force)
    ]


def car_box(centre_x, height, confidence=0.95, centre_y=360):
    """A box around a car seen from behind: twice as wide as it is tall."""
    return CarBox(centre_x - height, centre_y - height / 2, centre_x + height, centre_y + height / 2, confidence)


def detections_of(pictures, picture_height=720):
    """Detections as a pass over a 1280 pixel wide video would give them.

    pictures: a list of (time in seconds, [CarBox, ...]).
    """
    return Detections(
        analysis_width=1280,
        picture_height=picture_height,
        frames_per_second=settings.ANALYSIS_FRAMES_PER_SECOND,
        min_confidence=settings.MIN_DETECTION_CONFIDENCE,
        pictures=pictures,
    )


def pictures_of(cars, start=0.0, step=0.2):
    """Turn car histories into pictures.

    cars: one list of boxes per car, all the same length; picture n holds
    box n of every car (None where a car is not seen).
    """
    count = len(cars[0])
    return [
        (round(start + number * step, 3), [car[number] for car in cars if car[number] is not None])
        for number in range(count)
    ]
