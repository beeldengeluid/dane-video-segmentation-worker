import logging
import sys
import hecate_util
import keyframe_util
import spectogram_util
import cv2  # type: ignore
import os
from base_util import get_source_id
from dane.config import cfg
from models import Provenance, VisXPFeatureExtractionInput
from functools import reduce
from time import time


# TODO call this from the worker and start the actual processing of the input
def generate_input_for_feature_extraction(
    input_file_path: str
) -> VisXPFeatureExtractionInput:
    start_time = time()
    logger.info(f"Processing input: {input_file_path}")

    output_dirs = {}
    for kind in ["keyframes", "metadata", "spectograms", "tmp"]:
        output_dir = os.path.join("/data", get_source_id(input_file_path), kind)
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        output_dirs[kind] = output_dir

    if cfg.VISXP_PREP.RUN_HECATE:
        start_time_hecate = time()
        logger.info("Detecting shots and keyframes now.")
        try:
            shot_indices, keyframe_indices = hecate_util.detect_shots_and_keyframes(
                media_file=input_file_path
            )
            logger.info(f"Detected {len(keyframe_indices)} keyframes \
                        and {len(shot_indices)} shots.")
        except Exception:
            logger.info("Could not obtain shots and keyframes. Exit.")
            sys.exit()
        fps = _get_fps(input_file_path)
        logger.info(f"Framerate is {fps}.")

        output_paths = hecate_util.write_to_file(
            shot_indices, keyframe_indices, output_dirs['metadata'], fps)

        hecate_provenance = Provenance(
            activity_name='Hecate',
            activity_description="Hecate for shot and keyframe detection",
            start_time_unix=start_time_hecate,
            processing_time_ms=time() - start_time_hecate,
            software_version=_obtain_software_versions(['hecate']),
            input={'input_file': input_file_path},
            output=output_paths,
        )
    else:
        hecate_provenance = None
        keyframe_indices = None
        keyframe_timestamps = None

    if cfg.VISXP_PREP.RUN_KEYFRAME_EXTRACTION:
        start_time_keyframes = time()
        logger.info("Extracting keyframe images now.")
        if keyframe_indices is None:
            keyframe_indices = _read_from_file(
                os.path.join(output_dirs["metadata"], "keyframes_indices.txt"))
        keyframe_files = keyframe_util.extract_keyframes(
            media_file=input_file_path,
            keyframe_indices=keyframe_indices,
            out_dir=output_dirs["keyframes"],
        )
        logger.info(f"Extracted {len(keyframe_indices)} keyframes.")
        keyframe_provenance = Provenance(
            activity_name="Keyframe extraction",
            activity_description="Extract keyframes (images) for listed frame indices",
            start_time_unix=start_time_keyframes,
            processing_time_ms=time() - start_time_keyframes,
            input={'input_file_path': input_file_path,
                   'keyframe_indices': str(keyframe_indices)},
            output={'Keyframe files': str(keyframe_files)}
        )
    else:
        keyframe_provenance = None

    if cfg.VISXP_PREP.RUN_AUDIO_EXTRACTION:
        if keyframe_timestamps is None:
            keyframe_timestamps = _read_from_file(
                os.path.join(output_dirs["metadata"], "keyframes_timestamps_ms.txt"))
        start_time_spectograms = time()
        logger.info("Extracting audio spectograms now.")
        spectogram_files = spectogram_util.extract_audio_spectograms(
            media_file=input_file_path,
            keyframe_timestamps=keyframe_timestamps,
            location=output_dirs["spectograms"],
            tmp_location=output_dirs["tmp"],
        )
        spectogram_provenance = Provenance(
            activity_name="Spectogram extraction",
            activity_description="Extract audio spectogram (Numpy array) \
                corresponding to 1 sec. of audio around each listed keyframe",
            start_time_unix=start_time_spectograms,
            processing_time_ms=time() - start_time_spectograms,
            input={'input_file_path': input_file_path,
                   'keyframe_timestamps': str(keyframe_timestamps)},
            output={'spectogram_files': str(spectogram_files)}
        )
    else:
        spectogram_provenance = None

    provenance = Provenance(
        activity_name="VisXP prep",
        activity_description="Detect shots and keyframes, \
        extract keyframes and corresponding audio spectograms",
        start_time_unix=start_time,
        processing_time_ms=start_time - time(),
        parameters=cfg.VISXP_PREP,
        steps=[prov for prov in
               [hecate_provenance, keyframe_provenance, spectogram_provenance]
               if prov is not None],
        software_version=_obtain_software_versions(['dane-video-segmentation-worker']),
        input={'input_file_path': input_file_path},
        output=reduce(lambda a, b: {**a, **b},
                      [prov.output for prov in
                       [hecate_provenance, keyframe_provenance, spectogram_provenance]
                       if prov is not None])
    )

    with open('/data/provenance.json', 'w') as f:
        f.write(str(provenance.to_json()))

    return VisXPFeatureExtractionInput(500, "Not implemented yet!", -1, provenance)


# NOTE might be replaced with:
# ffprobe -v 0 -of csv=p=0 -select_streams v:0 -show_entries stream=r_frame_rate testob.mp4
def _get_fps(media_file):
    return cv2.VideoCapture(media_file).get(cv2.CAP_PROP_FPS)


def _obtain_software_versions(software_names):
    if isinstance(software_names, str):  # wrap a single software name in a list
        software_names = [software_names]
    try:
        with open('/software_provenance.txt') as f:
            urls = {}  # for some reason I couldnt manage a working comprehension for the below - SV
            for line in f.readlines():
                name, url = line.split(';')
                if name.strip() in software_names:
                    urls[name.strip()] = url.strip()
            assert len(urls) == len(software_names)
            return urls
    except FileNotFoundError:
        logger.info(f"Could not read {software_names} version \
                    from file /software_provenance.txt: file does not exist")
    except ValueError as e:
        logger.info(f"Could not parse {software_names} version \
                    from file /software_provenance.txt. {e}")
    except AssertionError:
        logger.info(f"Could not find {software_names} version \
                    in file /software_provenance.txt")


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
    logger = logging.getLogger()
    
    _obtain_software_versions(['hecate'])

    if cfg.VISXP_PREP and cfg.VISXP_PREP.TEST_INPUT_FILE:
        generate_input_for_feature_extraction(cfg.VISXP_PREP.TEST_INPUT_FILE)
    else:
        logger.error("Please configure an input file in VISXP_PREP.TEST_INPUT_FILE")
