"""Step 8: find the part of the video that is driven at pace.

What lies before and after that part is named in session.py.

How the car's pace is recognised, without GPS: a driver at pace brakes hard
and accelerates hard, again and again. On a warm-up or cool-down lap the
car rolls along: the corners may still be taken briskly, but the brake and
the throttle are used gently. So the rule looks at the force along the car
(braking and accelerating), not at the speed and not at the cornering force.

The speed itself was tried and does not work: in the examples a cool-down
lap is only about 10 km/h slower than a fast lap.
"""

from pp_tt_video import settings


def average(values):
    return sum(values) / len(values)


def forward_force_per_second(sensor_seconds):
    """Return the braking or accelerating force of every second, in m/s².

    The 200 measurements of a second are averaged, which removes the
    vibration of the engine and the road. The sign (plus or minus) is
    dropped: braking and accelerating both count as driving hard.
    """
    axis = settings.ACCELERATION_AXIS_FORWARD
    return [
        abs(average([measurement[axis] for measurement in second.acceleration]))
        for second in sensor_seconds
    ]


def effort_per_second(forces):
    """Average the force over a long window around every second.

    One hard braking says little; a driver at pace does it every few
    seconds. The window is long enough to always hold a few corners.
    """
    half = settings.PACE_WINDOW_SECONDS // 2
    efforts = []
    for position in range(len(forces)):
        window = forces[max(0, position - half):position + half + 1]
        efforts.append(average(window))
    return efforts


def runs_of_true(flags):
    """Return (first, last) for every unbroken series of True values."""
    runs = []
    first = None
    for position, flag in enumerate(flags):
        if flag and first is None:
            first = position
        if not flag and first is not None:
            runs.append((first, position - 1))
            first = None
    if first is not None:
        runs.append((first, len(flags) - 1))
    return runs


def find_pace_part(forces):
    """Return (first, last): the seconds between which the car is at pace.

    forces: the braking or accelerating force of every second.
    Returns None when the car is never driven at pace.
    """
    efforts = effort_per_second(forces)
    at_pace = [effort >= settings.PACE_MIN_EFFORT for effort in efforts]
    # A short burst (pulling away briskly in the pit lane) is not "at pace".
    runs = [
        (first, last) for first, last in runs_of_true(at_pace)
        if last - first + 1 >= settings.PACE_MIN_SECONDS
    ]
    if not runs:
        return None
    # Slow moments in the middle of a session (traffic, a mistake) stay
    # inside the part: warm up is only at the start, cooling only at the end.
    first, last = runs[0][0], runs[-1][1]
    end_of_video = len(forces) - 1

    def is_hard(position):
        return forces[position] >= settings.PACE_HARD_FORCE

    # The long window blurs the edges by several seconds. They are sharpened
    # by moving them to the first and the last moment of really hard braking
    # or accelerating inside the part.
    if first < settings.PACE_MIN_EDGE_SECONDS:
        first = 0   # the video starts at pace: no warm up
    else:
        while first < last and not is_hard(first):
            first += 1
    if end_of_video - last < settings.PACE_MIN_EDGE_SECONDS:
        last = end_of_video   # the video ends at pace: no cooling
    else:
        while last > first and not is_hard(last):
            last -= 1
    return first, last


def outside_pace(stretch, session_parts):
    """True when a stretch lies, with its middle, outside the part at pace.

    session_parts: the stretches found by session.py (out of session,
    warm up, cooling, crash).
    """
    middle = (stretch.start + stretch.end) / 2
    return any(part.start <= middle <= part.end + 1 for part in session_parts)
