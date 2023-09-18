import logging
import shutil
import os
from dane.config import cfg
from dane.s3_util import S3Store


logger = logging.getLogger(__name__)


# TODO adapt this, so it deletes the VisXP output from the local DANE filesystem
def delete_local_output(visxp_output_dir: str) -> bool:
    logger.info(f"Deleting output folder: {visxp_output_dir}")
    if visxp_output_dir == os.sep or visxp_output_dir == ".":
        logger.warning(f"Rejected deletion of: {visxp_output_dir}")
        return False

    if not _is_valid_visxp_output(visxp_output_dir):
        logger.warning(
            f"Tried to delete a dir that did not contain VisXP output: {visxp_output_dir}"
        )
        return False

    try:
        shutil.rmtree(visxp_output_dir)
        logger.info(f"Cleaned up folder {visxp_output_dir}")
    except Exception:
        logger.exception(f"Failed to delete output dir {visxp_output_dir}")
        return False
    return True


# TODO implement
def _is_valid_visxp_output(visxp_output_dir: str) -> bool:
    return False


# TODO arrange an S3 bucket to store the VisXP results in
# TODO finish implementation to whatever is needed for VisXP files
def transfer_output(path: str, asset_id: str) -> bool:
    logger.info(f"Transferring {path} to S3 (asset={asset_id})")
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
    return s3.transfer_to_s3(
        cfg.OUTPUT.S3_BUCKET,
        os.path.join(
            cfg.OUTPUT.S3_FOLDER_IN_BUCKET, asset_id
        ),  # assets/<program ID>__<carrier ID>
        [  # TODO determine the output files to be transferred
            # os.path.join(path, CTM_FILE),
            # os.path.join(path, TXT_FILE),
        ],
    )
