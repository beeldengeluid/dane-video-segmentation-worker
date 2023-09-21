import base_util
import logging
import os

logger = logging.getLogger(__name__)
hecate_path = "/hecate/distribute/bin/hecate"
# TODO: test environment variable instead of specifying path here


def detect_shots_and_keyframes(
    media_file: str,
) -> tuple[list[tuple[int, ...]], list[int]]:
    cmd = f"{hecate_path} \
            -i {media_file} \
            --print_shot_info \
            --print_keyfrm_info"
    # TODO: filter video according to optional timestamps in url
    try:
        hecate_result = base_util.run_shell_command(cmd).decode()
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


def write_to_file(shots, keyframes, metadata_dir, fps):
    shots_times_path = os.path.join(metadata_dir, "shot_boundaries_timestamps_ms.txt")
    keyframe_indices_path = os.path.join(metadata_dir, "keyframe_indices.txt")
    keyframe_times_path = os.path.join(metadata_dir, "keyframes_timestamps_ms.txt")
    with open(shots_times_path, "w",) as f:
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

    with open(keyframe_indices_path, "w") as f:
        f.write(str(keyframes))
    with open(keyframe_times_path, "w") as f:
        f.write(str([_frame_index_to_timecode(i, fps) for i in keyframes]))
    return {'shot_boundaires': shots_times_path,
            'keyframe_indices': keyframe_indices_path,
            'keyframes_timestamps': keyframe_times_path}


def _frame_index_to_timecode(frame_index: int, fps: float, out_format="ms"):
    if out_format == "ms":
        return round(frame_index / fps * 1000)
