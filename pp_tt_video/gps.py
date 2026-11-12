"""Step 2: extract the GPS track from a GoPro video into a GPX file.

The GPS data is written exactly as ExifTool delivers it. Nothing is removed,
corrected or filtered (see BUSINESS_SPEC.md, section 6.1).
"""

import subprocess
from pathlib import Path

from pp_tt_video import settings


class GpsExtractionError(Exception):
    """Raised when the GPS track could not be extracted from a video."""


def gpx_path_for(video_path, output_folder=None):
    """Return where the GPX file for a video belongs.

    Naming rule: "something.mp4" gives "something.gpx". The file goes next to
    the video, unless another output folder is given.
    """
    video_path = Path(video_path)
    folder = Path(output_folder) if output_folder else video_path.parent
    # .stem is the file name without its extension.
    return folder / (video_path.stem + ".gpx")


def extract_gps(video_path, output_folder=None, overwrite=False):
    """Extract the GPS track of one video and return the path of the GPX file.

    An existing GPX file is left alone unless overwrite is True.
    """
    video_path = Path(video_path)
    gpx_path = gpx_path_for(video_path, output_folder)

    if not video_path.is_file():
        raise GpsExtractionError(f"Video file not found: {video_path}")
    if gpx_path.exists() and not overwrite:
        raise FileExistsError(f"GPX file already exists: {gpx_path}")

    # The same command the user ran by hand:
    #   exiftool -a "-gps*" -p gpx.fmt -ee video.mp4 > video.gpx
    command = [
        str(settings.EXIFTOOL),
        "-a",       # allow duplicate tags, so every GPS point is kept
        "-gps*",    # only the GPS tags
        "-p", str(settings.GPX_TEMPLATE),  # print them in GPX layout
        "-ee",      # read the data embedded along the whole video
        str(video_path),
    ]

    # Run ExifTool and collect what it prints. The output is kept as raw
    # bytes, not text, so nothing is changed on the way to the file.
    try:
        result = subprocess.run(command, capture_output=True)
    except FileNotFoundError:
        raise GpsExtractionError(f"ExifTool not found: {settings.EXIFTOOL}")

    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise GpsExtractionError(f"ExifTool failed for {video_path.name}: {message}")
    # For a file without GPS data ExifTool still prints the GPX frame, only
    # with no track points in it. Such an empty track is not written.
    if b"<trkpt" not in result.stdout:
        raise GpsExtractionError(f"No GPS data found in {video_path.name}")

    gpx_path.write_bytes(result.stdout)
    return gpx_path
