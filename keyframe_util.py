import cv2
import os

import logging

logger = logging.getLogger(__name__)


def extract_keyframes(media_file: str, keyframe_indices: list[int], out_dir: str) -> dict[int,int]:
    if not os.path.exists(media_file):
        raise IOError('Input video not found')
    
    keyframe_timestamps = {}
    vcap = cv2.VideoCapture(media_file)
    if not vcap.isOpened():
        raise IOError('Unable to open video file ' + media_file)

    next_i = int(vcap.get(cv2.CAP_PROP_POS_FRAMES)) 
    max_i = max(keyframe_indices)
    while next_i <= max_i: 
        ret = vcap.grab()
        if next_i in keyframe_indices:
            timestamp=round(vcap.get(cv2.CAP_PROP_POS_MSEC)) # msec position 
            if ret:
                _, frame = vcap.retrieve()
                fn = os.path.join(out_dir, f'{timestamp}.jpg')
                cv2.imwrite(fn, frame)
            else:
                raise IOError(f'Unable to read keyframe {next_i}')
        next_i = int(vcap.get(cv2.CAP_PROP_POS_FRAMES))
    vcap.release()
    return keyframe_timestamps


