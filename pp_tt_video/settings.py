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

# ffmpeg decodes the video; ffprobe reads its properties (size, length, ...).
FFMPEG = EXECUTABLES_FOLDER / "ffmpeg.exe"
FFPROBE = EXECUTABLES_FOLDER / "ffprobe.exe"

# The video is analysed in a reduced form: smaller pictures, fewer of them.
# The width is fixed here; the height follows from the shape of the video.
ANALYSIS_WIDTH = 1280
ANALYSIS_FRAMES_PER_SECOND = 5

# Decode the video on the Nvidia graphics card. Measured on an RTX 3060 Ti:
# about 7 times faster than real time, against about 2 times on the processor.
# Set to False on a PC without an Nvidia card.
USE_GRAPHICS_CARD = True

# --- Finding other cars ------------------------------------------------------

# What the detection model calls the things we treat as "another car".
VEHICLE_NAMES = {"car", "truck", "bus"}

# The model gives every find a confidence between 0 and 1. Finds below this
# value are thrown away at once.
MIN_DETECTION_CONFIDENCE = 0.5

# A find wider than this part of the picture is the own cockpit, not a car.
MAX_CAR_WIDTH_FRACTION = 0.45

# How many pictures are handed to the model at once. More is a little faster
# but needs more memory on the graphics card.
DETECTION_BATCH_SIZE = 4

# --- Following cars from picture to picture ----------------------------------

# A car that is not seen for longer than this has gone; its track is closed.
TRACK_MAX_GAP_SECONDS = 1.0

# Between two pictures a car may move at most this many of its own widths
# and still count as the same car.
TRACK_MAX_JUMP_IN_WIDTHS = 1.5

# Between two pictures a car's height may change at most by this factor.
TRACK_MAX_SIZE_CHANGE = 2.5

# --- Turning car tracks into events ------------------------------------------
#
# How large another car looks tells how near it is. Its height in the picture
# is used, not its width: a car seen from the side is much wider than one seen
# from behind, but about as tall. Heights are given as a part of the picture's
# height, so they do not depend on the analysis size.

# A track only counts as a real car if the model was this sure at least once.
CAR_MIN_CONFIDENCE = 0.9

# A car taller than this is right next to us: we are passing it, or it us.
# (0.11 of the picture is about 80 of 720 pixels.)
PASSING_CAR_HEIGHT = 0.11

# A car ahead that is taller than this is close enough to hold us up.
CLOSE_CAR_HEIGHT = 0.0625

# "held up" is only marked after being close behind a car for this long.
HELD_UP_MIN_SECONDS = 3

# "overtaken" starts this long before the other car first appears, so that
# the whole process is covered.
OVERTAKEN_LEAD_SECONDS = 3

# An overtake is taken to start where the other car reached this part of its
# final size, and "overtaken" to end where it has shrunk to this part.
PASS_START_PART_OF_PEAK = 0.55
PASS_END_PART_OF_PEAK = 0.5

# --- Motion sensors -----------------------------------------------------------

# Tells ExifTool which sensor values to print, and how (used by sensors.py).
SENSOR_TEMPLATE = PROJECT_FOLDER / "pp_tt_video" / "sensors.fmt"

# Every sensor measurement has three numbers, one per axis of the camera.
# Which number means what depends on how the camera is mounted. These values
# are for a camera standing upright and looking forward (number 0, 1 or 2).
ACCELERATION_AXIS_DOWN = 0      # reads about -9.8 when standing still: gravity
ACCELERATION_AXIS_SIDEWAYS = 1  # cornering force
ACCELERATION_AXIS_FORWARD = 2   # plus when braking, minus when accelerating
ROTATION_AXIS_TURNING = 0       # how fast the car turns left or right

# --- Warm up and cooling: is the car driven at pace? ---------------------------
#
# All forces are in m/s². For comparison: 9.8 m/s² is the pull of gravity.

# The braking and accelerating force is averaged over this many seconds.
PACE_WINDOW_SECONDS = 40

# The car is at pace while that average is at least this much. In the
# examples it is 1.5 to 2.7 at pace and 0.4 to 1.3 on slow laps.
PACE_MIN_EFFORT = 1.3

# Driving at pace must last at least this long to count.
PACE_MIN_SECONDS = 20

# Braking or accelerating this hard marks the exact first and last moment
# at pace.
PACE_HARD_FORCE = 3.0

# A warm up or cooling shorter than this is not reported: the video then
# simply starts or ends at pace.
PACE_MIN_EDGE_SECONDS = 10

# The labels this step writes. They must be in the event type list.
WARM_UP_LABEL = "warm up"
COOLING_LABEL = "cooling"

# --- Out of session, and crash ---------------------------------------------------
#
# "out of session" is the time before the car joins the track and after it
# has left it: paddock, pit lane, parking.

# What the camera's GPS reports as "fix" when it knows its position.
GPS_FIX_VALUES = {"2", "3"}

# At the start of the video the car counts as not yet on the track when it
# is slower than this (km/h). The slowest corners of a track are faster.
SESSION_SLOW_SPEED = 45

# The speed is looked for in this many seconds at the start of the video.
SESSION_START_LOOK_SECONDS = 15

# Without GPS the speed is worked out in a turn (cornering force divided by
# turning rate). That is only trusted when the car turns at least this fast
# (radians per second).
SESSION_MIN_TURNING_FOR_SPEED = 0.3

# Joining the track, the car accelerates at least this hard (m/s²) ...
SESSION_JOIN_FORCE = 2.0

# ... and the session starts when the acceleration has dropped below this.
SESSION_JOIN_END_FORCE = 1.0

# The car stands still when it shakes less than this (m/s²). Driving, even
# slowly, shakes it more.
STANDSTILL_MAX_SHAKE = 1.0

# The video must end with at least this many seconds of standing still for
# the car to count as parked.
STANDSTILL_MIN_SECONDS = 3

# A corner of the track has at least this much cornering force (m/s²). The
# turns of a pit lane and paddock, taken slowly, have less.
SESSION_TRACK_CORNER_FORCE = 5.0

# "out of session" starts this long after the last corner of the track.
SESSION_LEAVE_SECONDS = 10

# If the car stands still sooner than this after it stopped driving at pace,
# there was no cool-down lap: something broke or it hit something.
CRASH_MAX_SECONDS = 60

OUT_OF_SESSION_LABEL = "out of session"
CRASH_LABEL = "crash"

# --- Sliding -------------------------------------------------------------------
#
# A slide is recognised by its catch: the car is still pushed sideways hard,
# but turns against the corner. The rule relies on the cornering force and
# the turning rate having the same sign in a normal corner, which is so for
# the axes set above.

# The cornering force and the turning rate are looked at this often.
SLIDE_SAMPLES_PER_SECOND = 10

# The cornering force must be at least this high (m/s²).
SLIDE_MIN_CORNERING_FORCE = 7.0

# The car must have turned into the corner at least this fast (radians per
# second; 0.4 is about 23 degrees per second) ...
SLIDE_MIN_TURNING_BEFORE = 0.4

# ... at most this long before it turns against the corner.
SLIDE_LOOK_BACK_SECONDS = 1.0

# The car must turn against the corner in at least this many samples.
SLIDE_MIN_SAMPLES = 2

# Samples closer together than this belong to the same catch.
SLIDE_GROUP_GAP_SECONDS = 1.0

# "sliding" starts this long before the catch and ends this long after it.
SLIDE_LEAD_SECONDS = 2.0
SLIDE_TAIL_SECONDS = 0.0

SLIDING_LABEL = "sliding"

# --- Offtrack ------------------------------------------------------------------

# The shaking of the car is measured this often.
OFFTRACK_SAMPLES_PER_SECOND = 5

# Off the tarmac the up-and-down force jumps around at least this much
# (m/s²). On the track it is about 2.5, on a kerb 5 to 6.
OFFTRACK_MIN_SHAKE = 7.0

# The shaking must last at least this long.
OFFTRACK_MIN_SECONDS = 1.0

# "offtrack" starts this long before the shaking and ends this long after.
OFFTRACK_LEAD_SECONDS = 1.5
OFFTRACK_TAIL_SECONDS = 0.5

OFFTRACK_LABEL = "offtrack"

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
