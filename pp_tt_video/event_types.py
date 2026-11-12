"""Reads the list of event types.

This is the only place that knows the list is a CSV file. When the list moves
to a database, only this file has to change.
"""

import csv

from pp_tt_video import settings


def load_event_types(csv_path=None):
    """Return the event types as a dictionary: label -> description."""
    csv_path = csv_path or settings.EVENT_TYPES_FILE
    event_types = {}
    # newline="" is what the csv module asks for; utf-8 allows accented letters.
    with open(csv_path, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            label = row["label"].strip().lower()
            if label:
                event_types[label] = row["description"].strip()
    return event_types


def known_labels(csv_path=None):
    """Return every label that may appear in an events file."""
    labels = set(load_event_types(csv_path))
    labels.add(settings.OTHER_EVENT_LABEL)
    return labels
