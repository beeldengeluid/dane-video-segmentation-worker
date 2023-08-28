import AudioExtractorUtil
import base_util
import logging
import sys

import FfMpegUtil

# initialises the root logger
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout  # configure a stream handler only for now (single handler)
)
logger = logging.getLogger()

def detect_shots(media_file: str)-> tuple[list[(str,str)],list[str]]:
    cmd = f'/hecate/distribute/bin/hecate -i {media_file}'
    hecate_result = base_util.run_shell_command(cmd)
    logging.info(f'Hecate result: {hecate_result}')
    # TODO: implement
    list_of_shots = []
    list_of_keyframe_timecodes = []
    return (list_of_shots, list_of_keyframe_timecodes)
    

def extract_audio(media_file: str, list_of_timecodes: list[str]):
    logger.info(f"extracting audio for {len(list_of_timecodes)} timestamps")
    audio_worker = AudioExtractorUtil.AudioExtractorUtil()
    audio_worker.set_media_source_file(filepath=media_file)
    audio_worker.run(list_of_timecodes)  # smooth as vanilla ice cream

def turn_into_spectogram(wav_file: str):
    # TODO: implement 
    return


if __name__ == "__main__":
    media_file = "/data/GEMKAN_MINANI-FHD00Z01PG3_112240_639720.mp4"
    shots = detect_shots(media_file=media_file)
    list_of_timecodes = [
        "00:00:04",
        "00:00:08.500",
        "00:00:18.123456",
        "00:00:33.500",
    ]

    # extract_audio(media_file=media_file, list_of_timecodes=list_of_timecodes)

    


