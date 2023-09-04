import logging
from datetime import datetime, time, timedelta
import ffmpeg
import os

logger = logging.getLogger(__name__)



def extract_audio_fragments(media_file: str, keyframe_timestamps: dict[int:int], location: str, window_size : int = 1000):
    if not os.path.exists(media_file):
        raise IOError('Input video not found')

    logger.info(f"Extracting audio from {media_file} to {location}.")

    for i, (keyframe_index, timestamp) in enumerate(keyframe_timestamps.items()):
            
            
        #try:
            out_file = os.path.join(location, f"{keyframe_index}.wav")
            if i % 100 == 0: print(f'Keyframe index: {keyframe_index} at time {timestamp} ms. Extracting audio to {out_file}.')
            # TODO: group together as one ffmpeg command rather than this for-loop
            ffmpeg.input(media_file).output(
                            filename = out_file,
                            **{"map": "0:a", "ss": f"{int(timestamp-0.5*window_size)}ms", "to":  f"{int(timestamp+0.5*window_size)}ms"}, # TODO: edge case if start/end time not in video (e.g. negative start)
                        ).run(quiet=True, overwrite_output=True) # set quiet to False for debugging
            if i>200: break
        #except ffmpeg.Error as e:
        #    logger.exception(e)