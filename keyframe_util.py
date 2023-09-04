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
    FPS = vcap.get(cv2.CAP_PROP_FPS)


    next_i = int(vcap.get(cv2.CAP_PROP_POS_FRAMES)) 
    max_i = max(keyframe_indices)
    while next_i <= max_i: 
        ret = vcap.grab()
        if next_i in keyframe_indices:
            keyframe_timestamps[next_i]=round(vcap.get(cv2.CAP_PROP_POS_MSEC)) # msec position 
            if ret:
                _, frame = vcap.retrieve()
                fn = os.path.join(out_dir, f'keyframe_{next_i}.jpg')
                cv2.imwrite(fn, frame)
            else:
                raise IOError(f'Unable to read keyframe {i}')
        next_i = int(vcap.get(cv2.CAP_PROP_POS_FRAMES))
    vcap.release()
    return keyframe_timestamps

