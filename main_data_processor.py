from functools import reduce
import logging
from typing import Optional, Tuple
import validators
from time import time

from dane.config import cfg
from dane.provenance import (
    Provenance,
    obtain_software_versions,
    generate_initial_provenance,
    stop_timer_and_persist_provenance_chain,
)
from dane.s3_util import validate_s3_uri
from models import (
    VisXPFeatureExtractionInput,
    CallbackResponse,
)
from media_file_util import validate_media_file
from io_util import (
    get_base_output_dir,
    generate_output_dirs,
    delete_local_output,
    delete_input_file,
    download_uri,
    get_provenance_file,
    to_download_provenance,
    transfer_output,
    validate_data_dirs,
)
import scenedetect_util


logger = logging.getLogger(__name__)
DANE_WORKER_ID = "dane-video-segmentation-worker"


# triggered by running: python worker.py --run-test-file
def run(
    input_file_path: str, download_provenance: Optional[Provenance] = None
) -> Tuple[CallbackResponse, Optional[Provenance]]:
    # there must be an input file
    if not input_file_path:
        logger.error("input file empty")
        return {"state": 403, "message": "Error, no input file"}, []

    # check if the file system is setup properly
    if not validate_data_dirs():
        logger.info("ERROR: data dirs not configured properly")
        return {"state": 500, "message": "Input & output dirs not ok"}, []

    # create the top-level provenance
    top_level_provenance = generate_initial_provenance(
        name="VisXP-preparation",
        description=(
            "Generate input data for VisXP feature extraction: detect shots and keyframes, "
            "optionally extract keyframes and/or corresponding audio spectrograms"
        ),
        input_data={"input_file_path": input_file_path},  # TODO S3 URI!
        start_time=time(),
        parameters=dict(cfg.VISXP_PREP),
        software_version=obtain_software_versions(DANE_WORKER_ID),
    )
    provenance_chain = []  # will contain the steps of the top-level provenance

    # check if the input_file_path was already downloaded or not, if not do so
    if not download_provenance:
        logger.info(f"Analyzing input file: {input_file_path}")
        start_time = time()
        if validate_s3_uri(input_file_path) or validators.url(input_file_path):
            logger.info("Input is a URI, contuining to download")
            download_result = download_uri(input_file_path)
            if not download_result:
                return {
                    "state": 500,
                    "message": f"Could not download {input_file_path}",
                }, []
            else:
                download_provenance = to_download_provenance(
                    download_result,
                    input_file_path,
                    start_time=start_time,
                    software_version=top_level_provenance.software_version,
                )
                input_file_path = download_result.file_path if download_result else ""

    if download_provenance:
        logger.info("Adding download provenance to provenance chain")
        provenance_chain.append(download_provenance)  # add the download provenance
    proc_result = generate_input_for_feature_extraction(input_file_path)

    if proc_result.provenance_chain:
        provenance_chain.extend(proc_result.provenance_chain)

    # as a last piece of output, generate the provenance.json before packaging and uploading
    full_provenance_chain = stop_timer_and_persist_provenance_chain(
        provenance=top_level_provenance,
        output_data=reduce(
            lambda a, b: {**a, **b},
            [p.output_data for p in provenance_chain],
        ),
        provenance_chain=provenance_chain,
        provenance_file_path=get_provenance_file(input_file_path),
    )

    validated_output: CallbackResponse = (
        apply_desired_io_on_output(  # TODO make sure the media file is there
            proc_result,
            cfg.INPUT.DELETE_ON_COMPLETION,
            cfg.OUTPUT.DELETE_ON_COMPLETION,
            cfg.OUTPUT.TRANSFER_ON_COMPLETION,
            cfg.OUTPUT.TAR_OUTPUT,
        )
    )
    return validated_output, full_provenance_chain


# generates all the required output for the 2nd DANE worker
def generate_input_for_feature_extraction(
    input_file_path: str,
) -> VisXPFeatureExtractionInput:
    logger.info(f"Processing input: {input_file_path}")

    media_file = validate_media_file(input_file_path)
    if not media_file:
        return VisXPFeatureExtractionInput(500, "Invalid or missing media file")

    # Step 1: generate output dir per OutputType
    generate_output_dirs(media_file.source_id)

    scenedetect_provenance = None
    # spectrogram_provenance = None TODO: implement if needed

    # scenedetect generates (keyframe) metadata and keyframes
    try:
        scenedetect_provenance = scenedetect_util.run(
            media_file,
            get_base_output_dir(media_file.source_id),
            cfg.VISXP_PREP.SPECTROGRAM_WINDOW_SIZE_MS,
        )
    except scenedetect_util.ScenedetectFailureException:
        return VisXPFeatureExtractionInput(
            500,
            "VisXP prep has failed.",
            media_file,
            [
                p
                for p in [
                    scenedetect_provenance,
                ]
                if p is not None
            ],
        )

    # TODO: implement this if we want it back
    if cfg.VISXP_PREP.GENERATE_SPECTROGRAM_IMAGES:
        logger.error(
            "Configured to generate spectrogram images, "
            "which is not implemented in the current version."
        )
    if cfg.VISXP_PREP.RUN_AUDIO_EXTRACTION:
        logger.error(
            "Configured to run audio extraction, "
            "which is not implemented in the current version."
        )

    return VisXPFeatureExtractionInput(
        200,
        "Succesfully generated input for VisXP feature extraction",
        media_file,
        [
            p
            for p in [
                scenedetect_provenance,
                # spectrogram_provenance, TODO: activate when needed
            ]
            if p is not None
        ],
    )


# assesses the output and makes sure input & output is handled properly
def apply_desired_io_on_output(
    proc_result: VisXPFeatureExtractionInput,
    delete_input_on_completion: bool,
    delete_output_on_completetion: bool,
    transfer_output_on_completion: bool,
    tar_before_transfer: bool,
) -> CallbackResponse:
    media_file = proc_result.media_file
    if not media_file:
        return {"state": 404, "message": "No media file in processing result"}
    # step 4: raise exception on failure
    if proc_result.state != 200:
        logger.error(f"Could not process the input properly: {proc_result.message}")
        input_deleted = delete_input_file(
            media_file.file_path, delete_input_on_completion
        )
        logger.info(f"Deleted input file of failed process: {input_deleted}")
        # something went wrong inside the VisXP work processor, return that response here
        return {"state": proc_result.state, "message": proc_result.message}

    # step 5: process returned successfully, generate the output
    visxp_output_dir = get_base_output_dir(media_file.source_id)

    # step 6: transfer the output to S3 (if configured so)
    transfer_success = True
    if transfer_output_on_completion:
        transfer_success = transfer_output(
            media_file.source_id, as_tar=tar_before_transfer
        )

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
        delete_success = delete_local_output(media_file.source_id)

    if (
        not delete_success
    ):  # NOTE: just a warning for now, but one to keep an EYE out for
        logger.warning(f"Could not delete output files: {visxp_output_dir}")

    # step 8: clean the input file (if configured so)
    if not delete_input_file(media_file.file_path, delete_input_on_completion):
        return {
            "state": 500,
            "message": "Generated VISXP_PREP output, but could not delete the input file",
        }

    return {
        "state": 200,
        "message": "Successfully generated VisXP data for the next worker",
    }
