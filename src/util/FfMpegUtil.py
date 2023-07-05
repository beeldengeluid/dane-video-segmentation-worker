import logging
import subprocess
import os
from datetime import datetime, time
import ffmpeg

logger = logging.getLogger("ffmpeg_util")


class FfMpegUtil:
    """pip install ffmpeg-python to be able to use the python extension for ffmpeg"""

    def __init__(self):
        self._media_source_file = None
        if self.__check_ffmpeg_installed():
            logger.info("YEAH! We've got transcoding in the house :-D")
        else:
            logger.warning(
                "you're in trouble. No no, no no no no, no no no no, no no no transcoding!"
            )

    def __check_ffmpeg_installed(self):
        """Before using ffmpeg-python, FFmpeg must be installed and accessible via the $PATH environment variable."""
        try:
            logger.info(subprocess.check_output(["ffmpeg", "-version"]))
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(
                f"Ffmpeg execution failed with error code {e.returncode}: {e.output}"
            )
        except FileNotFoundError as e:
            logger.warning(
                f"Error {e.errno}: {e.strerror}. Check whether ffmpeg is properly installed."
            )
        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
        return False

    def set_media_source_file(self, filepath: str):
        """Set the media file that is the input for ffmpeg."""
        if filepath is None:
            self._media_source_file = None
        elif os.path.isfile(filepath):
            self._media_source_file = filepath

    def is_media_source_file_set(self) -> bool:
        """Check just before processing to make sure media source file exists.
        Note that we do not probe the media file, so assuming it is media."""
        if self._media_source_file is not None and os.path.isfile(
            self._media_source_file
        ):
            return True
        else:
            return False

    def is_valid_timestamp(self, timestamp: str) -> bool:
        # TODO: find out what the real timestamps are that we can expect.
        for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
            try:
                tm = datetime.strptime(timestamp, fmt).time()
                if isinstance(tm, time):
                    return True
            except ValueError:
                pass
        return False

    def extract_audio(self) -> bool:
        """Given a media file, extract the audio and save to file."""
        try:
            if self.is_media_source_file_set() is False:
                logger.warning("No valid media source file is set.")
            else:
                logger.info(f"Extracting audio from {self._media_source_file}.")
                filename, ext = os.path.splitext(self._media_source_file)
                out_file = f"{filename}_out.mp3"
                if ext == ".mp3":
                    # just extract audio, copy and no transcoding.
                    (
                        ffmpeg.input(self._media_source_file)
                        .output(
                            out_file,
                            **{"map": "0:a", "c": "copy"},
                        )
                        .run(quiet=True, overwrite_output=True)
                    )
                else:
                    (
                        ffmpeg.input(self._media_source_file)
                        .output(
                            out_file,
                            **{"map": "0:a"},
                        )
                        .run(quiet=True, overwrite_output=True)
                    )
            if os.path.isfile(out_file):
                return True
        except ffmpeg.Error as e:
            logger.exception(e)
        return False

    def extract_audio_fragment(self, start_time: str, end_time: str) -> bool:
        """Extract audio fragment from media source file ans save to file.
        :param start_time: timestamp indicating the start time of the audio fragment.
        :param end_time: timestamp indicating the end time of the audio fragment.
                        Note that if end_time is greater than the end time of media,
                        the fragment ends at the end of media.
            Timestamps need to be in HH:MM:SS.xxx format.
            (see: https://ffmpeg.org/ffmpeg-utils.html#Time-duration)
        """
        try:
            if self.is_valid_timestamp(start_time) is False:
                logger.warning(f"Start time is not a valid timestamp: {start_time}")
                return False

            if self.is_valid_timestamp(end_time) is False:
                logger.warning(f"End time is not a valid timestamp: {end_time}")
                return False

            if self.is_media_source_file_set() is False:
                logger.warning("No valid media source file is set.")
                return False

            filename, ext = os.path.splitext(self._media_source_file)
            out_file = f"{filename}_beg_{start_time.replace(':', '').replace('.', '_')}_end_{end_time.replace(':', '').replace('.', '_')}.mp3"
            logger.info(
                f"Extracting fragment from {self._media_source_file}: {start_time} - {end_time}."
            )

            if ext == ".mp3":  # no re-encoding
                (
                    ffmpeg.input(self._media_source_file)
                    .output(
                        out_file,
                        **{
                            "map": "0:a",
                            "c:a": "copy",
                            "ss": start_time,
                            "to": end_time,
                        },
                    )
                    .run(quiet=True, overwrite_output=True)
                )
            else:
                (
                    ffmpeg.input(self._media_source_file)
                    .output(
                        out_file,
                        **{"map": "0:a", "ss": start_time, "to": end_time},
                    )
                    .run(quiet=True, overwrite_output=True)
                )

            if os.path.isfile(out_file):
                return True

        except ffmpeg.Error as e:
            logger.exception(e)
        return False
