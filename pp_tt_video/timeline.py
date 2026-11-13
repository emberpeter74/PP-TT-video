"""Builds the timeline for the events file from labelled stretches of time.

The detectors report stretches such as "overtaking from 120.2 s to 122.4 s".
The events file wants whole seconds, one line per change, "clear" wherever
nothing happens, and combined labels where stretches overlap.
"""

from pp_tt_video import settings
from pp_tt_video.events import Event


def build_timeline(stretches, duration_seconds, label_order=None):
    """Turn stretches into a list of Event covering the whole video.

    label_order: the labels in the order they should be written when several
    apply at once (the order of the event type list).
    """
    label_order = list(label_order or [])

    def position(label):
        return label_order.index(label) if label in label_order else len(label_order)

    # Work out, for every whole second, which labels apply.
    total_seconds = max(1, int(duration_seconds))
    labels_per_second = [set() for _ in range(total_seconds)]
    for stretch in stretches:
        first = max(0, int(round(stretch.start)))
        last = min(total_seconds - 1, int(round(stretch.end)))
        # A very short stretch still gets its one second.
        for second in range(first, max(first, last) + 1):
            if second < total_seconds:
                labels_per_second[second].add(stretch.label)

    # Write a line only where the labels change.
    timeline = []
    previous = None
    for second, labels in enumerate(labels_per_second):
        labels = tuple(sorted(labels, key=position)) or (settings.CLEAR_LABEL,)
        if labels != previous:
            timeline.append(Event(second, labels))
            previous = labels
    return timeline
