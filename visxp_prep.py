import logging
import sys
import hecate_util
import keyframe_util
import spectogram_util
import os
from typing import Dict
from base_util import get_source_id
from dane.config import cfg
from provenance import generate_full_provenance_chain
from models import VisXPFeatureExtractionInput
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
        hecate_provenance = hecate_util.run(input_file_path, output_dirs["metadata"])

    if cfg.VISXP_PREP.RUN_KEYFRAME_EXTRACTION:
        keyframe_indices = _read_from_file(
            os.path.join(output_dirs["metadata"], "keyframes_indices.txt")
        )
        if not keyframe_indices:
            logger.error("Could not find keyframe_indices")
            sys.exit()

        keyframe_provenance = keyframe_util.run(
            input_file_path, keyframe_indices, output_dirs["keyframes"]
        )

    if cfg.VISXP_PREP.RUN_AUDIO_EXTRACTION:
        keyframe_timestamps = _read_from_file(
            os.path.join(output_dirs["metadata"], "keyframes_timestamps_ms.txt")
        )
        if not keyframe_timestamps:
            logger.error("Could not find keyframe_timestamps")
            sys.exit()

        spectogram_provenance = spectogram_util.run(
            input_file_path,
            keyframe_timestamps,
            output_dirs["spectograms"],
            output_dirs["tmp"],
        )

    # finally generate the provenance chain before returning the generated results
    provenance = generate_full_provenance_chain(
        start_time,
        input_file_path,
        [
            p
            for p in [hecate_provenance, keyframe_provenance, spectogram_provenance]
            if p is not None
        ],
    )

    return VisXPFeatureExtractionInput(500, "Not implemented yet!", -1, provenance)


# NOTE: maybe move this to base_util
def _generate_output_dirs(input_file_path: str) -> Dict[str, str]:
    output_dirs = {}
    for kind in ["keyframes", "metadata", "spectograms", "tmp"]:
        output_dir = os.path.join(
            cfg.VISXP_PREP.OUTPUT_DIR, get_source_id(input_file_path), kind
        )
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        output_dirs[kind] = output_dir
    return output_dirs


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
