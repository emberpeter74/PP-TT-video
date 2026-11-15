"""Draws the overview picture: one picture of a whole video.

The check video shows a few seconds at a time. Some problems only show
over the whole video: the pace rule that never fires, twenty offtracks in a
row, an event thrown away because it lies in the warm up. The overview has
time running from left to right and, from the top:

  - the pace rule: force and effort with the rule's thresholds, in front of
    coloured bands for the large parts of the video (out of session, warm
    up, at pace, cooling, crash),
  - the moments the effort was high enough, but too briefly to count,
  - one row per event: kept events as filled bars, thrown-away ones as
    outlines,
  - one row for the cars that were followed.

Like the check video it decides nothing: everything comes from an
Explanation (explain.py), so the thresholds are those of the profile.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from pp_tt_video import settings
from pp_tt_video.draw import (
    DROPPED_COLOUR,
    LINE_COLOURS,
    STRIP_BACKGROUND,
    STRIP_BORDER,
    TEXT_COLOUR,
    THRESHOLD_COLOUR,
    dashed_line,
    font_of_size,
)
from pp_tt_video.event_types import load_event_types
from pp_tt_video.events import format_time
from pp_tt_video.pace import runs_of_true

# Sizes in pixels.
WIDTH = 2000
LEFT = 170            # room for the names of the rows
RIGHT = 100           # room for the thresholds' names and values
TITLE_HEIGHT = 50
PACE_HEIGHT = 240
BRIEF_HEIGHT = 22
LEGEND_HEIGHT = 40
ROW_HEIGHT = 30
BAR_HEIGHT = 18
AXIS_HEIGHT = 44
TEXT_SIZE = 16
TITLE_SIZE = 24
MIN_BAR_WIDTH = 3     # so an event of one second can still be seen

# Colours are (red, green, blue), each from 0 to 255. The bands are dark,
# so the lines in front of them stay readable.
AT_PACE = "at pace"
BAND_COLOURS = {
    settings.OUT_OF_SESSION_LABEL: (70, 70, 70),
    settings.WARM_UP_LABEL: (45, 60, 125),
    AT_PACE: (25, 75, 35),
    settings.COOLING_LABEL: (25, 95, 105),
    settings.CRASH_LABEL: (135, 30, 30),
}
OTHER_BAND_COLOUR = (90, 60, 100)
FORCE_COLOUR = (150, 140, 60)     # thin and dim: the single seconds
EFFORT_COLOUR = LINE_COLOURS[1]   # thick and bright: what the rule decides on
BRIEF_COLOUR = (255, 130, 255)
EVENT_COLOUR = (255, 190, 0)
CAR_COLOUR = (90, 190, 255)

# How far apart the written times on the time line may be, in minutes.
MINUTE_STEPS = [1, 2, 5, 10, 15, 30, 60]
MOST_WRITTEN_TIMES = 35


def overview_path_for(video_path, output_folder=None):
    """Return where the overview picture for a video belongs.

    Naming rule: "something.mp4" gives "something-overview.png".
    """
    video_path = Path(video_path)
    folder = Path(output_folder) if output_folder else video_path.parent
    return folder / (video_path.stem + "-overview.png")


def labels_with_rows(explanation):
    """The event labels that get a row: those that occur, in the usual order."""
    present = {stretch.label for stretch in explanation.kept_stretches}
    present.update(dropped.stretch.label for dropped in explanation.dropped_stretches)
    in_order = [label for label in load_event_types() if label in present]
    return in_order + sorted(present.difference(in_order))


def draw_bar(draw, left, right, middle, colour, filled):
    """Draw one bar of a row: filled, or as an outline only."""
    right = max(right, left + MIN_BAR_WIDTH)
    area = (left, middle - BAR_HEIGHT // 2, right, middle + BAR_HEIGHT // 2)
    if filled:
        draw.rectangle(area, fill=colour)
    else:
        draw.rectangle(area, outline=colour, width=1)


def draw_pace(draw, explanation, top, height, x_of):
    """Draw the pace rule's part: bands, force, effort and thresholds."""
    bottom = top + height
    left, right = LEFT, WIDTH - RIGHT
    font = font_of_size(TEXT_SIZE)
    chart = explanation.charts.get("pace")
    draw.text((8, top + 4), "pace", font=font, fill=TEXT_COLOUR)
    if chart is None:
        draw.rectangle((left, top, right, bottom), outline=STRIP_BORDER)
        draw.text((left + 8, top + 8), "no sensor data", font=font, fill=DROPPED_COLOUR)
        return

    # The bands. What no session part covers is the part at pace.
    draw.rectangle((left, top, right, bottom), fill=BAND_COLOURS[AT_PACE])
    for part in explanation.session_parts:
        colour = BAND_COLOURS.get(part.label, OTHER_BAND_COLOUR)
        draw.rectangle((x_of(part.start), top, x_of(part.end), bottom), fill=colour)

    def y_of(value):
        part = (value - chart.low) / (chart.high - chart.low)
        return bottom - 2 - min(1.0, max(0.0, part)) * (height - 4)

    # The chart's lines are the force and the effort, in this order.
    name_top = top + 30
    for line, colour, width in zip(chart.lines, (FORCE_COLOUR, EFFORT_COLOUR), (1, 3)):
        points = [(x_of(time), y_of(value)) for time, value in zip(line.times, line.values)]
        if len(points) > 1:
            draw.line(points, fill=colour, width=width)
        draw.text((8, name_top), line.name, font=font, fill=colour)   # its name, under "pace" at the left
        name_top += 22

    for label, value in chart.thresholds:
        y = y_of(value)
        dashed_line(draw, left, right, y, THRESHOLD_COLOUR)
        # Written beside the chart, so it never covers a line.
        draw.text((right + 6, y), f"{label} {value:g}", font=font, anchor="lm", fill=THRESHOLD_COLOUR)


def draw_brief_runs(draw, explanation, top, x_of):
    """Mark where the effort was high enough, but too briefly to count as at pace."""
    chart = explanation.charts.get("pace")
    if chart is None:
        return
    draw.text((8, top + 2), "too brief", font=font_of_size(TEXT_SIZE), fill=BRIEF_COLOUR)
    effort = chart.lines[1]
    pace_threshold = chart.thresholds[0][1]
    for first, last in runs_of_true([value >= pace_threshold for value in effort.values]):
        if last - first + 1 < settings.PACE_MIN_SECONDS:
            left = x_of(effort.times[first])
            draw.rectangle((left, top + 6, max(x_of(effort.times[last] + 1), left + MIN_BAR_WIDTH), top + 16),
                           fill=BRIEF_COLOUR)


def draw_legend(draw, top):
    """Explain the colours of the bands and the two kinds of bars."""
    font = font_of_size(TEXT_SIZE)
    x = LEFT
    middle = top + LEGEND_HEIGHT // 2
    for name, colour in BAND_COLOURS.items():
        draw.rectangle((x, middle - 8, x + 24, middle + 8), fill=colour, outline=STRIP_BORDER)
        draw.text((x + 32, middle), name, font=font, anchor="lm", fill=TEXT_COLOUR)
        x += 32 + draw.textlength(name, font=font) + 30
    x += 30
    for name, filled in (("event kept", True), ("event thrown away", False)):
        draw_bar(draw, x, x + 24, middle, EVENT_COLOUR if filled else DROPPED_COLOUR, filled)
        draw.text((x + 32, middle), name, font=font, anchor="lm", fill=TEXT_COLOUR)
        x += 32 + draw.textlength(name, font=font) + 30


def draw_time_line(draw, duration_seconds, top, x_of):
    """Draw the time along the bottom: a tick per minute, a time every few."""
    font = font_of_size(TEXT_SIZE)
    draw.line((LEFT, top, WIDTH - RIGHT, top), fill=TEXT_COLOUR)
    minutes = int(duration_seconds // 60)
    # The first step that leaves room between the written times.
    step = next((step for step in MINUTE_STEPS if minutes / step <= MOST_WRITTEN_TIMES), MINUTE_STEPS[-1])
    tick_step = 1 if minutes <= 120 else step
    for minute in range(0, minutes + 1, tick_step):
        x = x_of(minute * 60)
        written = minute % step == 0
        draw.line((x, top, x, top + (9 if written else 5)), fill=TEXT_COLOUR)
        if written:
            draw.text((x, top + 12), format_time(minute * 60), font=font, anchor="ma", fill=TEXT_COLOUR)


def draw_overview(explanation, profile_name, video_name):
    """Return the overview picture of a video, as a Pillow image.

    explanation:  what the rules did with the video (see explain.py).
    profile_name: the driver and car profile in force.
    video_name:   written in the title.
    """
    labels = labels_with_rows(explanation)
    has_sensors = "pace" in explanation.charts
    pace_height = PACE_HEIGHT if has_sensors else 2 * ROW_HEIGHT
    height = (TITLE_HEIGHT + pace_height + BRIEF_HEIGHT + LEGEND_HEIGHT
              + (len(labels) + 1) * ROW_HEIGHT + AXIS_HEIGHT)
    picture = Image.new("RGB", (WIDTH, height), STRIP_BACKGROUND)
    draw = ImageDraw.Draw(picture)
    font = font_of_size(TEXT_SIZE)
    duration = max(explanation.duration_seconds, 1.0)   # never zero: it is divided by

    def x_of(time_seconds):
        part = min(1.0, max(0.0, time_seconds / duration))
        return LEFT + part * (WIDTH - RIGHT - LEFT)

    title = f"{video_name}   profile: {profile_name}   length {format_time(explanation.duration_seconds)}"
    draw.text((LEFT, 12), title, font=font_of_size(TITLE_SIZE), fill=TEXT_COLOUR)

    top = TITLE_HEIGHT
    draw_pace(draw, explanation, top, pace_height, x_of)
    top += pace_height
    draw_brief_runs(draw, explanation, top, x_of)
    top += BRIEF_HEIGHT
    draw_legend(draw, top)
    top += LEGEND_HEIGHT

    # One row per event label.
    for label in labels:
        middle = top + ROW_HEIGHT // 2
        draw.line((LEFT, top, WIDTH - RIGHT, top), fill=STRIP_BORDER)
        draw.text((8, middle), label, font=font, anchor="lm", fill=TEXT_COLOUR)
        for dropped in explanation.dropped_stretches:
            if dropped.stretch.label == label:
                draw_bar(draw, x_of(dropped.stretch.start), x_of(dropped.stretch.end), middle, DROPPED_COLOUR, False)
        for stretch in explanation.kept_stretches:
            if stretch.label == label:
                draw_bar(draw, x_of(stretch.start), x_of(stretch.end), middle, EVENT_COLOUR, True)
        top += ROW_HEIGHT

    # The cars that were followed. A car the model was never sure of is
    # skipped by the car rules: it is drawn as an outline, like a dropped event.
    middle = top + ROW_HEIGHT // 2
    draw.line((LEFT, top, WIDTH - RIGHT, top), fill=STRIP_BORDER)
    draw.text((8, middle), f"cars ({len(explanation.tracks)})", font=font, anchor="lm", fill=TEXT_COLOUR)
    for track in explanation.tracks:
        trusted = track.best_confidence >= settings.CAR_MIN_CONFIDENCE
        draw_bar(draw, x_of(track.start), x_of(track.end), middle, CAR_COLOUR if trusted else DROPPED_COLOUR, trusted)
    top += ROW_HEIGHT

    draw_time_line(draw, explanation.duration_seconds, top, x_of)
    return picture


def write_overview(path, explanation, profile_name, video_name):
    """Draw the overview picture and write it as a PNG file."""
    path = Path(path)
    # Written under another name first, so a half-written picture is never
    # mistaken for a finished one.
    part_path = path.with_name(path.stem + ".part.png")
    draw_overview(explanation, profile_name, video_name).save(part_path)
    part_path.replace(path)   # replace: rename, also when the file exists already
