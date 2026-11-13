"""A stretch of time with one label: what every detector reports."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Stretch:
    """A stretch of time with one label."""

    start: float   # seconds since the beginning of the video
    end: float
    label: str
