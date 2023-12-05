import csv
import logging
import os
from time import time
from typing import Generator, List, Tuple
from dane.provenance import Provenance, obtain_software_versions
from base_util import run_shell_command

# from media_file_util import too_close_to_edge
from models import OutputType, ScenedetectOutput, HecateOutput

# TODO write some code

logger = logging.getLogger(__name__)


def _get_csv_file_path(output_dir: str) -> str:
    return os.path.join(
        output_dir,
        OutputType.METADATA.value,
        ScenedetectOutput.KEYFRAME_METADATA_CSV.value,
    )


def _get_keyframe_dir(output_dir: str) -> str:
    return os.path.join(output_dir, OutputType.KEYFRAMES.value)


def _get_shot_boundaries_path(output_dir: str) -> str:
    return os.path.join(
        output_dir, OutputType.METADATA.value, HecateOutput.SHOT_BOUNDARIES.value
    )


def _get_keyframe_indices_path(output_dir: str) -> str:
    return os.path.join(
        output_dir, OutputType.METADATA.value, HecateOutput.KEYFRAME_INDICES.value
    )


# TODO also try the Python client
def run(input_file_path: str, output_dir: str, extract_keyframes=False) -> Provenance:
    logger.info(f"Running scenedetect on {input_file_path}")
    start_time = time()
    output_csv = _get_csv_file_path(output_dir)
    keyframe_dir = _get_keyframe_dir(output_dir)
    cmd = [
        "scenedetect",
        "-i",
        input_file_path,
        "list-scenes",
        "-f",  # where to save the .csv file
        ScenedetectOutput.KEYFRAME_METADATA_CSV.value,
        "-o",
        os.path.join(output_dir, OutputType.METADATA.value),
    ]
    if extract_keyframes:
        logger.info("Also telling scenedetect to extract keyframes")
        cmd.extend(
            [
                "save-images",  # TODO make sure to save 1 per scene (or filter out the rest when making spectograms)
                "-n",
                "1",  # just one keyframe per scene/shot
                "-f",
                "\$FRAME_NUMBER",  # noqa: W605
                "-o",
                keyframe_dir,
            ]
        )
    result = run_shell_command(" ".join(cmd))
    if not result:
        logger.error(f"Failed to run scenedetect on {input_file_path}")

    # for backwards compatability, save the HecateOutput.SHOT_BOUNDARIES
    save_shot_boundaries_file(output_dir)

    # for backwards compatability, save the HecateOutput.KEYFRAME_INDICES
    save_keyframe_indices_file(output_dir)

    return Provenance(
        activity_name="Python Scenedetect",
        activity_description="Shot detection & keyframe extraction",
        start_time_unix=start_time,
        processing_time_ms=time() - start_time,
        software_version=obtain_software_versions(["scenedetect"]),
        input_data={"input_file": input_file_path},
        output_data={
            "keyframe_dir": keyframe_dir,
            "output_csv": output_csv,
            "shot_boundaries": _get_shot_boundaries_path(output_dir),
        },
    )


def save_shot_boundaries_file(output_dir: str) -> bool:
    shot_boundaries = get_shot_boundaries(output_dir)
    shot_boundaries_file_path = _get_shot_boundaries_path(output_dir)
    logger.info(f"Saving shot boundaries to {shot_boundaries_file_path}")
    try:
        with open(shot_boundaries_file_path, "w+") as f:
            f.write(str(shot_boundaries))
    except Exception:
        logger.exception(f"Could not save to {shot_boundaries_file_path}")
        return False
    return True


def save_keyframe_indices_file(output_dir: str) -> bool:
    keyframe_indices = get_keyframe_indices(output_dir)
    keyframe_indices_file_path = _get_keyframe_indices_path(output_dir)
    logger.info(f"Saving shot boundaries to {keyframe_indices_file_path}")
    try:
        with open(keyframe_indices_file_path, "w+") as f:
            f.write(str(keyframe_indices))
    except Exception:
        logger.exception(f"Could not save to {keyframe_indices_file_path}")
        return False
    return True


# extracts the keyframe timestamps from the generated CSV file
def get_keyframe_timestamps(output_dir: str) -> List[int]:
    logger.info("Extracting keyframe timestamps")
    return [int(float(row[3]) * 1000) for row in load_csv_data(output_dir)]


# extracts the keyframe timestamps from the generated CSV file
def get_keyframe_indices(output_dir: str) -> List[int]:
    logger.info("Extracting keyframe indices")
    # filter out the first frame also subtract 1 frame somehow
    return [int(row[1]) - 1 for row in load_csv_data(output_dir) if int(row[1]) != 1]


# extracts the keyframe timestamps from the generated CSV file
def get_shot_boundaries(output_dir: str) -> List[Tuple[int, int]]:
    logger.info("Extracting shot boundaries")
    return [
        (int(float(row[3]) * 1000), int(float(row[6]) * 1000))
        for row in load_csv_data(output_dir)
    ]


def load_csv_data(output_dir: str) -> Generator:
    output_csv = _get_csv_file_path(output_dir)
    if not os.path.exists(output_csv):
        logger.error(f"CSV file not found: {output_csv}")
        return
    logger.info(f"Parsing {output_csv}")
    with open(output_csv, newline="") as f:
        r = csv.reader(f, delimiter=",", quotechar="|")
        next(r)  # skip 1st line (timecode list)
        next(r)  # skip 2nd line (column headers)
        next(r)  # skip 3rd line (frame 1)
        for row in r:
            yield row


if __name__ == "__main__":
    import sys
    from base_util import LOG_FORMAT

    logging.basicConfig(
        stream=sys.stdout,  # configure a stream handler only for now (single handler)
        format=LOG_FORMAT,
        level="INFO",
    )
    logger.info("Let us test this")
    timestamps = get_keyframe_timestamps("./tests/data/scenedetect")
    logger.info(len(timestamps))

    shot_boundaries = get_shot_boundaries("./tests/data/scenedetect")
    logger.info(len(shot_boundaries))
