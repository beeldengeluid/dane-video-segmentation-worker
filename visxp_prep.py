import logging
import sys
import hecate_util
import keyframe_util
import spectogram_util
import cv2  # type: ignore
import os
from base_util import get_source_id
from dane.config import cfg
from dataclasses import dataclass


@dataclass
class VisXPFeatureExtractionInput:
    state: int
    message: str
    processing_time: float


# TODO call this from the worker and start the actual processing of the input
def generate_input_for_feature_extraction(
    input_file_path: str,
) -> VisXPFeatureExtractionInput:
    logger.info(f"Processing input: {input_file_path}")

    output_dirs = {}
    for kind in ["keyframes", "metadata", "spectograms", "tmp"]:
        output_dir = os.path.join("/data", get_source_id(input_file_path), kind)
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        output_dirs[kind] = output_dir

    if cfg.VISXP_PREP.RUN_HECATE:
        logger.info("Detecting shots and keyframes now.")
        try:
            shots, keyframes = hecate_util.detect_shots_and_keyframes(
                media_file=input_file_path
            )
            logger.info(f"Detected {len(keyframes)} keyframes and {len(shots)} shots.")
        except Exception:
            logger.info("Could not obtain shots and keyframes. Exit.")
            sys.exit()
        fps = _get_fps(input_file_path)
        logger.info(f"Framerate is {fps}.")
        with open(
            os.path.join(output_dirs["metadata"], "shot_boundaries_timestamps_ms.txt"),
            "w",
        ) as f:
            f.write(
                str(
                    [
                        (
                            _frame_index_to_timecode(start, fps),
                            _frame_index_to_timecode(end, fps),
                        )
                        for (start, end) in shots
                    ]
                )
            )
        with open(
            os.path.join(output_dirs["metadata"], "keyframe_indices.txt"), "w"
        ) as f:
            f.write(str(keyframes))
        with open(
            os.path.join(output_dirs["metadata"], "keyframes_timestamps_ms.txt"), "w"
        ) as f:
            f.write(str([_frame_index_to_timecode(i, fps) for i in keyframes]))

    if cfg.VISXP_PREP.RUN_KEYFRAME_EXTRACTION:
        logger.info("Extracting keyframe images now.")
        with open(
            os.path.join(output_dirs["metadata"], "keyframe_indices.txt"), "r"
        ) as f:
            keyframe_indices = eval(f.read())
            logger.debug(keyframe_indices)
        keyframe_util.extract_keyframes(
            media_file=input_file_path,
            keyframe_indices=keyframe_indices,
            out_dir=output_dirs["keyframes"],
        )
        logger.info(f"Extracted {len(keyframes)} keyframes.")

    if cfg.VISXP_PREP.RUN_AUDIO_EXTRACTION:
        with open(
            os.path.join(output_dirs["metadata"], "keyframes_timestamps_ms.txt"), "r"
        ) as f:
            keyframe_timestamps = eval(f.read())
            logger.debug(keyframe_timestamps)
        logger.info(
            f"Extracting audio spectograms for {len(keyframe_timestamps)} keyframes."
        )
        sample_rates = cfg.VISXP_PREP.SPECTOGRAM_SAMPLERATE_HZ
        for sample_rate in sample_rates:
            logger.info(f"Extracting spectograms for {sample_rate}Hz now.")
            spectogram_util.extract_audio_spectograms(
                media_file=input_file_path,
                keyframe_timestamps=keyframe_timestamps,
                location=output_dirs["spectograms"],
                tmp_location=output_dirs["tmp"],
                sample_rate=sample_rate,
            )
    return VisXPFeatureExtractionInput(500, "Not implemented yet!", -1)


def _frame_index_to_timecode(frame_index: int, fps: float, out_format="ms"):
    if out_format == "ms":
        return round(frame_index / fps * 1000)


# NOTE might be replaced with:
# ffprobe -v 0 -of csv=p=0 -select_streams v:0 -show_entries stream=r_frame_rate testob.mp4
def _get_fps(media_file):
    return cv2.VideoCapture(media_file).get(cv2.CAP_PROP_FPS)


if __name__ == "__main__":
    from base_util import LOG_FORMAT

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,  # configure a stream handler only for now (single handler)
        format=LOG_FORMAT,
    )
    logger = logging.getLogger()
    if cfg.VISXP_PREP and cfg.VISXP_PREP.TEST_INPUT_FILE:
        generate_input_for_feature_extraction(cfg.VISXP_PREP.TEST_INPUT_FILE)
    logger.error("Please configure an input file in VISXP_PREP.TEST_INPUT_FILE")
