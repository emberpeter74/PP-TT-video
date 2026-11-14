"""Driver and car profiles: what counts as quick for one driver in one car.

The values in settings.py were set on one driver's own driving. A gentler
driver never reaches them, so to the rules that driver is never at pace.
A profile is a small text file that replaces some of those values while
that driver's videos are processed.

A profile file looks like this (the format is called TOML):

    # Average braking or accelerating force from which the car is at pace.
    PACE_MIN_EFFORT = 0.51

The values are put into the settings module itself while a video is
processed, and the built-in values are put back afterwards. The rules read
settings.NAME at the moment they run, so they use the profile's value
without knowing about profiles.
"""

import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from pp_tt_video import settings

# Every name a profile may set, and what the value depends on. make_profile
# scales the "driver" values; the others are changed by hand if needed.
PROFILE_VALUES = {
    "PACE_MIN_EFFORT": "driver braking",
    "PACE_HARD_FORCE": "driver braking",
    "SLIDE_MIN_CORNERING_FORCE": "driver cornering",
    "SESSION_TRACK_CORNER_FORCE": "driver cornering",
    "OFFTRACK_MIN_SHAKE": "car",
    "STANDSTILL_MAX_SHAKE": "car",
    "PASSING_CAR_HEIGHT": "camera",
    "CLOSE_CAR_HEIGHT": "camera",
    "MAX_CAR_WIDTH_FRACTION": "camera",
}


class ProfileError(Exception):
    """Raised when a profile file is missing or cannot be used."""


@dataclass(frozen=True)
class Profile:
    """A profile: its name, the file it came from, and the values it sets."""

    name: str
    path: Path | None     # None for the built-in values
    values: dict          # setting name -> number

    @property
    def description(self):
        """A short text for the user, for example "son (son.toml)"."""
        if self.path is None:
            return self.name
        return f"{self.name} ({self.path.name})"


# No profile: every setting keeps the value written in settings.py.
BUILT_IN = Profile("built-in values", None, {})


def is_number(value):
    # True and False count as numbers in Python (1 and 0); a profile value
    # written as true or false is a mistake, so they are refused.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load_profile(path):
    """Read a profile file and return a Profile.

    Raises ProfileError with a message that names the file and the problem.
    A mistake must stop the run for that video: if a misspelt name were
    ignored, the built-in value would be used without anyone noticing.
    """
    path = Path(path)
    try:
        # "utf-8-sig" also reads files that start with a BOM: three invisible
        # bytes that Windows Notepad may put at the start of a text file.
        text = path.read_bytes().decode("utf-8-sig")
    except FileNotFoundError:
        raise ProfileError(f"Profile file not found: {path}")
    except UnicodeDecodeError:
        raise ProfileError(f"Profile file {path.name} is not a text file")
    try:
        # tomllib is part of Python (since version 3.11): it reads TOML files.
        content = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ProfileError(f"Profile file {path.name} cannot be read: {error}")

    values = {}
    for name, value in content.items():
        if name not in PROFILE_VALUES:
            raise ProfileError(f"Profile file {path.name}: {name} is not a value a profile can set")
        if not is_number(value):
            raise ProfileError(f"Profile file {path.name}: {name} must be a number, not {value!r}")
        values[name] = float(value)

    # A profile kept in a driver's video folder is always called profile.toml,
    # so it is named after its folder; a named profile after its file.
    if path.name == settings.PROFILE_FILE_NAME:
        name = path.resolve().parent.name
    else:
        name = path.stem
    return Profile(name, path, values)


@contextmanager
def using_profile(profile):
    """Apply a profile's values while the block inside "with" runs.

    A context manager is used with "with": the code before "yield" runs when
    the block starts, the code after it when the block ends. Because it is
    in "finally", the built-in values are put back even after an error.

        with using_profile(profile):
            ...   # here the rules see the profile's values
    """
    old_values = {name: getattr(settings, name) for name in profile.values}
    try:
        for name, value in profile.values.items():
            setattr(settings, name, value)
        yield profile
    finally:
        for name, value in old_values.items():
            setattr(settings, name, value)
