"""Writes the check video: the video in reduced size, with the module's
work drawn over every picture.

The video is read once more, in the size the detection used, and every
picture goes through draw.py before it is written to the new file. What is
drawn comes from an Explanation (explain.py); what is shown of it is chosen
in check_video_settings.py.
"""

from pathlib import Path

from PIL import Image

from pp_tt_video import check_video_settings
from pp_tt_video.draw import draw_picture, full_picture_size
from pp_tt_video.video import VideoWriter, analysis_size, read_frames, read_video_info


def check_video_path_for(video_path, output_folder=None):
    """Return where the check video for a video belongs.

    Naming rule: "something.mp4" gives "something-check.mp4".
    """
    video_path = Path(video_path)
    folder = Path(output_folder) if output_folder else video_path.parent
    return folder / (video_path.stem + "-check.mp4")


def write_check_video(video_path, output_path, explanation, profile_name, on_progress=None):
    """Draw the explanation over the video and write the result.

    profile_name: the driver and car profile in force, written on every picture.
    on_progress(part), if given, is called with the part done so far (0 to 1).
    May raise VideoError.
    """
    info = read_video_info(video_path)
    frames_per_second = check_video_settings.FRAMES_PER_SECOND
    width, height = full_picture_size(*analysis_size(info))
    sound_from = video_path if check_video_settings.KEEP_SOUND else None

    with VideoWriter(output_path, width, height, frames_per_second, sound_from=sound_from,
                     quality=check_video_settings.VIDEO_QUALITY) as writer:
        for frame in read_frames(video_path, frames_per_second=frames_per_second):
            # From plain bytes to a picture Pillow can draw on, and back.
            image = Image.frombytes("RGB", (frame.width, frame.height), frame.pixels)
            drawn = draw_picture(image, frame.time_seconds, explanation, profile_name)
            writer.write(drawn.tobytes())
            if on_progress and info.duration_seconds:
                on_progress(min(1.0, frame.time_seconds / info.duration_seconds))
    if on_progress:
        on_progress(1.0)
