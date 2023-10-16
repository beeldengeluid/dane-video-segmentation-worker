import logging
import os
import sys
import base_util
from dane.config import cfg
from keyframe_extraction import get_fps, get_framecount, frame_index_to_timecode
from models import Provenance, HecateOutput
from provenance import obtain_software_versions
from time import time


logger = logging.getLogger(__name__)


# NOTE main function should be configurable in config.yml
# each processing module has a run function
def run(input_file_path: str, output_dir: str) -> Provenance:
    start_time = time()
    logger.info("Detecting shots and keyframes now.")
    try:
        shot_indices, keyframe_indices = detect_shots_and_keyframes(
            media_file=input_file_path
        )
        logger.info(
            f"Detected {len(keyframe_indices)} keyframes"
            f"and {len(shot_indices)} shots."
        )
    except Exception:
        logger.info("Could not obtain shots and keyframes. Exit.")
        sys.exit()

    fps = get_fps(input_file_path)

    # filter out the edge cases
    keyframe_indices = filter_edge_keyframes(
        keyframe_indices=keyframe_indices,
        fps=fps,
        framecount=get_framecount(input_file_path),
    )

    logger.info(f"Framerate is {fps}.")
    output_paths = _write_to_metadata_file(
        shot_indices, keyframe_indices, output_dir, fps
    )

    return Provenance(
        activity_name="Hecate",
        activity_description="Hecate for shot and keyframe detection",
        start_time_unix=start_time,
        processing_time_ms=time() - start_time,
        software_version=obtain_software_versions(["hecate"]),
        input_data={"input_file": input_file_path},
        output_data=output_paths,
    )


# each processing module has a get_output function
def get_output(metadata_dir: str, hecate_output_type: HecateOutput):
    return _read_metadata_file(metadata_dir, hecate_output_type.value)


def detect_shots_and_keyframes(
    media_file: str,
) -> tuple[list[tuple[int, ...]], list[int]]:
    cmd = [
        "hecate",  # NOTE: should be findable in PATH
        "-i",
        media_file,
        "--print_shot_info",
        "--print_keyfrm_info",
    ]
    # TODO: filter video according to optional timestamps in url
    try:
        hecate_result = base_util.run_shell_command(" ".join(cmd)).decode()
        logger.info(f"Hecate result: {hecate_result}")
    except Exception:
        logger.exception(f"Skipping hecate for {media_file}. {str(Exception)}.")
        return ([], [])
    return interpret_hecate_output(
        hecate_result
    )  # The units are frame indices (zero-based).


def interpret_hecate_output(
    hecate_result: str,
) -> tuple[list[tuple[int, ...]], list[int]]:
    for line in hecate_result.split("\n"):
        if line.startswith("shots:"):
            shots = [
                tuple([int(timestamp) for timestamp in shot[1:-1].split(":")])
                for shot in line[len("shots: ") :].split(",")
            ]
        elif line.startswith("keyframes:"):
            keyframes = [
                int(keyframe_index)
                for keyframe_index in line[len("keyframes: ") :][1:-1].split(",")
            ]
    return (shots, keyframes)


def _write_to_metadata_file(shots, keyframes, metadata_dir, fps):
    shots_times_path = os.path.join(metadata_dir, HecateOutput.SHOT_BOUNDARIES.value)
    keyframe_indices_path = os.path.join(
        metadata_dir, HecateOutput.KEYFRAME_INDICES.value
    )
    keyframe_times_path = os.path.join(
        metadata_dir, HecateOutput.KEYFRAMES_TIMESTAMPS.value
    )
    with open(
        shots_times_path,
        "w",
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

    with open(keyframe_indices_path, "w") as f:
        f.write(str(keyframes))
    with open(keyframe_times_path, "w") as f:
        f.write(str([frame_index_to_timecode(i, fps) for i in keyframes]))
    return {
        "shot_boundaires": shots_times_path,
        "keyframe_indices": keyframe_indices_path,
        "keyframes_timestamps": keyframe_times_path,
    }


# metadata_dir is the root dir for the hecate module
# filename is one of KEYFRAME_INDICES_FILE, SHOT_BOUNDARIES_FILE or KEYFRAMES_TIMESTAMPS_FILE
def _read_metadata_file(metadata_dir: str, file_name: str):
    file_path = os.path.join(metadata_dir, file_name)
    if not os.path.exists(file_path):
        logger.warning(f"Cannot find: {file_path}")
        return None

    with open(file_path, "r") as f:
        result = eval(f.read())
        logger.debug(result)
    return result


def filter_edge_keyframes(keyframe_indices, fps, framecount):
    # compute number of frames that should exist on either side of the keyframe
    half_window = cfg.VISXP_PREP.SPECTOGRAM_WINDOW_SIZE_MS / 2000 * fps
    logger.info(f"Half a window corresponds to {half_window} frames.")
    logger.info(f"Clip consists of {framecount} frames.")
    logger.info(
        f"Omitting frames 0-{half_window} and" f"{framecount-half_window}-{framecount}"
    )
    filtered = [
        keyframe_i
        for keyframe_i in keyframe_indices
        if keyframe_i > half_window and keyframe_i < framecount - half_window
    ]
    logger.info(f"Filtered out {len(keyframe_indices)-len(filtered)} edge keyframes")
    return filtered
