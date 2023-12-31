from functools import reduce
import logging
from typing import Optional, Tuple
import validators

from dane.config import cfg
from dane.provenance import (
    Provenance,
    obtain_software_versions,
    generate_initial_provenance,
    stop_timer_and_persist_provenance_chain,
)
from dane.s3_util import validate_s3_uri

# import hecate
import keyframe_extraction
from models import (
    VisXPFeatureExtractionInput,
    OutputType,
    # HecateOutput,
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
import spectogram
import scenedetect


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
        name="Generate input data for VisXP feature extraction",
        description=(
            "Detect shots and keyframes, "
            "extract keyframes and corresponding audio spectograms"
        ),
        input_data={"input_file_path": input_file_path},  # TODO S3 URI!
        parameters=dict(cfg.VISXP_PREP),
        software_version=obtain_software_versions(DANE_WORKER_ID),
    )
    provenance_chain = []  # will contain the steps of the top-level provenance

    # check if the input_file_path was already downloaded or not, if not do so
    if not download_provenance:
        logger.info(f"Analyzing input file: {input_file_path}")
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
                    download_result, input_file_path
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
    output_dirs = generate_output_dirs(media_file.source_id)

    # hecate_provenance = None
    keyframe_provenance = None
    scenedetect_provenance = None
    spectogram_provenance = None

    # scenedetect generates (keyframe) metadata and keyframes
    scenedetect_provenance = scenedetect.run(
        media_file,
        get_base_output_dir(media_file.source_id),
        cfg.VISXP_PREP.SPECTOGRAM_WINDOW_SIZE_MS,
    )

    # if cfg.VISXP_PREP.RUN_HECATE:
    #     hecate_provenance = hecate.run(
    #         input_file_path, output_dirs[OutputType.METADATA.value]
    #     )

    keyframe_indices = scenedetect.get_keyframe_indices(
        get_base_output_dir(media_file.source_id),
        media_file.duration_ms,
        cfg.VISXP_PREP.SPECTOGRAM_WINDOW_SIZE_MS,
    )
    keyframe_timestamps = scenedetect.get_keyframe_timestamps(
        get_base_output_dir(media_file.source_id),
        media_file.duration_ms,
        cfg.VISXP_PREP.SPECTOGRAM_WINDOW_SIZE_MS,
    )
    logger.info(keyframe_timestamps)

    logger.info(keyframe_indices)

    # NOTE this step can be skipped with scenedetect
    if cfg.VISXP_PREP.RUN_KEYFRAME_EXTRACTION:
        # keyframe_indices = hecate.get_output(
        #     output_dirs[OutputType.METADATA.value], HecateOutput.KEYFRAME_INDICES
        # )
        if not keyframe_indices:
            logger.error("Could not find keyframe_indices")
            return VisXPFeatureExtractionInput(500, "Could not find keyframe_indices")

        keyframe_provenance = keyframe_extraction.run(
            input_file_path,
            keyframe_indices,
            keyframe_timestamps,
            output_dirs[OutputType.KEYFRAMES.value],
        )

    # TODO adapt to work with the output of Scenedetect
    if cfg.VISXP_PREP.RUN_AUDIO_EXTRACTION:
        # keyframe_timestamps = hecate.get_output(
        #     output_dirs[OutputType.METADATA.value], HecateOutput.KEYFRAMES_TIMESTAMPS
        # )
        if not keyframe_timestamps:
            logger.error("Could not find keyframe_timestamps")
            return VisXPFeatureExtractionInput(
                500, "Could not find keyframe_timestamps"
            )

        spectogram_provenance = spectogram.run(
            input_file_path=input_file_path,
            keyframe_timestamps=keyframe_timestamps,  # TODO check if this matches the actual keyframe timestamps
            output_dirs=output_dirs,
        )

    return VisXPFeatureExtractionInput(
        200,
        "Succesfully generated input for VisXP feature extraction",
        media_file,
        [
            p
            for p in [
                scenedetect_provenance,
                spectogram_provenance,
                keyframe_provenance,
            ]  # hecate_provenance
            if p is not None
        ],
    )


# assesses the output and makes sure input & output is handled properly
def apply_desired_io_on_output(
    proc_result: VisXPFeatureExtractionInput,
    delete_input_on_completion: bool,
    delete_output_on_completetion: bool,
    transfer_output_on_completion: bool,
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
        transfer_success = transfer_output(media_file.source_id)

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
