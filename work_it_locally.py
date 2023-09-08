import logging
import sys

import hecate_util
import keyframe_util
import spectogram_util
import cv2  # type: ignore

# import AudioExtractorUtil

import os

# initialises the root logger
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,  # configure a stream handler only for now (single handler)
)
logger = logging.getLogger()


def frame_index_to_timecode(frame_index: int, fps: float, out_format="ms"):
    if out_format == "ms":
        return round(frame_index / fps * 1000)


def get_fps(media_file):
    return cv2.VideoCapture(media_file).get(cv2.CAP_PROP_FPS)


if __name__ == "__main__":
    media_file = "/data/ZQWO_DYnq5Q_000000.mp4"
    source_id = "ZQWO_DYnq5Q_000000"
    # media_file = "/data/GEMKAN_MINANI-FHD00Z01PG3_112240_639720.mp4"
    # source_id = "GEMKAN_MINANI-FHD00Z01PG3_112240_639720"
    dirs = {}
    for kind in ["keyframes", "metadata", "spectograms", "tmp"]:
        dir = os.path.join("/data", source_id, kind)
        if not os.path.isdir(dir):
            os.makedirs(dir)
        dirs[kind] = dir
    run_hecate = True
    run_keyfame_extraction = True
    run_audio_extraction = True

    if run_hecate:
        logger.info("Detecting shots and keyframes now.")
        try:
            shots, keyframes = hecate_util.detect_shots_and_keyframes(
                media_file=media_file
            )
            logger.info(f"Detected {len(keyframes)} keyframes and {len(shots)} shots.")
        except Exception:
            logger.info("Could not obtain shots and keyframes. Exit.")
            sys.exit()
        fps = get_fps(media_file)
        logger.info(f"Framerate is {fps}.")
        with open(
            os.path.join(dirs["metadata"], "shot_boundaries_timestamps_ms.txt"), "w"
        ) as f:
            f.write(
                str(
                    [
                        (
                            frame_index_to_timecode(start, fps),
                            frame_index_to_timecode(end, fps),
                        )
                        for (start, end) in shots
                    ]
                )
            )
        with open(os.path.join(dirs["metadata"], "keyframe_indices.txt"), "w") as f:
            f.write(str(keyframes))
        with open(
            os.path.join(dirs["metadata"], "keyframes_timestamps_ms.txt"), "w"
        ) as f:
            f.write(str([frame_index_to_timecode(i, fps) for i in keyframes]))

    if run_keyfame_extraction:
        logger.info("Extracting keyframe images now.")
        with open(os.path.join(dirs["metadata"], "keyframe_indices.txt"), "r") as f:
            keyframe_indices = eval(f.read())
        keyframe_util.extract_keyframes(
            media_file=media_file,
            keyframe_indices=keyframe_indices,
            out_dir=dirs["keyframes"],
        )
        logger.info(f"Extracted {len(keyframes)} keyframes.")

    if run_audio_extraction:
        with open(
            os.path.join(dirs["metadata"], "keyframes_timestamps_ms.txt"), "r"
        ) as f:
            keyframe_timestamps = eval(f.read())
        logger.info("Extracting audio spectograms now.")
        spectogram_util.extract_audio_spectograms(
            media_file=media_file,
            keyframe_timestamps=keyframe_timestamps,
            location=dirs["spectograms"],
            tmp_location=dirs["tmp"],
        )
