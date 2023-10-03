import logging
import ntpath
import os
from pathlib import Path
import requests
import sys
from time import time
from typing import Optional
from urllib.parse import urlparse

from base_util import validate_config, LOG_FORMAT
from dane import Document, Task, Result
from dane.base_classes import base_worker
from dane.config import cfg
from models import CallbackResponse, DownloadResult, Provenance
from output_util import transfer_output, delete_local_output
from pika.exceptions import ChannelClosedByBroker
from visxp_prep import generate_input_for_feature_extraction


"""
NOTE now the output dir created by by DANE (createDirs()) for the PATHS.OUT_FOLDER is not used:

- /mnt/dane-fs/output-files/03/d2/8a/03d28a03643a981284b403b91b95f6048576c234

Instead we put the output in:

- /mnt/dane-fs/output-files/visxp_prep/{asset-id}
"""
# initialises the root logger
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,  # configure a stream handler only for now (single handler)
    format=LOG_FORMAT,
)
logger = logging.getLogger()


class VideoSegmentationWorker(base_worker):
    def __init__(self, config):
        logger.info(config)

        self.UNIT_TESTING = os.getenv("DW_VISXP_UNIT_TESTING", False)

        if not validate_config(config, not self.UNIT_TESTING):
            logger.error("Invalid config, quitting")
            sys.exit()

        # first make sure the config has everything we need
        # Note: base_config is loaded first by DANE,
        # so make sure you overwrite everything in your config.yml!
        try:
            # put all of the relevant settings in a variable
            self.BASE_MOUNT: str = config.FILE_SYSTEM.BASE_MOUNT

            # construct the input & output paths using the base mount as a parent dir
            self.DOWNLOAD_DIR: str = os.path.join(
                self.BASE_MOUNT, config.FILE_SYSTEM.INPUT_DIR
            )
            self.VISXP_OUTPUT_DIR: str = os.path.join(
                self.BASE_MOUNT, config.FILE_SYSTEM.OUTPUT_DIR
            )

            self.DANE_DEPENDENCIES: list = (
                config.DANE_DEPENDENCIES if "DANE_DEPENDENCIES" in config else []
            )

            # read from default DANE settings
            self.DELETE_INPUT_ON_COMPLETION: bool = config.INPUT.DELETE_ON_COMPLETION
            self.DELETE_OUTPUT_ON_COMPLETION: bool = config.OUTPUT.DELETE_ON_COMPLETION
            self.TRANSFER_OUTPUT_ON_COMPLETION: bool = (
                config.OUTPUT.TRANSFER_ON_COMPLETION
            )

        except AttributeError:
            logger.exception("Missing configuration setting")
            sys.exit()

        # check if the file system is setup properly
        if not self.validate_data_dirs(self.DOWNLOAD_DIR, self.VISXP_OUTPUT_DIR):
            logger.info("ERROR: data dirs not configured properly")
            if not self.UNIT_TESTING:
                sys.exit()

        # we specify a queue name because every worker of this type should
        # listen to the same queue
        self.__queue_name = "VISXP_PREP"  # this is the queue that receives the work and NOT the reply queue
        self.DANE_DOWNLOAD_TASK_KEY = "DOWNLOAD"
        self.__binding_key = "#.VISXP_PREP"  # ['Video.VISXP_PREP', 'Sound.VISXP_PREP']
        self.__depends_on = self.DANE_DEPENDENCIES  # TODO make this part of DANE lib?

        if not self.UNIT_TESTING:
            logger.warning("Need to initialize the VISXP_PREP service")

        super().__init__(
            self.__queue_name,
            self.__binding_key,
            config,
            self.__depends_on,
            auto_connect=not self.UNIT_TESTING,
            no_api=self.UNIT_TESTING,
        )

    """----------------------------------INIT VALIDATION FUNCTIONS ---------------------------------"""

    def validate_data_dirs(self, input_dir: str, visxp_output_dir: str) -> bool:
        i_dir = Path(input_dir)
        o_dir = Path(visxp_output_dir)

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

    """----------------------------------INTERACTION WITH DANE SERVER ---------------------------------"""

    # DANE callback function, called whenever there is a job for this worker
    def callback(self, task: Task, doc: Document) -> CallbackResponse:
        logger.info("Receiving a task from the DANE (mock) server!")
        logger.info(task)
        logger.info(doc)

        # step 0: Create provenance object
        provenance = Provenance(
            activity_name="dane-video-segmenation-worker",
            activity_description="Apply VisXP prep to input media",
            start_time_unix=time(),
            processing_time_ms=-1,
            input={},
            output={},
        )

        # step 1: try to fetch the content via the configured DANE download worker
        download_result = self.fetch_downloaded_content(doc)

        # step 2: try to download the file if no DANE download worker was configured
        if download_result is None:
            logger.info(
                "The file was not downloaded by the DANE worker, downloading it myself..."
            )
            download_result = self.download_content(doc)
            if download_result is None:
                return {
                    "state": 500,
                    "message": "Could not download the document content",
                }
        download_provenance = Provenance(
            activity_name="download",
            activity_description="Download source media",
            start_time_unix=-1,
            processing_time_ms=download_result.download_time * 1000,
            input={},
            output={"file_path": download_result.file_path},
        )
        if not provenance.steps:
            provenance.steps = []
        provenance.steps.append(download_provenance)

        input_file = download_result.file_path

        # step 3: submit the input file to hecate/etc
        proc_result = generate_input_for_feature_extraction(input_file)

        # step 4: raise exception on failure
        if proc_result.state != 200:
            # something went wrong inside the VisXP work processor, return that response here
            return {"state": proc_result.state, "message": proc_result.message}
        provenance.steps.append(proc_result.provenance)

        # step 5: process returned successfully, generate the output
        asset_id = self.get_asset_id(input_file)
        visxp_output_dir = self.get_visxp_output_dir(asset_id)

        # step 6: transfer the output to S3 (if configured so)
        transfer_success = True
        if self.TRANSFER_OUTPUT_ON_COMPLETION:
            transfer_success = transfer_output(visxp_output_dir, asset_id)

        if (
            not transfer_success
        ):  # failure of transfer, impedes the workflow, so return error
            return {
                "state": 500,
                "message": "Failed to transfer output to S3",
            }

        # step 7: clear the output files (if configured so)
        delete_success = True
        if self.DELETE_OUTPUT_ON_COMPLETION:
            delete_success = delete_local_output(visxp_output_dir)

        if (
            not delete_success
        ):  # NOTE: just a warning for now, but one to keep an EYE out for
            logger.warning(f"Could not delete output files: {visxp_output_dir}")

        # step 8: clean the input file (if configured so)
        if not self.cleanup_input_file(input_file, self.DELETE_INPUT_ON_COMPLETION):
            return {
                "state": 500,
                "message": "Generated a transcript, but could not delete the input file",
            }

        # step 9: save the results back to the DANE index
        self.save_to_dane_index(
            doc,
            task,
            visxp_output_dir,  # TODO adapt function and pass whatever is neccesary for VisXP
            provenance=provenance,
        )
        return {
            "state": 200,
            "message": "Successfully generated VisXP data for the next worker",
        }

    # TODO adapt this function for VisXP
    def cleanup_input_file(self, input_file: str, actually_delete: bool) -> bool:
        # logger.info(f"Verifying deletion of input file: {input_file}")
        # if actually_delete is False:
        #     logger.info("Configured to leave the input alone, skipping deletion")
        #     return True

        # # first remove the input file
        # try:
        #     os.remove(input_file)
        #     logger.info(f"Deleted VisXP input file: {input_file}")
        #     # also remove the transcoded mp3 file (if any)
        #     if input_file.find(".mp3") == -1 and input_file.find(".") != -1:
        #         mp3_input_file = f"{input_file[:input_file.rfind('.')]}.mp3"
        #         if os.path.exists(mp3_input_file):
        #             os.remove(mp3_input_file)
        #             logger.info(f"Deleted mp3 transcode file: {mp3_input_file}")
        # except OSError:
        #     logger.exception("Could not delete input file")
        #     return False

        # # now remove the "chunked path" from /mnt/dane-fs/input-files/03/d2/8a/03d28a03643a981284b403b91b95f6048576c234/xyz.mp4
        # try:
        #     os.chdir(self.DOWNLOAD_DIR)  # cd /mnt/dane-fs/input-files
        #     os.removedirs(
        #         f".{input_file[len(self.DOWNLOAD_DIR):input_file.rfind(os.sep)]}"
        #     )  # /03/d2/8a/03d28a03643a981284b403b91b95f6048576c234
        #     logger.info("Deleted empty input dirs too")
        # except OSError:
        #     logger.exception("OSError while removing empty input file dirs")
        # except FileNotFoundError:
        #     logger.exception("FileNotFoundError while removing empty input file dirs")

        return True  # return True even if empty dirs were not removed

    # TODO adapt to VisXP
    def save_to_dane_index(
        self,
        doc: Document,
        task: Task,
        visxp_output_dir: str,
        provenance: Provenance,
    ) -> None:
        logger.info("saving results to DANE, task id={0}".format(task._id))
        # TODO figure out the multiple lines per transcript (refresh my memory)
        r = Result(
            self.generator,
            payload={
                # "transcript": transcript,
                # "visxp_output_dir": visxp_output_dir,
                # "doc_id": doc._id,
                # "task_id": task._id if task else None,  # TODO add this as well
                # "doc_target_id": doc.target["id"],
                # "doc_target_url": doc.target["url"],
                "provenance": provenance.to_json()
                # if provenance
                # else None,  # TODO test this
            },
            api=self.handler,
        )
        r.save(task._id)

    """----------------------------------ID MANAGEMENT FUNCTIONS ---------------------------------"""

    # the file name without extension is used as an asset ID by the container to save the results
    def get_asset_id(self, input_file: str) -> str:
        # grab the file_name from the path
        file_name = ntpath.basename(input_file)

        # split up the file in asset_id (used for creating a subfolder in the output) and extension
        asset_id, extension = os.path.splitext(file_name)
        logger.info("working with this asset ID {}".format(asset_id))
        return asset_id

    def get_visxp_output_dir(self, asset_id: str) -> str:
        return os.path.join(self.VISXP_OUTPUT_DIR, asset_id)

    """----------------------------------DOWNLOAD FUNCTIONS ---------------------------------"""

    # https://www.openbeelden.nl/files/29/29494.29451.WEEKNUMMER243-HRE00015742.mp4
    def download_content(self, doc: Document) -> Optional[DownloadResult]:
        if not doc.target or "url" not in doc.target or not doc.target["url"]:
            logger.info("No url found in DANE doc")
            return None

        logger.info("downloading {}".format(doc.target["url"]))
        fn = os.path.basename(urlparse(doc.target["url"]).path)
        # fn = unquote(fn)
        # fn = doc.target['url'][doc.target['url'].rfind('/') +1:]
        output_file = os.path.join(self.DOWNLOAD_DIR, fn)
        logger.info("saving to file {}".format(fn))

        # download if the file is not present (preventing unnecessary downloads)
        start_time = time()
        if not os.path.exists(output_file):
            with open(output_file, "wb") as file:
                response = requests.get(doc.target["url"])
                file.write(response.content)
                file.close()
        download_time = time() - start_time
        return DownloadResult(
            fn,  # NOTE or output_file? hmmm
            download_time,  # TODO add mime_type and content_length
        )

    def fetch_downloaded_content(self, doc: Document) -> Optional[DownloadResult]:
        logger.info("checking download worker output")
        possibles = self.handler.searchResult(doc._id, self.DANE_DOWNLOAD_TASK_KEY)
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


# Start the worker
if __name__ == "__main__":
    w = VideoSegmentationWorker(cfg)
    try:
        w.run()
    except ChannelClosedByBroker:
        """
        (406, 'PRECONDITION_FAILED - delivery acknowledgement on channel 1 timed out.
        Timeout value used: 1800000 ms.
        This timeout value can be configured, see consumers doc guide to learn more')
        """
        logger.critical("Please increase the consumer_timeout in your RabbitMQ server")
        w.stop()
    except (KeyboardInterrupt, SystemExit):
        w.stop()
