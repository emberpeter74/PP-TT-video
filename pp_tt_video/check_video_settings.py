"""Settings of the check video: what is drawn, and how.

The check video is made with --check-video. It is the video in reduced size
with the module's work drawn over it. Change a value here, delete the
check video (name-check.mp4) and run the module again with --check-video:
the detections are saved, so only the drawing is done again.

The thresholds of the rules are NOT here. They stay in settings.py and in
the driver and car profile, so the check video always shows the values the
rules really use.
"""

# --- The video itself -------------------------------------------------------------

# How many pictures per second the check video has. 30 is as smooth as the
# original. A lower value is quicker to make; 5 shows exactly the pictures
# the car detection looked at.
FRAMES_PER_SECOND = 30

# True: the sound of the original video is copied into the check video.
# Tyre noise and kerbs help to judge a moment. False: no sound.
KEEP_SOUND = True

# How strongly the check video is compressed. Lower is a better picture and a
# larger file. 18 is very good, 28 is good enough to check things, 35 is rough.
VIDEO_QUALITY = 28

# --- The car boxes ----------------------------------------------------------------

# True: a box is drawn around every car the rules work with. Its colour
# shows how the car rules see the car at that moment:
#   blue   far away
#   amber  close: counts towards "held up"
#   red    passing: right next to us, counts towards "overtaking" or "overtaken"
SHOW_KEPT_BOXES = True

# True: next to each box its details are written, for example
# "car 3  0.87  h 0.11":
#   car 3   the number of the car; one car keeps its number while it is followed
#   0.87    how sure the model is that this is a vehicle, from 0 to 1
#   h 0.11  how tall the car is, as a part of the picture's height. This is
#           the value the car rules decide on.
SHOW_BOX_DETAILS = True

# True: the boxes that were thrown away are drawn too, thin and grey, with
# the reason:
#   too wide            wider than a car can be: the own cockpit
#   double              a second box around a car that has a box already
#   never sure enough   the model was never sure enough that this is a car,
#                       so the car rules skip it (written with its car number)
# These are what the rules never see. If a real car is among them, that is
# why an event was missed.
SHOW_DROPPED_BOXES = True

# --- The events -------------------------------------------------------------------

# True: the labels that apply at this moment are written across the top,
# exactly as they go into the events file.
SHOW_EVENTS = True

# True: events that were found and then thrown away are written in grey
# under the event line, with the reason, for example
# "dropped: sliding (outside the part at pace)". Events are only kept in the
# part of the video that is driven at pace.
SHOW_DROPPED_EVENTS = True

# --- The sensor strip ---------------------------------------------------------------

# True: below the picture a strip shows the motion sensor values the rules
# look at, moving along with the video, with each rule's threshold drawn as
# a dashed line. False: no strip; the check video is as tall as the picture.
SHOW_STRIP = True

# Which charts the strip has, from top to bottom. Leave one out to hide it.
#   "pace"      braking and accelerating force (yellow) and its average
#               over time, the "effort" (blue). Thresholds: the effort
#               from which the car counts as at pace, and the force that
#               marks the first and last moment at pace.
#   "sliding"   the cornering force. A slide is only looked for in corners
#               above the threshold. Marks along the top: the moments the
#               car turned against the corner (the catch of a slide).
#   "turning"   how fast the car turns. Goes with "sliding": before a catch
#               the car must have turned into the corner faster than the
#               threshold.
#   "offtrack"  how hard the car shakes up and down (thick yellow line), with
#               its threshold. Only slow shaking is in it: a fast vibration
#               of the camera is smoothed away first, as the rule does.
#               The thin green line is the shake without smoothing, for
#               information: where it is high and the yellow line is not,
#               the camera vibrates. It is often beyond the chart's scale
#               and then runs along the top edge.
STRIP_CHARTS = ["pace", "sliding", "turning", "offtrack"]

# True: the rules' thresholds are drawn as dashed lines, with their value.
SHOW_THRESHOLDS = True

# How many seconds the strip shows before and after the moment of the
# picture. The vertical line marks "now".
STRIP_SECONDS_BEFORE = 8
STRIP_SECONDS_AFTER = 2

# The height of the strip in pixels, shared by its charts (for a picture
# 1280 pixels wide; a smaller picture gets a smaller strip).
STRIP_HEIGHT = 320

# --- The overview picture -----------------------------------------------------------

# True: besides the check video, one picture of the whole video is written
# (name-overview.png), with time running from left to right:
#   pace        the braking and accelerating force (thin) and the effort
#               (thick), with the pace rule's thresholds, in front of
#               coloured bands: out of session, warm up, at pace, cooling,
#               crash
#   too brief   where the effort was above its threshold, but for too short
#               a time to count as driving at pace
#   one row per event: filled bars are events that were kept, outlines are
#               events that were found and thrown away
#   cars        every car that was followed; an outline is a car the model
#               was never sure of, which the car rules skip
# It shows what a few seconds of video cannot: why a whole video came out
# as warm up, or how many offtracks there are and where.
WRITE_OVERVIEW = True
