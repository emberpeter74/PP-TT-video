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

# --- The events -------------------------------------------------------------------

# True: the labels that apply at this moment are written across the top,
# exactly as they go into the events file.
SHOW_EVENTS = True
