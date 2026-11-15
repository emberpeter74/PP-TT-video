"""Draws one picture of the check video.

Takes a picture of the video and draws over it what the module made of
that moment: the car boxes, the events, the profile in use and the time.
What is drawn is chosen in check_video_settings.py.

The drawing is done with Pillow, a library for working with pictures. It
was installed together with the detection libraries.
"""

from bisect import bisect_left, bisect_right
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from pp_tt_video import check_video_settings
from pp_tt_video.charts import window
from pp_tt_video.events import format_time
from pp_tt_video.explain import boxes_at, dropped_at, labels_at

# Colours are (red, green, blue), each from 0 to 255.
STATE_COLOURS = {
    "far": (90, 190, 255),      # blue
    "close": (255, 190, 0),     # amber
    "passing": (255, 60, 60),   # red
}
TEXT_COLOUR = (255, 255, 255)
TEXT_BACKGROUND = (0, 0, 0)
DROPPED_COLOUR = (170, 170, 170)   # grey: what was thrown away

# The sensor strip.
STRIP_BACKGROUND = (18, 18, 22)
STRIP_BORDER = (70, 70, 80)
THRESHOLD_COLOUR = (255, 255, 255)
NOW_COLOUR = (255, 255, 255)
MARK_COLOUR = (255, 60, 60)
LINE_COLOURS = [(255, 210, 0), (0, 220, 255), (255, 130, 255)]   # the rules' lines
INFORMATION_COLOURS = [(110, 200, 110), (200, 140, 90)]          # lines shown for information
STRIP_TEXT_SIZE = 15

# Sizes are given for a picture 1280 pixels wide and grow or shrink with
# the picture, so a smaller check video is still readable.
REFERENCE_WIDTH = 1280
EVENT_TEXT_SIZE = 30
INFO_TEXT_SIZE = 20
BOX_TEXT_SIZE = 16
BOX_LINE_WIDTH = 3
DROPPED_TEXT_SIZE = 20
MARGIN = 8


@lru_cache   # remembers the fonts already loaded, so each size is loaded once
def font_of_size(size):
    # Pillow's built-in font: no font file needs to be installed.
    return ImageFont.load_default(size=size)


def picture_size(video_width, video_height, strip_height):
    """Return the (width, height) of a check video picture.

    The sensor strip sits below the video picture. The height is made even,
    because the video format cannot have an odd size.
    """
    height = video_height + strip_height
    return video_width, height + height % 2


def scaled(value, picture_width):
    """Turn a size meant for a 1280 wide picture into one for this picture."""
    return max(1, round(value * picture_width / REFERENCE_WIDTH))


def strip_height(picture_width):
    """The height of the sensor strip for a picture of this width; 0 if it is switched off."""
    if not check_video_settings.SHOW_STRIP:
        return 0
    return scaled(check_video_settings.STRIP_HEIGHT, picture_width)


def full_picture_size(video_width, video_height):
    """The (width, height) of a check video picture, with the strip the settings ask for."""
    return picture_size(video_width, video_height, strip_height(video_width))


def write_text(draw, position, text, size, anchor="la", colour=TEXT_COLOUR):
    """Write text on a dark background, so it can be read on any picture.

    anchor says which point of the text sits at the position: "la" is its
    top left corner, "ra" its top right corner, "ld" its bottom left corner.
    """
    font = font_of_size(size)
    left, top, right, bottom = draw.textbbox(position, text, font=font, anchor=anchor)
    draw.rectangle((left - 3, top - 2, right + 3, bottom + 2), fill=TEXT_BACKGROUND)
    draw.text(position, text, font=font, anchor=anchor, fill=colour)


def draw_kept_boxes(draw, boxes, picture_width):
    """Draw the cars the rules work with, each in the colour of its state."""
    line_width = scaled(BOX_LINE_WIDTH, picture_width)
    for shown in boxes.kept:
        box = shown.box
        colour = STATE_COLOURS[shown.state]
        draw.rectangle((box.left, box.top, box.right, box.bottom), outline=colour, width=line_width)
        if check_video_settings.SHOW_BOX_DETAILS:
            details = f"car {shown.track_number}  {box.confidence:.2f}  h {shown.height_part:.2f}"
            # "ld": the text stands on the top edge of the box.
            write_text(draw, (box.left, box.top - 4), details, scaled(BOX_TEXT_SIZE, picture_width),
                       anchor="ld", colour=colour)


def draw_dropped_boxes(draw, boxes, picture_width):
    """Draw the boxes that were thrown away: thin, grey, with the reason."""
    for shown in boxes.dropped:
        box = shown.box
        draw.rectangle((box.left, box.top, box.right, box.bottom), outline=DROPPED_COLOUR, width=1)
        if check_video_settings.SHOW_BOX_DETAILS:
            # A car that was followed but never trusted still has a number.
            car = f"car {shown.track_number}  " if shown.track_number else ""
            details = f"{car}{shown.reason}  {box.confidence:.2f}"
            # "la": the text hangs inside the box, below its top edge, so it
            # does not cover the label of a kept box that stands on top.
            write_text(draw, (box.left + 4, box.top + 4), details, scaled(BOX_TEXT_SIZE, picture_width),
                       anchor="la", colour=DROPPED_COLOUR)


def dashed_line(draw, left, right, y, colour):
    """Draw a level line of short dashes."""
    for x in range(int(left), int(right), 12):
        draw.line((x, y, min(x + 6, right), y), fill=colour, width=1)


def draw_chart(draw, chart, area, time_seconds):
    """Draw one chart of the strip into its area (left, top, right, bottom)."""
    left, top, right, bottom = area
    width = right - left
    text_size = scaled(STRIP_TEXT_SIZE, width)
    start = time_seconds - check_video_settings.STRIP_SECONDS_BEFORE
    end = time_seconds + check_video_settings.STRIP_SECONDS_AFTER

    def x_of(time):
        return left + (time - start) / (end - start) * width

    def y_of(value):
        # The largest value of the scale lies at the top edge. Values beyond
        # the scale are drawn at the edge, so they stay inside their chart.
        part = (value - chart.low) / (chart.high - chart.low)
        return bottom - 2 - min(1.0, max(0.0, part)) * (bottom - top - 4)

    draw.rectangle(area, fill=STRIP_BACKGROUND)
    draw.line((left, top, right, top), fill=STRIP_BORDER)   # a rule between two charts
    if chart.low < 0:
        draw.line((left, y_of(0), right, y_of(0)), fill=STRIP_BORDER)   # the zero line

    if check_video_settings.SHOW_THRESHOLDS:
        for label, value in chart.thresholds:
            y = y_of(value)
            dashed_line(draw, left, right, y, THRESHOLD_COLOUR)
            # A threshold below zero is the mirror of one above: its value says enough.
            text = f"{label} {value:g}" if value >= 0 else f"{value:g}"
            draw.text((right - 4, y - 1), text, font=font_of_size(text_size), anchor="rd", fill=THRESHOLD_COLOUR)

    # The rule's own lines are thick and bright, the information lines thin.
    # iter() hands out the colours one after the other.
    colours = iter(LINE_COLOURS)
    information_colours = iter(INFORMATION_COLOURS)
    names = []
    for line in chart.lines:
        colour = next(colours) if line.from_rule else next(information_colours)
        times, values = window(line, start, end)
        points = [(x_of(time), y_of(value)) for time, value in zip(times, values)]
        if len(points) > 1:
            draw.line(points, fill=colour, width=2 if line.from_rule else 1)
        names.append((line.name, colour))

    # The moments the rule noticed something: small ticks along the top.
    for mark in chart.marks[bisect_left(chart.marks, start):bisect_right(chart.marks, end)]:
        draw.line((x_of(mark), top + 1, x_of(mark), top + scaled(10, width)), fill=MARK_COLOUR, width=2)

    # The names of the lines, each in its own colour, in the top left corner.
    x = left + 4
    for name, colour in names:
        draw.text((x, top + 3), name, font=font_of_size(text_size), fill=colour)
        x += draw.textlength(name, font=font_of_size(text_size)) + scaled(16, width)

    draw.line((x_of(time_seconds), top, x_of(time_seconds), bottom), fill=NOW_COLOUR, width=1)   # "now"


def draw_strip(draw, area, time_seconds, explanation):
    """Draw the sensor strip into its area: one chart below the other."""
    left, top, right, bottom = area
    draw.rectangle(area, fill=STRIP_BACKGROUND)
    charts = [explanation.charts[name] for name in check_video_settings.STRIP_CHARTS if name in explanation.charts]
    if not charts:
        text = "no sensor data" if not explanation.charts else "no charts chosen"
        draw.text((left + 8, top + 8), text, font=font_of_size(scaled(INFO_TEXT_SIZE, right - left)),
                  fill=DROPPED_COLOUR)
        return
    height = (bottom - top) / len(charts)
    for number, chart in enumerate(charts):
        draw_chart(draw, chart, (left, round(top + number * height), right, round(top + (number + 1) * height)),
                   time_seconds)


def draw_picture(image, time_seconds, explanation, profile_name):
    """Return a new picture: the given one with the module's work drawn over it.

    image:         one picture of the video, as a Pillow image.
    time_seconds:  where in the video this picture is.
    explanation:   what the rules did with the video (see explain.py).
    profile_name:  the driver and car profile in force.
    """
    width, height = full_picture_size(image.width, image.height)
    picture = Image.new("RGB", (width, height))   # starts black
    picture.paste(image, (0, 0))
    draw = ImageDraw.Draw(picture)
    margin = scaled(MARGIN, width)

    # The sensor strip, below the video picture.
    if height > image.height:
        draw_strip(draw, (0, image.height, width, height), time_seconds, explanation)

    boxes = boxes_at(explanation, time_seconds)
    # The thrown-away boxes go first, so the kept ones are drawn over them.
    if boxes and check_video_settings.SHOW_DROPPED_BOXES:
        draw_dropped_boxes(draw, boxes, width)
    if boxes and check_video_settings.SHOW_KEPT_BOXES:
        draw_kept_boxes(draw, boxes, width)

    if check_video_settings.SHOW_EVENTS:
        labels = ", ".join(labels_at(explanation, time_seconds))
        write_text(draw, (margin, margin), labels, scaled(EVENT_TEXT_SIZE, width))

    if check_video_settings.SHOW_DROPPED_EVENTS:
        dropped = dropped_at(explanation, time_seconds)
        if dropped:
            # The second line, below the event line.
            text = "dropped: " + ", ".join(f"{d.stretch.label} ({d.reason})" for d in dropped)
            below = margin + scaled(EVENT_TEXT_SIZE, width) + scaled(12, width)
            write_text(draw, (margin, below), text, scaled(DROPPED_TEXT_SIZE, width), colour=DROPPED_COLOUR)

    # Always shown: which profile's values the rules used, and the time.
    tenths = int(time_seconds * 10) % 10
    info = f"profile: {profile_name}   {format_time(time_seconds)}.{tenths}"
    write_text(draw, (width - margin, margin), info, scaled(INFO_TEXT_SIZE, width), anchor="ra")
    return picture
