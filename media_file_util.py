import logging
import os
from typing import Optional

from base_util import run_shell_command
from io_util import get_source_id
from models import MediaFile


logger = logging.getLogger(__name__)


def validate_media_file(media_file_path: str) -> Optional[MediaFile]:
    if not os.path.exists(media_file_path):
        logger.error(f"Could not find media file at: {media_file_path}")
        return None

    duration_ms = get_media_file_length(media_file_path)
    if duration_ms <= 0:
        logger.error("Not a valid media file")
        return None
    return MediaFile(media_file_path, duration_ms, get_source_id(media_file_path))


# returns duration in ms
def get_media_file_length(media_file: str):
    result = run_shell_command(
        " ".join(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                media_file,
            ]
        ),
    )
    return int(float(result) * 1000)  # NOTE unsafe! (convert secs to ms)


def too_close_to_edge(keyframe_ms: int, duration_ms: int, window_size_ms: int):
    if keyframe_ms + (window_size_ms / 2) > duration_ms or keyframe_ms < (
        window_size_ms / 2
    ):
        return True
    return False


def get_start_frame(keyframe_ms: int, window_size_ms: int, sample_rate: int):
    return (keyframe_ms - window_size_ms // 2) * sample_rate // 1000


def get_end_frame(keyframe_ms: int, window_size_ms: int, sample_rate: int):
    return (keyframe_ms + window_size_ms // 2) * sample_rate // 1000
