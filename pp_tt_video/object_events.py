"""Step 9, part 2: turn the objects found in a video into events.

The objects are found by find_objects.py and saved by objects_file.py. The
rules here decide what they mean. So far there is one rule: a cone lying on
its side has been knocked onto the track, and that is an "obstacle".

How a new kind of event is added later (for example a car part on the road):
  1. Its label and description go into event_types.csv, like every event.
  2. If the model must look for something new, a line goes into
     settings.OBJECT_WORDS (the kind, and the words for the model).
  3. A rule is written here: a function that takes the Objects of a video
     and returns a list of Stretches with the new label. It is added to
     OBJECT_RULES at the bottom of this file.
Nothing else needs to change: every rule in the list is asked, and its
stretches go into the events file like those of every other rule.
"""

from pp_tt_video import settings
from pp_tt_video.stretch import Stretch


def is_lying_cone(box, boxes_of_picture, picture_width):
    """True when this box is a cone lying on its side.

    box:              the ObjectBox to judge.
    boxes_of_picture: every box of the same picture (box itself included).
    picture_width:    the width of the picture, in pixels.
    """
    if box.kind != "cone":
        return False
    if box.confidence < settings.OBSTACLE_MIN_CONFIDENCE:
        return False
    if box.width < settings.OBSTACLE_MIN_WIDTH_FRACTION * picture_width:
        return False
    # A standing cone is taller than wide; a lying one is wider than tall.
    if box.height <= 0 or box.width < settings.OBSTACLE_MIN_WIDTH_RATIO * box.height:
        return False
    # A far row of standing cones is sometimes boxed as one wide object, as
    # well as cone by cone. Such a box holds the centre of a clearly smaller
    # cone. A second box around the same cone is about as large, and must
    # not hide it: the model often gives two boxes for one cone.
    for other in boxes_of_picture:
        if other is box or other.kind != "cone":
            continue
        x, y = other.centre
        inside = box.left <= x <= box.right and box.top <= y <= box.bottom
        if inside and other.width < box.width / 2:
            return False
    return True


def lying_cones(objects):
    """Find the knocked-over cones in a video. Returns a list of "obstacle" Stretches.

    Each picture with a lying cone is a sighting. Sightings close together
    are one obstacle; it starts at the first and ends a little after the last.
    """
    sightings = [
        time for time, boxes in objects.pictures
        if any(is_lying_cone(box, boxes, objects.analysis_width) for box in boxes)
    ]
    stretches = []
    start = last = None
    for time in sightings:
        if start is not None and time - last > settings.OBSTACLE_MERGE_SECONDS:
            stretches.append(Stretch(start, last + settings.OBSTACLE_TAIL_SECONDS, settings.OBSTACLE_LABEL))
            start = None
        if start is None:
            start = time
        last = time
    if start is not None:
        stretches.append(Stretch(start, last + settings.OBSTACLE_TAIL_SECONDS, settings.OBSTACLE_LABEL))
    return stretches


# Every rule on the objects of a video. A new rule is added to this list.
OBJECT_RULES = [lying_cones]


def events_of_objects(objects):
    """The events every rule finds in the objects of a video.

    objects: the Objects of the video, or None when there are none (then
    there are no events from objects).
    """
    if objects is None:
        return []
    events = []
    for rule in OBJECT_RULES:
        events += rule(objects)
    return events
