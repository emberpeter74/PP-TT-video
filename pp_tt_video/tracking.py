"""Step 6, part 2: follow each car from picture to picture.

The detector looks at every picture on its own. It says "there is a car
here", but not "this is the same car as a moment ago". The tracker makes that
link, so that every car gets a history: where it was and how large it looked
at each moment. That history is called a track.
"""

from dataclasses import dataclass, field

from pp_tt_video import settings


@dataclass
class Sighting:
    """One car seen in one picture."""

    time_seconds: float
    box: object   # a CarBox


@dataclass
class Track:
    """The history of one car: all its sightings, in order of time."""

    sightings: list = field(default_factory=list)

    @property
    def start(self):
        return self.sightings[0].time_seconds

    @property
    def end(self):
        return self.sightings[-1].time_seconds

    @property
    def duration(self):
        return self.end - self.start

    @property
    def best_confidence(self):
        return max(sighting.box.confidence for sighting in self.sightings)

    def widths(self):
        """The car's width in the picture at each sighting."""
        return [sighting.box.width for sighting in self.sightings]


def overlap(box_a, box_b):
    """How much two boxes cover each other, from 0 (not at all) to 1 (same box).

    It is the shared area divided by the area both cover together.
    """
    shared_width = min(box_a.right, box_b.right) - max(box_a.left, box_b.left)
    shared_height = min(box_a.bottom, box_b.bottom) - max(box_a.top, box_b.top)
    if shared_width <= 0 or shared_height <= 0:
        return 0.0
    shared = shared_width * shared_height
    together = box_a.width * box_a.height + box_b.width * box_b.height - shared
    return shared / together


def closeness(last_box, new_box):
    """How well a new box fits the last known box of a track, from 0 to 1.

    Boxes that overlap fit well. A car that moved quickly may not overlap its
    old box at all, so boxes that are near each other and of similar size
    also count, a little less.
    """
    # A car cannot become several times taller or shorter from one picture to
    # the next. If it seems to, the new box belongs to something else.
    taller, shorter = max(last_box.height, new_box.height), min(last_box.height, new_box.height)
    if taller > shorter * settings.TRACK_MAX_SIZE_CHANGE:
        return 0.0

    score = overlap(last_box, new_box)
    if score > 0:
        return 0.5 + score / 2
    # Distance between the centres, measured in car widths.
    size = max(last_box.width, new_box.width)
    distance = max(abs(last_box.centre[0] - new_box.centre[0]), abs(last_box.centre[1] - new_box.centre[1]))
    similar_size = min(last_box.width, new_box.width) / size
    if distance <= settings.TRACK_MAX_JUMP_IN_WIDTHS * size and similar_size >= 0.5:
        return 0.5 * (1 - distance / (settings.TRACK_MAX_JUMP_IN_WIDTHS * size)) * similar_size
    return 0.0


def part_inside(box, other):
    """Which part of a box lies inside another box, from 0 to 1."""
    shared_width = min(box.right, other.right) - max(box.left, other.left)
    shared_height = min(box.bottom, other.bottom) - max(box.top, other.top)
    if shared_width <= 0 or shared_height <= 0:
        return 0.0
    return shared_width * shared_height / (box.width * box.height)


def drop_double_boxes(boxes):
    """The model sometimes draws several boxes around one car. Keep the surest.

    This happens most when a car is only partly in the picture: the model
    then boxes the whole car and, again, a part of it.
    """
    kept = []
    for box in sorted(boxes, key=lambda b: b.confidence, reverse=True):
        if all(part_inside(box, other) < 0.7 and part_inside(other, box) < 0.7 for other in kept):
            kept.append(box)
    return kept


class Tracker:
    """Builds tracks from the detections of one picture after another."""

    def __init__(self):
        self.open_tracks = []       # cars that were seen recently
        self.finished_tracks = []   # cars that have gone

    def add_picture(self, time_seconds, boxes):
        """Take in the cars found in the next picture."""
        # Cars not seen for a while have gone: close their tracks.
        still_open = []
        for track in self.open_tracks:
            if time_seconds - track.end > settings.TRACK_MAX_GAP_SECONDS:
                self.finished_tracks.append(track)
            else:
                still_open.append(track)
        self.open_tracks = still_open

        # Rate every pairing of an open track with a new box, best first.
        boxes = drop_double_boxes(boxes)
        pairings = []
        for track in self.open_tracks:
            for box in boxes:
                score = closeness(track.sightings[-1].box, box)
                if score > 0:
                    pairings.append((score, id(track), id(box), track, box))
        pairings.sort(key=lambda pairing: pairing[0], reverse=True)

        # Hand out the boxes: each track gets at most one box, and each box
        # goes to at most one track.
        used_tracks, used_boxes = set(), set()
        for score, track_id, box_id, track, box in pairings:
            if track_id in used_tracks or box_id in used_boxes:
                continue
            track.sightings.append(Sighting(time_seconds, box))
            used_tracks.add(track_id)
            used_boxes.add(box_id)

        # A box that fits no track is a car seen for the first time.
        for box in boxes:
            if id(box) not in used_boxes:
                self.open_tracks.append(Track([Sighting(time_seconds, box)]))

    def finish(self):
        """Close all tracks at the end of the video and return every track."""
        self.finished_tracks.extend(self.open_tracks)
        self.open_tracks = []
        return sorted(self.finished_tracks, key=lambda track: track.start)
