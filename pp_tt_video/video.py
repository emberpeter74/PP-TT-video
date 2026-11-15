"""Step 5: read a video in reduced form.

The camera records 5312x2988 pictures, 30 per second. That is far more than
the analysis needs, so ffmpeg shrinks the pictures and passes on only a few
per second. The reduced pictures arrive here one by one.
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pp_tt_video import settings


class VideoError(Exception):
    """Raised when a video cannot be read."""


@dataclass
class VideoInfo:
    """The basic properties of a video file."""

    width: int                # in pixels
    height: int               # in pixels
    frames_per_second: float
    duration_seconds: float
    codec: str                # how the video is compressed, for example "hevc"


@dataclass
class Frame:
    """One reduced picture from the video."""

    time_seconds: float   # position in the video
    width: int
    height: int
    pixels: bytes         # 3 bytes per pixel (red, green, blue), row by row


# Decoders that run on an Nvidia graphics card, per compression format.
GRAPHICS_CARD_DECODERS = {"hevc": "hevc_cuvid", "h264": "h264_cuvid"}


def read_video_info(video_path):
    """Ask ffprobe for the size, frame rate and length of a video."""
    video_path = Path(video_path)
    if not video_path.is_file():
        raise VideoError(f"Video file not found: {video_path}")
    command = [
        str(settings.FFPROBE),
        "-v", "error",
        "-select_streams", "v:0",   # the first video track
        "-show_entries", "stream=width,height,avg_frame_rate,codec_name:format=duration",
        "-of", "json",              # answer in JSON, which Python can read directly
        str(video_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True)
    except FileNotFoundError:
        raise VideoError(f"ffprobe not found: {settings.FFPROBE}")
    if result.returncode != 0:
        raise VideoError(f"ffprobe could not read {video_path.name}")

    answer = json.loads(result.stdout)
    if not answer.get("streams"):
        raise VideoError(f"No video track found in {video_path.name}")
    stream = answer["streams"][0]
    # The frame rate comes as a fraction, for example "30000/1001" (= 29.97).
    numerator, _, denominator = stream["avg_frame_rate"].partition("/")
    return VideoInfo(
        width=int(stream["width"]),
        height=int(stream["height"]),
        frames_per_second=float(numerator) / float(denominator or 1),
        duration_seconds=float(answer["format"]["duration"]),
        codec=stream["codec_name"],
    )


def analysis_size(info, width=None):
    """Return the (width, height) of the reduced pictures.

    The height keeps the shape of the original video. It is rounded to an
    even number, because video tools cannot handle odd sizes.
    """
    width = width or settings.ANALYSIS_WIDTH
    height = round(width * info.height / info.width / 2) * 2
    return width, height


def read_frames(video_path, start_seconds=0, duration_seconds=None,
                frames_per_second=None, width=None, use_graphics_card=None):
    """Yield the reduced pictures of a video one by one, as Frame objects.

    This is a "generator": it hands out one frame at a time instead of
    loading the whole video into memory. Use it in a for loop:

        for frame in read_frames("video.mp4"):
            ...
    """
    video_path = Path(video_path)
    info = read_video_info(video_path)
    frames_per_second = frames_per_second or settings.ANALYSIS_FRAMES_PER_SECOND
    width, height = analysis_size(info, width)
    if use_graphics_card is None:
        use_graphics_card = settings.USE_GRAPHICS_CARD
    decoder = GRAPHICS_CARD_DECODERS.get(info.codec) if use_graphics_card else None

    command = [str(settings.FFMPEG), "-hide_banner", "-loglevel", "error", "-nostdin"]
    if decoder:
        # Decode and shrink on the graphics card.
        command += ["-hwaccel", "cuda", "-c:v", decoder, "-resize", f"{width}x{height}"]
    if start_seconds:
        command += ["-ss", str(start_seconds)]
    command += ["-i", str(video_path)]
    if duration_seconds is not None:
        command += ["-t", str(duration_seconds)]
    filters = f"fps={frames_per_second}"
    if not decoder:
        filters += f",scale={width}:{height}"   # shrink on the processor instead
    command += [
        "-vf", filters,
        "-an",                 # no sound
        "-f", "rawvideo",      # plain pixels, no file format around them
        "-pix_fmt", "rgb24",   # 3 bytes per pixel: red, green, blue
        "-",                   # write to this program instead of to a file
    ]

    bytes_per_frame = width * height * 3
    # ffmpeg's error messages go to a temporary file, the pictures come
    # through a "pipe": a direct line from ffmpeg to this program.
    with tempfile.TemporaryFile() as error_file:
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_file)
        except FileNotFoundError:
            raise VideoError(f"ffmpeg not found: {settings.FFMPEG}")
        frame_number = 0
        try:
            while True:
                pixels = process.stdout.read(bytes_per_frame)
                if len(pixels) < bytes_per_frame:
                    break   # the video has ended
                yield Frame(start_seconds + frame_number / frames_per_second, width, height, pixels)
                frame_number += 1
            process.wait()
        finally:
            # Also runs when the caller stops early: shut ffmpeg down.
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()

        if process.returncode != 0 and frame_number == 0:
            error_file.seek(0)
            message = error_file.read().decode("utf-8", errors="replace").strip()
            hint = " (if this PC has no Nvidia card, set USE_GRAPHICS_CARD to False)" if decoder else ""
            raise VideoError(f"ffmpeg could not decode {video_path.name}{hint}: {message[-500:]}")


class VideoWriter:
    """Writes pictures to a video file, one after the other.

    Used with "with", so the file is always finished properly:

        with VideoWriter("out.mp4", 1280, 720, 30) as writer:
            writer.write(pixels)   # 3 bytes per pixel, row by row, like Frame.pixels

    The pictures are handed to ffmpeg through a pipe, and ffmpeg compresses
    them as H.264, a format every video player understands.

    The video is written under a temporary name and renamed when it is
    complete. A run that is interrupted, or fails, leaves no file behind
    that the next run could take for a finished video.
    """

    def __init__(self, path, width, height, frames_per_second, sound_from=None,
                 quality=28, use_graphics_card=None):
        """
        sound_from: a video file whose sound is copied into the new video.
        quality:    how strongly the video is compressed. Lower is better and
                    larger; 18 is very good, 28 is good enough to check things.
        """
        self.path = Path(path)
        # ffmpeg picks the file format from the ending, so the temporary
        # name must end in .mp4 too.
        self.part = self.path.with_name(self.path.stem + ".part" + self.path.suffix)
        self.bytes_per_picture = width * height * 3
        if use_graphics_card is None:
            use_graphics_card = settings.USE_GRAPHICS_CARD

        command = [
            str(settings.FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24",          # what comes through the pipe:
            "-s", f"{width}x{height}",                      # plain pixels of this size,
            "-r", str(frames_per_second),                   # this many per second
            "-i", "-",                                      # "-" = read from the pipe
        ]
        if sound_from:
            command += ["-i", str(sound_from)]
        command += ["-map", "0:v"]                          # the picture: from the pipe
        if sound_from:
            # The first sound track of the other file, copied as it is. The
            # "?" means: carry on without sound if that file has none.
            command += ["-map", "1:a:0?", "-c:a", "copy", "-shortest"]
        if use_graphics_card:
            command += ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", str(quality), "-b:v", "0"]
        else:
            command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(quality)]
        command += ["-pix_fmt", "yuv420p", str(self.part)]  # the colour format players expect
        self.command = command
        self.process = None
        self.error_file = None

    def __enter__(self):
        # ffmpeg's error messages go to a temporary file.
        self.error_file = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stderr=self.error_file)
        except FileNotFoundError:
            self.error_file.close()
            raise VideoError(f"ffmpeg not found: {settings.FFMPEG}")
        return self

    def write(self, pixels):
        """Add one picture to the video."""
        if len(pixels) != self.bytes_per_picture:
            raise VideoError(f"a picture of {len(pixels)} bytes does not fit the video size")
        try:
            self.process.stdin.write(pixels)
        except OSError:
            # ffmpeg has stopped and closed the pipe. Why it stopped is
            # reported when the "with" block ends.
            raise VideoError(self._failure())

    def _failure(self):
        """Wait for ffmpeg to end and return its error message."""
        if self.process.stdin and not self.process.stdin.closed:
            try:
                self.process.stdin.close()
            except OSError:
                pass
        self.process.wait()
        self.error_file.seek(0)
        message = self.error_file.read().decode("utf-8", errors="replace").strip()
        return f"ffmpeg could not write {self.path.name}: {message[-500:]}"

    def __exit__(self, error_type, error, traceback):
        # Runs when the "with" block ends, also when an error happened in it.
        try:
            if error_type is None:
                self.process.stdin.close()   # tells ffmpeg that no more pictures come
                self.process.wait()
                if self.process.returncode != 0:
                    raise VideoError(self._failure())
                self.part.replace(self.path)   # complete: give it its real name
            else:
                # Something went wrong halfway: stop ffmpeg, keep nothing.
                if self.process.poll() is None:
                    self.process.kill()
                self.process.wait()
                try:
                    self.process.stdin.close()
                except OSError:
                    pass   # the pipe broke when ffmpeg was stopped
        finally:
            self.error_file.close()
            if self.part.exists():
                self.part.unlink()
        return False   # an error from inside the block is passed on
