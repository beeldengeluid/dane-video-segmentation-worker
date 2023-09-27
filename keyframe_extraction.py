import cv2  # type: ignore
import os
import logging
from time import time
from typing import List
from models import Provenance


logger = logging.getLogger(__name__)


# Step 2: run keyframe extraction based on list of keyframe indices
def run(
    input_file_path: str, keyframe_indices: List[int], output_dir: str
) -> Provenance:
    start_time_keyframes = time()
    logger.info("Extracting keyframe images now.")

    keyframe_files = extract_keyframes(
        media_file=input_file_path,
        keyframe_indices=keyframe_indices,
        out_dir=output_dir,
    )
    logger.info(f"Extracted {len(keyframe_indices)} keyframes.")
    return Provenance(
        activity_name="Keyframe extraction",
        activity_description="Extract keyframes (images) for listed frame indices",
        start_time_unix=start_time_keyframes,
        processing_time_ms=time() - start_time_keyframes,
        input={
            "input_file_path": input_file_path,
            "keyframe_indices": str(keyframe_indices),
        },
        output={"Keyframe files": str(keyframe_files)},
    )


def extract_keyframes(
    media_file: str, keyframe_indices: list[int], out_dir: str
) -> list[str]:
    if not os.path.exists(media_file):
        raise IOError("Input video not found")

    vcap = cv2.VideoCapture(media_file)
    if not vcap.isOpened():
        raise IOError("Unable to open video file " + media_file)

    next_i = int(vcap.get(cv2.CAP_PROP_POS_FRAMES))
    max_i = max(keyframe_indices)
    fns = []
    while next_i <= max_i:
        ret = vcap.grab()
        if next_i in keyframe_indices:
            timestamp = round(vcap.get(cv2.CAP_PROP_POS_MSEC))  # msec position
            if ret:
                _, frame = vcap.retrieve()
                fn = os.path.join(out_dir, f"{timestamp}.jpg")
                cv2.imwrite(fn, frame)
                fns.append(fn)
            else:
                raise IOError(f"Unable to read keyframe {next_i}")
        next_i = int(vcap.get(cv2.CAP_PROP_POS_FRAMES))
    vcap.release()
    return fns


def get_fps(media_file):
    return cv2.VideoCapture(media_file).get(cv2.CAP_PROP_FPS)


def get_framecount(media_file):
    return cv2.VideoCapture(media_file).get(cv2.CAP_PROP_FRAME_COUNT)


def frame_index_to_timecode(frame_index: int, fps: float, out_format="ms"):
    if out_format == "ms":
        return round(frame_index / fps * 1000)
