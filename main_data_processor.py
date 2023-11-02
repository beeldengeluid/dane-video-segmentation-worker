import logging
from time import time

from dane.config import cfg
import hecate
import keyframe_extraction
from models import (
    VisXPFeatureExtractionInput,
    OutputType,
    HecateOutput,
    CallbackResponse,
)
from io_util import (
    get_source_id,
    get_base_output_dir,
    generate_output_dirs,
    delete_local_output,
    delete_input_file,
    transfer_output,
)
from provenance import generate_full_provenance_chain
import spectogram


logger = logging.getLogger(__name__)


# generates all the required output for the 2nd DANE worker
def generate_input_for_feature_extraction(
    input_file_path: str,
) -> VisXPFeatureExtractionInput:
    start_time = time()
    logger.info(f"Processing input: {input_file_path}")

    # Step 0: this is the "processing ID" if you will
    source_id = get_source_id(input_file_path)

    # Step 1: generate output dir per OutputType
    output_dirs = generate_output_dirs(source_id)

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
            return VisXPFeatureExtractionInput(
                500, "Could not find keyframe_indices", None
            )

        keyframe_provenance = keyframe_extraction.run(
            input_file_path, keyframe_indices, output_dirs[OutputType.KEYFRAMES.value]
        )

    if cfg.VISXP_PREP.RUN_AUDIO_EXTRACTION:
        keyframe_timestamps = hecate.get_output(
            output_dirs[OutputType.METADATA.value], HecateOutput.KEYFRAMES_TIMESTAMPS
        )
        if not keyframe_timestamps:
            logger.error("Could not find keyframe_timestamps")
            return VisXPFeatureExtractionInput(
                500, "Could not find keyframe_timestamps", None
            )

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

    return VisXPFeatureExtractionInput(
        200, "Succesfully generated input for VisXP feature extraction", provenance
    )


# assesses the output and makes sure input & output is handled properly
def apply_desired_io_on_output(
    input_file: str,
    proc_result: VisXPFeatureExtractionInput,
    delete_input_on_completion: bool,
    delete_output_on_completetion: bool,
    transfer_output_on_completion: bool,
) -> CallbackResponse:
    # step 4: raise exception on failure
    if proc_result.state != 200:
        logger.error(f"Could not process the input properly: {proc_result.message}")
        input_deleted = delete_input_file(input_file, delete_input_on_completion)
        logger.info(f"Deleted input file of failed process: {input_deleted}")
        # something went wrong inside the VisXP work processor, return that response here
        return {"state": proc_result.state, "message": proc_result.message}

    # step 5: process returned successfully, generate the output
    source_id = get_source_id(input_file)
    visxp_output_dir = get_base_output_dir(source_id)

    # step 6: transfer the output to S3 (if configured so)
    transfer_success = True
    if transfer_output_on_completion:
        transfer_success = transfer_output(source_id)

    if (
        not transfer_success
    ):  # failure of transfer, impedes the workflow, so return error
        return {
            "state": 500,
            "message": "Failed to transfer output to S3",
        }

    # step 7: clear the output files (if configured so)
    delete_success = True
    if delete_output_on_completetion:
        delete_success = delete_local_output(source_id)

    if (
        not delete_success
    ):  # NOTE: just a warning for now, but one to keep an EYE out for
        logger.warning(f"Could not delete output files: {visxp_output_dir}")

    # step 8: clean the input file (if configured so)
    if not delete_input_file(input_file, delete_input_on_completion):
        return {
            "state": 500,
            "message": "Generated VISXP_PREP output, but could not delete the input file",
        }

    return {
        "state": 200,
        "message": "Successfully generated VisXP data for the next worker",
    }
