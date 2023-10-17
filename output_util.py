import logging
import os
import shutil
from typing import Dict, List

from dane.config import cfg
from dane.s3_util import S3Store
from models import OutputType


logger = logging.getLogger(__name__)
S3_OUTPUT_TYPES: List[OutputType] = [
    OutputType.KEYFRAMES,
    OutputType.SPECTOGRAMS,
    OutputType.PROVENANCE,
    OutputType.METADATA,
]  # only upload this output to S3


# returns the basename of the input file path without an extension
# throughout processing this is then used as a unique ID to keep track of the input/output
def get_source_id(input_file_path: str) -> str:
    fn = os.path.basename(input_file_path)
    return fn[0 : fn.rfind(".")] if "." in fn else fn


# below this dir each processing module will put its output data in a subfolder
def get_base_output_dir(source_id: str = "") -> str:
    path_elements = [cfg.FILE_SYSTEM.BASE_MOUNT, cfg.FILE_SYSTEM.OUTPUT_DIR]
    if source_id:
        path_elements.append(source_id)
    return os.path.join(*path_elements)


def get_download_dir():
    return os.path.join(cfg.FILE_SYSTEM.BASE_MOUNT, cfg.FILE_SYSTEM.INPUT_DIR)


# for each OutputType a subdir is created inside the base output dir
def generate_output_dirs(source_id: str) -> Dict[str, str]:
    base_output_dir = get_base_output_dir(source_id)
    output_dirs = {}
    for output_type in OutputType:
        output_dir = os.path.join(base_output_dir, output_type.value)
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        output_dirs[output_type.value] = output_dir
    return output_dirs


def delete_local_output(source_id: str) -> bool:
    output_dir = get_base_output_dir(source_id)
    logger.info(f"Deleting output folder: {output_dir}")
    if output_dir == os.sep or output_dir == ".":
        logger.warning(f"Rejected deletion of: {output_dir}")
        return False

    if not _is_valid_visxp_output(output_dir):
        logger.warning(
            f"Tried to delete a dir that did not contain VisXP output: {output_dir}"
        )
        return False

    try:
        shutil.rmtree(output_dir)
        logger.info(f"Cleaned up folder {output_dir}")
    except Exception:
        logger.exception(f"Failed to delete output dir {output_dir}")
        return False
    return True


# TODO implement some more, now checks presence of provenance dir
def _is_valid_visxp_output(output_dir: str) -> bool:
    return os.path.exists(os.path.join(output_dir, OutputType.PROVENANCE.value))


# TODO arrange an S3 bucket to store the VisXP results in
# TODO finish implementation to whatever is needed for VisXP files
def transfer_output(source_id: str) -> bool:
    output_dir = get_base_output_dir(source_id)
    logger.info(f"Transferring {output_dir} to S3 (asset={source_id})")
    if any(
        [
            not x
            for x in [
                cfg.OUTPUT.S3_ENDPOINT_URL,
                cfg.OUTPUT.S3_BUCKET,
                cfg.OUTPUT.S3_FOLDER_IN_BUCKET,
            ]
        ]
    ):
        logger.warning(
            "TRANSFER_ON_COMPLETION configured without all the necessary S3 settings"
        )
        return False

    s3 = S3Store(cfg.OUTPUT.S3_ENDPOINT_URL)
    for output_type in S3_OUTPUT_TYPES:
        output_sub_dir = os.path.join(output_dir, output_type.value)
        success = s3.transfer_to_s3(
            cfg.OUTPUT.S3_BUCKET,
            os.path.join(
                cfg.OUTPUT.S3_FOLDER_IN_BUCKET, source_id, output_type.value
            ),  # assets/<program ID>__<carrier ID>/spectograms|keyframes|provenance
            obtain_files_to_upload_to_s3(output_sub_dir),
        )
        if not success:
            logger.error(
                f"Failed to upload output folder: {output_sub_dir}, aborting rest of upload"
            )
            return False
    return True


def get_s3_base_url(source_id: str) -> str:
    return f"s3://{os.path.join(cfg.OUTPUT.S3_BUCKET, cfg.OUTPUT.S3_FOLDER_IN_BUCKET, source_id)}"


def obtain_files_to_upload_to_s3(output_dir: str) -> List[str]:
    s3_file_list = []
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            s3_file_list.append(os.path.join(root, f))
    return s3_file_list


# NOTE: untested
def delete_input_file(input_file: str, actually_delete: bool) -> bool:
    logger.info(f"Verifying deletion of input file: {input_file}")
    if actually_delete is False:
        logger.info("Configured to leave the input alone, skipping deletion")
        return True

    # first remove the input file
    try:
        os.remove(input_file)
        logger.info(f"Deleted VisXP input file: {input_file}")
    except OSError:
        logger.exception("Could not delete input file")
        return False

    # now remove the "chunked path" from /mnt/dane-fs/input-files/03/d2/8a/03d28a03643a981284b403b91b95f6048576c234/xyz.mp4
    try:
        os.chdir(get_download_dir())  # cd /mnt/dane-fs/input-files
        os.removedirs(
            f".{input_file[len(get_download_dir()):input_file.rfind(os.sep)]}"
        )  # /03/d2/8a/03d28a03643a981284b403b91b95f6048576c234
        logger.info("Deleted empty input dirs too")
    except OSError:
        logger.exception("OSError while removing empty input file dirs")
    except FileNotFoundError:
        logger.exception("FileNotFoundError while removing empty input file dirs")

    return True  # return True even if empty dirs were not removed
