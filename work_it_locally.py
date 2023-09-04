

import logging
import sys

import FfMpegUtil
import hecate_util
import keyframe_util
import AudioExtractorUtil

import os

# initialises the root logger
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout  # configure a stream handler only for now (single handler)
)
logger = logging.getLogger()

def extract_shots_and_keyframes(media_file: str):
    shots, keyframes = hecate_util.detect_shots_and_keyframes(media_file=media_file)
    return shots, keyframes

    

def extract_audio(media_file: str, dict_of_timecodes: list[str], target_location: str):
    logger.info(f"extracting audio for {len(dict_of_timecodes)} timestamps to {target_location}.")
    AudioExtractorUtil.extract_audio_fragments(media_file=media_file,keyframe_timestamps=dict_of_timecodes,location=target_location)

def turn_into_spectogram(wav_file: str):
    # TODO: implement 
    return


if __name__ == "__main__":
    media_file = "/data/GEMKAN_MINANI-FHD00Z01PG3_112240_639720.mp4"
    source_id = "GEMKAN_MINANI-FHD00Z01PG3_112240_639720"
    dirs = {}
    for kind in ['keyframes','audio','metadata']:
        dir = os.path.join('/data',source_id,kind)
        if not os.path.isdir(dir):
            os.makedirs(dir)
        dirs[kind] = dir
    run_hecate = False
    run_keyfame_extraction = False
    run_audio_extraction = True

    if run_hecate:
        try:
            shots,keyframes = extract_shots_and_keyframes(media_file=media_file)
        except:
            logger.info(f'Could not obtain shots and keyframes. Exit.')
            sys.exit()
    else:
         with open(os.path.join(dirs['metadata'],'hecate_stdout.txt'),'r') as f:
              shots,keyframes = hecate_util.interpret_hecate_output(f.read())
    logger.info(f'Detected {len(keyframes)} keyframes and {len(shots)} shots.')
   
    if run_keyfame_extraction:
        logger.info("Extracting keyframe images now.")
        keyframe_times = keyframe_util.extract_keyframes(media_file = media_file, keyframe_indices=keyframes, out_dir=dirs['keyframes'])
        with open(os.path.join(dirs['metadata'],'keyframe_times.txt'),'w') as f:
            f.write(str(keyframe_times))
    else:
        with open(os.path.join(dirs['metadata'],'keyframe_times.txt'),'r') as f:
            keyframe_times = eval(f.read())
    
    logger.info(f'Obtained timecodes for {len(keyframes)} keyframes.')
    
    if run_audio_extraction:
        extract_audio(media_file=media_file, dict_of_timecodes=keyframe_times, target_location = dirs['audio'])
    else:
        True

    


