"""Step 6, part 3: decide what each tracked car means.

The rules look at how tall another car appears over time:

    overtaking   the car grows and then vanishes while it is large:
                 we caught it and passed it.
    overtaken    the car appears large and then shrinks:
                 it came from behind and pulled away.
    held up      the car stays close ahead for some time.

The position of the car in the picture is not used. The camera's
stabilisation moves the whole view around, so position is unreliable; size
is not affected by it.
"""

from dataclasses import dataclass

from pp_tt_video import settings


@dataclass(frozen=True)
class Stretch:
    """A stretch of time with one label."""

    start: float   # seconds since the beginning of the video
    end: float
    label: str


def smooth(values):
    """Replace every value by the middle one of itself and its two neighbours.

    This removes a single wrong value (the model sometimes draws one box far
    too large) without blurring a real, lasting change.
    """
    if len(values) < 3:
        return list(values)
    padded = [values[0]] + list(values) + [values[-1]]
    return [sorted(padded[i:i + 3])[1] for i in range(len(values))]


def split_into_runs(flags, times, max_gap):
    """Group the positions where flags is True into runs.

    A run is a series of positions that follow each other without a pause in
    time longer than max_gap. Returns a list of (first, last) positions.
    """
    runs = []
    first = last = None
    for position, flag in enumerate(flags):
        if not flag:
            continue
        if first is not None and times[position] - times[last] <= max_gap:
            last = position
        else:
            if first is not None:
                runs.append((first, last))
            first = last = position
    if first is not None:
        runs.append((first, last))
    return runs


def events_of_track(track, picture_height):
    """Return the stretches (overtaking, overtaken, held up) of one car."""
    if track.best_confidence < settings.CAR_MIN_CONFIDENCE:
        return []

    times = [sighting.time_seconds for sighting in track.sightings]
    heights = smooth([sighting.box.height / picture_height for sighting in track.sightings])
    gap = settings.TRACK_MAX_GAP_SECONDS
    last_position = len(times) - 1
    stretches = []

    # --- Passing: moments when the car is right next to us -------------------
    is_passing = [height >= settings.PASSING_CAR_HEIGHT for height in heights]
    for first, last in split_into_runs(is_passing, times, gap):
        if first == last:
            continue   # seen large in one picture only: too little to go on
        peak = max(heights[first:last + 1])

        # Was the car already large when it was first seen at all?
        appeared_large = times[first] - times[0] <= gap / 2
        # Did it vanish while large? Either the track ends here, or the size
        # drops at once (the tracker has moved on to a different, distant car).
        vanished_large = (
            last == last_position
            or times[last + 1] - times[last] > gap / 2
            or heights[last + 1] <= heights[last] * 0.5
        )

        if vanished_large and not appeared_large:
            # It grew and then vanished: we overtook it. The overtake starts
            # where its final growth began.
            start = first
            while start > 0 and heights[start - 1] >= peak * settings.PASS_START_PART_OF_PEAK:
                start -= 1
            stretches.append(Stretch(times[start], times[last], "overtaking"))
        elif appeared_large and not vanished_large:
            # It appeared large and then shrank: it overtook us. It ends
            # where the car has pulled away.
            end = last
            while end < last_position and heights[end] > peak * settings.PASS_END_PART_OF_PEAK:
                end += 1
            start_time = max(0.0, times[first] - settings.OVERTAKEN_LEAD_SECONDS)
            stretches.append(Stretch(start_time, times[end], "overtaken"))
        # Appeared large AND vanished large: seen too briefly to tell which
        # way it went. Neither: it came close and fell back. No event.

    # --- Held up: the car stays close ahead -----------------------------------
    passes = [stretch for stretch in stretches]
    is_close = []
    for time, height in zip(times, heights):
        during_pass = any(stretch.start <= time <= stretch.end for stretch in passes)
        is_close.append(height >= settings.CLOSE_CAR_HEIGHT and not during_pass)
    for first, last in split_into_runs(is_close, times, gap):
        if times[last] - times[first] >= settings.HELD_UP_MIN_SECONDS:
            stretches.append(Stretch(times[first], times[last], "held up"))

    return stretches


def events_of_tracks(tracks, picture_height):
    """Return the stretches of all tracked cars, in order of time."""
    stretches = []
    for track in tracks:
        stretches.extend(events_of_track(track, picture_height))
    return sorted(stretches, key=lambda stretch: stretch.start)
