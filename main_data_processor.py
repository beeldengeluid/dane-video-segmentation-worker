import logging
import sys
from time import time

from dane.config import cfg
import hecate
import keyframe_extraction
from models import VisXPFeatureExtractionInput, OutputType, HecateOutput
from output_util import generate_output_dirs
from provenance import generate_full_provenance_chain
import spectogram


logger = logging.getLogger(__name__)


# TODO call this from the worker and start the actual processing of the input
def generate_input_for_feature_extraction(
    input_file_path: str,
) -> VisXPFeatureExtractionInput:
    start_time = time()
    logger.info(f"Processing input: {input_file_path}")

    # Step 1: generate output dir per OutputType
    output_dirs = generate_output_dirs(input_file_path)

    hecate_provenance = None
    keyframe_provenance = None
    spectogram_provenance = None

    if cfg.VISXP_PREP.RUN_HECATE:
        hecate_provenance = hecate.run(
            input_file_path, output_dirs[OutputType.METADATA.value]
        )

    if cfg.VISXP_PREP.RUN_KEYFRAME_EXTRACTION:
        keyframe_indices = hecate.get_output(
            output_dirs[OutputType.METADATA.value], HecateOutput.KEYFRAME_INDICES
        )
        if not keyframe_indices:
            logger.error("Could not find keyframe_indices")
            sys.exit()

        keyframe_provenance = keyframe_extraction.run(
            input_file_path, keyframe_indices, output_dirs[OutputType.KEYFRAMES.value]
        )

    if cfg.VISXP_PREP.RUN_AUDIO_EXTRACTION:
        keyframe_timestamps = hecate.get_output(
            output_dirs[OutputType.METADATA.value], HecateOutput.KEYFRAMES_TIMESTAMPS
        )
        if not keyframe_timestamps:
            logger.error("Could not find keyframe_timestamps")
            sys.exit()

        spectogram_provenance = spectogram.run(
            input_file_path,
            keyframe_timestamps,
            output_dirs[OutputType.SPECTOGRAMS.value],
            output_dirs[OutputType.TMP.value],
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
