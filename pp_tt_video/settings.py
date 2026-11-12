"""Settings: every value that may need changing later lives in this one file.

The rest of the code reads these names and never contains the values itself.
"""

from pathlib import Path

# The project folder is the folder that contains the "pp_tt_video" folder.
# __file__ is the path of this file; .parent goes one folder up.
PROJECT_FOLDER = Path(__file__).resolve().parent.parent

# External tools are copied by hand into this folder (it is not in Git).
EXECUTABLES_FOLDER = PROJECT_FOLDER / "executables"

# ExifTool reads the GPS data that the GoPro stores inside the video file.
EXIFTOOL = EXECUTABLES_FOLDER / "exiftool.exe"

# ExifTool's template that describes what a GPX file looks like.
GPX_TEMPLATE = EXECUTABLES_FOLDER / "gpx.fmt"

# File extensions that count as video files (compared in lower case).
VIDEO_EXTENSIONS = {".mp4"}

# The list of event types: one line per type, with a label and a description.
# Adding a type means adding a line to this file. Later it becomes a database.
EVENT_TYPES_FILE = PROJECT_FOLDER / "event_types.csv"

# The label for "nothing is happening". It is the background, not an event.
CLEAR_LABEL = "clear"

# The label for something unusual that fits no type in the list.
OTHER_EVENT_LABEL = "other event"

# How far a detected time may be from the hand-marked time and still count
# as correct, in seconds.
TIME_TOLERANCE_SECONDS = 5
