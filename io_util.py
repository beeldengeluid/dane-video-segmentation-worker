import logging
import os
from pathlib import Path
import requests
import shutil
from time import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

from dane import Document
from dane.config import cfg
from dane.provenance import PROVENANCE_FILE, Provenance
from dane.s3_util import S3Store, parse_s3_uri, validate_s3_uri
from models import OutputType, DownloadResult


logger = logging.getLogger(__name__)
DANE_DOWNLOAD_TASK_KEY = "DOWNLOAD"
OUTPUT_FILE_BASE_NAME = "visxp_prep"
S3_OUTPUT_TYPES: List[OutputType] = [
    OutputType.KEYFRAMES,
    OutputType.SPECTOGRAMS,
    OutputType.PROVENANCE,
    OutputType.METADATA,
    OutputType.SPECTOGRAM_IMAGES,
    OutputType.AUDIO,
]  # only upload this output to S3


# make sure the necessary base dirs are there
def validate_data_dirs() -> bool:
    i_dir = Path(get_download_dir())
    o_dir = Path(get_base_output_dir())
    logger.info(
        f"Making sure the input ({i_dir}) & output ({o_dir}) dirs are available"
    )

    if not os.path.exists(i_dir.parent.absolute()):
        logger.info(
            "{} does not exist. Make sure BASE_MOUNT_DIR exists before retrying".format(
                i_dir.parent.absolute()
            )
        )
        return False

    # make sure the input and output dirs are there
    try:
        os.makedirs(i_dir, 0o755)
        logger.info("created VisXP input dir: {}".format(i_dir))
    except FileExistsError as e:
        logger.info(e)

    try:
        os.makedirs(o_dir, 0o755)
        logger.info("created VisXP output dir: {}".format(o_dir))
    except FileExistsError as e:
        logger.info(e)

    return True


def get_download_dir():
    return os.path.join(cfg.FILE_SYSTEM.BASE_MOUNT, cfg.FILE_SYSTEM.INPUT_DIR)


def get_provenance_file(input_file_path: str) -> str:
    return os.path.join(
        get_base_output_dir(get_source_id(input_file_path)),
        OutputType.PROVENANCE.value,
        PROVENANCE_FILE,
    )


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


# output file name of the final tar.gz that will be uploaded to S3
def get_output_file_name(source_id: str) -> str:
    return f"{OUTPUT_FILE_BASE_NAME}__{source_id}.tar.gz"


# e.g. s3://<bucket>/assets/<source_id>
def get_s3_base_uri(source_id: str) -> str:
    return f"s3://{os.path.join(cfg.OUTPUT.S3_BUCKET, cfg.OUTPUT.S3_FOLDER_IN_BUCKET, source_id)}"


# e.g. s3://<bucket>/assets/<source_id>/visxp_prep__<source_id>.tar.gz
def get_s3_output_file_uri(source_id: str) -> str:
    return f"{get_s3_base_uri(source_id)}/{get_output_file_name(source_id)}"


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


def _validate_transfer_config() -> bool:
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
    return True


# compresses all desired output dirs into a single tar and uploads it to S3
def transfer_output(source_id: str) -> bool:
    output_dir = get_base_output_dir(source_id)
    logger.info(f"Transferring {output_dir} to S3 (asset={source_id})")
    if not _validate_transfer_config():
        return False

    s3 = S3Store(cfg.OUTPUT.S3_ENDPOINT_URL)
    file_list = [os.path.join(output_dir, ot.value) for ot in S3_OUTPUT_TYPES]
    tar_file = os.path.join(output_dir, get_output_file_name(source_id))

    success = s3.transfer_to_s3(
        cfg.OUTPUT.S3_BUCKET,
        os.path.join(
            cfg.OUTPUT.S3_FOLDER_IN_BUCKET, source_id
        ),  # assets/<program ID>__<carrier ID>
        file_list,  # this list of subdirs will be compressed into the tar below
        tar_file,  # this file will be uploaded
    )
    if not success:
        logger.error(f"Failed to upload: {tar_file}")
        return False
    return True


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


def get_dane_download_worker_provenance(handler, doc: Document) -> Optional[Provenance]:
    # the input doc MUST have a url
    if not doc.target or "url" not in doc.target or not doc.target.get("url", None):
        logger.info("No url found in DANE doc")
        return None

    dane_input_url = doc.target.get("url")

    # step 1: try to fetch the content via the configured DANE download worker
    download_result = _fetch_dane_download_result(handler, doc)

    return (
        to_download_provenance(download_result, dane_input_url)
        if download_result
        else None
    )


def _fetch_dane_download_result(handler, doc: Document) -> Optional[DownloadResult]:
    logger.info("checking download worker output")
    possibles = handler.searchResult(doc._id, DANE_DOWNLOAD_TASK_KEY)
    logger.info(possibles)
    # NOTE now MUST use the latest dane-beng-download-worker or dane-download-worker
    if len(possibles) > 0 and "file_path" in possibles[0].payload:
        return DownloadResult(
            possibles[0].payload.get("file_path"),
            possibles[0].payload.get("download_time", -1),
            possibles[0].payload.get("mime_type", "unknown"),
            possibles[0].payload.get("content_length", -1),
        )
    logger.error("No file_path found in download result")
    return None


def download_uri(uri: str) -> Optional[DownloadResult]:
    logger.info(f"Trying to download {uri}")
    if validate_s3_uri(uri):
        logger.info("URI seems to be an s3 uri")
        return s3_download(uri)
    return http_download(uri)


# TODO test this!
def http_download(url: str) -> Optional[DownloadResult]:
    logger.info(f"Downloading {url}")
    fn = os.path.basename(urlparse(url).path)
    # fn = unquote(fn)
    # fn = doc.target['url'][doc.target['url'].rfind('/') +1:]
    output_file = os.path.join(get_download_dir(), fn)
    logger.info(f"Saving to file {fn}")

    # download if the file is not present (preventing unnecessary downloads)
    start_time = time()
    if not os.path.exists(output_file):
        with open(output_file, "wb") as file:
            response = requests.get(url)
            file.write(response.content)
            file.close()
    download_time = time() - start_time
    return DownloadResult(
        output_file,  # NOTE or output_file? hmmm
        download_time,  # TODO add mime_type and content_length
    )


# e.g. s3://dane-asset-staging-gb/assets/2101608170158176431__NOS_JOURNAAL_-WON01513227.mp4
def s3_download(s3_uri: str) -> Optional[DownloadResult]:
    logger.info(f"Downloading {s3_uri}")
    if not validate_s3_uri(s3_uri):
        logger.error(f"Invalid S3 URI: {s3_uri}")
        return None

    # source_id = get_source_id(s3_uri)
    start_time = time()
    output_folder = get_download_dir()

    # TODO download the content into get_download_dir()
    s3 = S3Store(cfg.OUTPUT.S3_ENDPOINT_URL)
    bucket, object_name = parse_s3_uri(s3_uri)
    logger.info(f"OBJECT NAME: {object_name}")
    input_file_path = os.path.join(
        get_download_dir(),
        # source_id,
        os.path.basename(object_name),  # i.e. visxp_prep__<source_id>.tar.gz
    )
    success = s3.download_file(bucket, object_name, output_folder)
    if success:
        download_time = time() - start_time
        return DownloadResult(
            input_file_path,
            download_time,
        )
    logger.error("Failed to download input data from S3")
    return None


def to_download_provenance(
    download_result: DownloadResult, input_file_path: str
) -> Provenance:
    return Provenance(
        activity_name="Download VisXP input",
        activity_description="Download source AV media",
        start_time_unix=-1,  # TODO not supplied yet by download worker
        processing_time_ms=download_result.download_time,  # TODO not supllied yet by download worker
        input_data={"input_file_path": input_file_path},
        output_data={"file_path": download_result.file_path},
    )
