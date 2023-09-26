import logging
import sys
import hecate_util
import keyframe_util
import spectogram_util
import cv2  # type: ignore
import os
from typing import Dict, List
from base_util import get_source_id
from dane.config import cfg
from models import Provenance, VisXPFeatureExtractionInput
from functools import reduce
from time import time


logger = logging.getLogger(__name__)


# TODO call this from the worker and start the actual processing of the input
def generate_input_for_feature_extraction(
    input_file_path: str,
) -> VisXPFeatureExtractionInput:
    start_time = time()
    logger.info(f"Processing input: {input_file_path}")

    output_dirs = _generate_output_dirs(input_file_path)

    hecate_provenance = None
    keyframe_provenance = None
    spectogram_provenance = None

    if cfg.VISXP_PREP.RUN_HECATE:
        hecate_provenance = _run_hecate(input_file_path, output_dirs["metadata"])

    if cfg.VISXP_PREP.RUN_KEYFRAME_EXTRACTION:
        keyframe_indices = _read_from_file(
            os.path.join(output_dirs["metadata"], "keyframes_indices.txt")
        )
        if not keyframe_indices:
            logger.error("Could not find keyframe_indices")
            sys.exit()

        keyframe_provenance = _run_keyframe_extraction(
            input_file_path, keyframe_indices, output_dirs["keyframes"]
        )

    if cfg.VISXP_PREP.RUN_AUDIO_EXTRACTION:
        keyframe_timestamps = _read_from_file(
            os.path.join(output_dirs["metadata"], "keyframes_timestamps_ms.txt")
        )
        if not keyframe_timestamps:
            logger.error("Could not find keyframe_timestamps")
            sys.exit()

        spectogram_provenance = _run_audio_extraction(
            input_file_path,
            keyframe_timestamps,
            output_dirs["spectograms"],
            output_dirs["tmp"],
        )

    provenance = Provenance(
        activity_name="VisXP prep",
        activity_description=(
            "Detect shots and keyframes, "
            "extract keyframes and corresponding audio spectograms"
        ),
        start_time_unix=start_time,
        processing_time_ms=start_time - time(),
        parameters=cfg.VISXP_PREP,
        steps=[
            prov
            for prov in [hecate_provenance, keyframe_provenance, spectogram_provenance]
            if prov is not None
        ],
        software_version=_obtain_software_versions(["dane-video-segmentation-worker"]),
        input={"input_file_path": input_file_path},
        output=reduce(
            lambda a, b: {**a, **b},
            [
                prov.output
                for prov in [
                    hecate_provenance,
                    keyframe_provenance,
                    spectogram_provenance,
                ]
                if prov is not None
            ],
        ),
    )

    with open("/data/provenance.json", "w") as f:
        f.write(str(provenance.to_json()))
    logger.info("Wrote provenance info to file: /data/provenance.json")

    return VisXPFeatureExtractionInput(500, "Not implemented yet!", -1, provenance)


# NOTE: maybe move this to base_util
def _generate_output_dirs(input_file_path: str) -> Dict[str, str]:
    output_dirs = {}
    for kind in ["keyframes", "metadata", "spectograms", "tmp"]:
        output_dir = os.path.join("/data", get_source_id(input_file_path), kind)
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        output_dirs[kind] = output_dir
    return output_dirs


# Step 1: generate shots & keyframes using Hecate
def _run_hecate(input_file_path: str, output_dir: str) -> Provenance:
    start_time_hecate = time()
    logger.info("Detecting shots and keyframes now.")
    try:
        shot_indices, keyframe_indices = hecate_util.detect_shots_and_keyframes(
            media_file=input_file_path
        )
        logger.info(
            f"Detected {len(keyframe_indices)} keyframes"
            f"and {len(shot_indices)} shots."
        )
    except Exception:
        logger.info("Could not obtain shots and keyframes. Exit.")
        sys.exit()

    fps = _get_fps(input_file_path)

    # filter out the edge cases
    keyframe_indices = _filter_edge_keyframes(
        keyframe_indices=keyframe_indices,
        fps=fps,
        framecount=_get_framecount(input_file_path),
    )

    logger.info(f"Framerate is {fps}.")
    output_paths = hecate_util.write_to_file(
        shot_indices, keyframe_indices, output_dir, fps
    )

    return Provenance(
        activity_name="Hecate",
        activity_description="Hecate for shot and keyframe detection",
        start_time_unix=start_time_hecate,
        processing_time_ms=time() - start_time_hecate,
        software_version=_obtain_software_versions(["hecate"]),
        input={"input_file": input_file_path},
        output=output_paths,
    )


def _run_keyframe_extraction(
    input_file_path: str, keyframe_indices: List[int], output_dir: str
) -> Provenance:
    start_time_keyframes = time()
    logger.info("Extracting keyframe images now.")

    keyframe_files = keyframe_util.extract_keyframes(
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


def _run_audio_extraction(
    input_file_path: str, keyframe_timestamps: List[int], output_dir: str, tmp_dir: str
) -> Provenance:
    start_time_spectograms = time()
    logger.info("Extracting audio spectograms now.")
    sample_rates = cfg.VISXP_PREP.SPECTOGRAM_SAMPLERATE_HZ

    spectogram_files = []
    for sample_rate in sample_rates:
        logger.info(f"Extracting spectograms for {sample_rate}Hz now.")
        sf = spectogram_util.extract_audio_spectograms(
            media_file=input_file_path,
            keyframe_timestamps=keyframe_timestamps,
            location=output_dir,
            tmp_location=tmp_dir,
            sample_rate=sample_rate,
            window_size_ms=cfg.VISXP_PREP.SPECTOGRAM_WINDOW_SIZE_MS,
        )
        spectogram_files.extend(sf)
    return Provenance(
        activity_name="Spectogram extraction",
        activity_description=(
            "Extract audio spectogram (Numpy array)"
            "corresponding to 1 sec. of audio around each listed keyframe"
        ),
        start_time_unix=start_time_spectograms,
        processing_time_ms=time() - start_time_spectograms,
        input={
            "input_file_path": input_file_path,
            "keyframe_timestamps": str(keyframe_timestamps),
        },
        output={"spectogram_files": str(spectogram_files)},
    )


def _filter_edge_keyframes(keyframe_indices, fps, framecount):
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


def _frame_index_to_timecode(frame_index: int, fps: float, out_format="ms"):
    if out_format == "ms":
        return round(frame_index / fps * 1000)


def _get_framecount(media_file):
    return cv2.VideoCapture(media_file).get(cv2.CAP_PROP_FRAME_COUNT)


# NOTE might be replaced with:
# ffprobe -v 0 -of csv=p=0 -select_streams v:0 -show_entries stream=r_frame_rate testob.mp4
def _get_fps(media_file):
    return cv2.VideoCapture(media_file).get(cv2.CAP_PROP_FPS)


def _obtain_software_versions(software_names):
    if isinstance(software_names, str):  # wrap a single software name in a list
        software_names = [software_names]
    try:
        with open("/software_provenance.txt") as f:
            urls = (
                {}
            )  # for some reason I couldnt manage a working comprehension for the below - SV
            for line in f.readlines():
                name, url = line.split(";")
                if name.strip() in software_names:
                    urls[name.strip()] = url.strip()
            assert len(urls) == len(software_names)
            return urls
    except FileNotFoundError:
        logger.info(
            f"Could not read {software_names} version"
            f"from file /software_provenance.txt: file does not exist"
        )
    except ValueError as e:
        logger.info(
            f"Could not parse {software_names} version"
            f"from file /software_provenance.txt. {e}"
        )
    except AssertionError:
        logger.info(
            f"Could not find {software_names} version"
            f"in file /software_provenance.txt"
        )


def _read_from_file(metadata_file):
    with open(metadata_file, "r") as f:
        result = eval(f.read())
        logger.debug(result)
    return result


if __name__ == "__main__":
    from base_util import LOG_FORMAT

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,  # configure a stream handler only for now (single handler)
        format=LOG_FORMAT,
    )

    if cfg.VISXP_PREP and cfg.VISXP_PREP.TEST_INPUT_FILE:
        generate_input_for_feature_extraction(cfg.VISXP_PREP.TEST_INPUT_FILE)
    else:
        logger.error("Please configure an input file in VISXP_PREP.TEST_INPUT_FILE")
