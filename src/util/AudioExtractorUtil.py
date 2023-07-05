import logging
from datetime import datetime, time, timedelta
from FfMpegUtil import FfMpegUtil

logging.basicConfig(level=logging.DEBUG, format="%(message)s")

logger = logging.getLogger("audio_extractor_util")


class AudioExtractorUtil(FfMpegUtil):
    """Utility class to provide functions that extract audio fragments
    from input media file. This class is created specifically for VisXP.
    """

    def __init__(self):
        super(FfMpegUtil, self).__init__()

    def extract_audio_fragments_from_list(self, timecodes: list) -> None:
        """Read a list of timecodes and extract audio fragments for each of them."""
        if isinstance(timecodes, list) is False:
            logging.info("A list of timecodes is needed.")
        for tc in timecodes:
            try:
                ts = self.generate_timestamps_visxp(tc)
                self.extract_audio_fragment(start_time=ts.get("begin"), end_time=ts.get("end"))
            except ValueError as e:
                logger.error(e)

    def generate_timestamps_visxp(self, timecode: str, delta_secs: float = 0.5) -> dict:
        """Given a timecode, generate the start- and end timestamp for the audio fragment.
        :param timecode: a timestamp
        :param delta_secs: a float indicating the time (in seconds) to be extracted
            before and after the timecode.
        """
        # TODO: find out what the real timestamps are that we can expect.
        if self.is_valid_timestamp(timecode):
            for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
                try:
                    tm = datetime.strptime(timecode, fmt).time()
                    if isinstance(tm, time):
                        return {
                            "begin": (
                                datetime.combine(datetime.now(), tm) - timedelta(seconds=delta_secs)
                            )
                            .time()
                            .isoformat(),
                            "end": (
                                datetime.combine(datetime.now(), tm) + timedelta(seconds=delta_secs)
                            )
                            .time()
                            .isoformat(),
                        }
                except ValueError:
                    pass
        raise ValueError(f"Not a valid time code: {timecode}")

    def run(self, timecodes: list) -> None:
        """Describe the things you want to get done and run!"""
        for timestamp in timecodes:
            ts = self.generate_timestamps_visxp(timestamp)
            self.extract_audio_fragment(start_time=ts.get("begin"), end_time=ts.get("end"))
        print("Done!")


if __name__ == "__main__":
    media_file = "/mnt/c/Users/wmelder/Downloads/WEEKNUMMER374-HRE0000D0ED_1748000_1782000.mp4"
    worker = AudioExtractorUtil()
    list_of_timecodes = [
        "00:00:04",
        "00:00:08.500",
        "00:00:18.123456",
        "00:00:33.500",
    ]
    worker.set_media_source_file(filepath=None)
    worker.run(list_of_timecodes)  # no media file set
    worker.set_media_source_file(filepath=media_file)
    worker.run(list_of_timecodes)  # smooth as vanilla ice cream
    list_of_timecodes = ["00:er:ro.r"]
    worker.run(list_of_timecodes)  # value error expected
