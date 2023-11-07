import logging
import os
from pathlib import Path
import sys
from time import time

from base_util import validate_config
from dane import Document, Task, Result
from dane.base_classes import base_worker
from dane.config import cfg
from dane.s3_util import validate_s3_uri
from models import CallbackResponse, Provenance
from io_util import (
    get_base_output_dir,
    get_source_id,
    get_s3_output_file_uri,
    obtain_input_file,
    get_download_dir,
    s3_download,
)
from pika.exceptions import ChannelClosedByBroker
from main_data_processor import (
    generate_input_for_feature_extraction,
    apply_desired_io_on_output,
)


"""
NOTE now the output dir created by by DANE (createDirs()) for the PATHS.OUT_FOLDER is not used:

- /mnt/dane-fs/output-files/03/d2/8a/03d28a03643a981284b403b91b95f6048576c234

Instead we put the output in:

- /mnt/dane-fs/output-files/visxp_prep/{source_id}
"""
logger = logging.getLogger()


# triggered by running: python worker.py --run-test-file
def process_configured_input_file():
    logger.info("Triggered processing of configured VISXP_PREP.TEST_INPUT_PATH")
    input_file_path = cfg.VISXP_PREP.TEST_INPUT_FILE
    if validate_s3_uri(input_file_path):
        download_result = s3_download(input_file_path)
        input_file_path = download_result.file_path if download_result else None

    if not input_file_path:
        logger.error("input file empty")
        sys.exit()

    proc_result = generate_input_for_feature_extraction(input_file_path)
    if proc_result.provenance:
        logger.info(
            f"Successfully processed example file in {proc_result.provenance.processing_time_ms}ms"
        )
        logger.info("Result ok, now applying the desired IO on the results")
        validated_output: CallbackResponse = apply_desired_io_on_output(
            input_file_path,
            proc_result,
            cfg.INPUT.DELETE_ON_COMPLETION,
            cfg.OUTPUT.DELETE_ON_COMPLETION,
            cfg.OUTPUT.TRANSFER_ON_COMPLETION,
        )
        logger.info("Results after applying desired I/O")
        logger.info(validated_output)
    else:
        logger.info(f"Error: {proc_result.state}: {proc_result.message}")


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
        if not self.validate_data_dirs(get_download_dir(), get_base_output_dir()):
            logger.info("ERROR: data dirs not configured properly")
            if not self.UNIT_TESTING:
                sys.exit()

        # we specify a queue name because every worker of this type should
        # listen to the same queue
        self.__queue_name = "VISXP_PREP"  # this is the queue that receives the work and NOT the reply queue
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

        # NOTE: cannot be automaticcally filled, because no git client is present
        if not self.generator:
            logger.info("Generator was None, creating it now")
            self.generator = {
                "id": "dane-video-segmentation-worker",
                "type": "Software",
                "name": "VISXP_PREP",
                "homepage": "https://github.com/beeldengeluid/dane-video-segmentation-worker",
            }

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
        logger.info("Receiving a task from the DANE server!")
        logger.info(task)
        logger.info(doc)

        # step 0: Create provenance object
        provenance = Provenance(
            activity_name="dane-video-segmenation-worker",
            activity_description="Apply VisXP prep to input media",
            start_time_unix=time(),
            processing_time_ms=-1,
            input_data={},
            output_data={},
            steps=[],
        )

        # obtain the input file
        download_result, download_provenance = obtain_input_file(self.handler, doc)
        if not download_result:
            return {
                "state": 500,
                "message": "Could not download the document content",
            }
        if download_provenance and provenance.steps:
            provenance.steps.append(download_provenance)

        input_file_path = download_result.file_path

        # step 3: submit the input file to hecate/etc
        proc_result = generate_input_for_feature_extraction(input_file_path)

        if proc_result.provenance and provenance.steps:
            provenance.steps.append(proc_result.provenance)

        validated_output: CallbackResponse = apply_desired_io_on_output(
            input_file_path,
            proc_result,
            self.DELETE_INPUT_ON_COMPLETION,
            self.DELETE_OUTPUT_ON_COMPLETION,
            self.TRANSFER_OUTPUT_ON_COMPLETION,
        )

        if validated_output.get("state", 500) == 200:
            logger.info(
                "applying IO on output went well, now finally saving to DANE index"
            )
            # step 9: save the results back to the DANE index
            self.save_to_dane_index(
                doc,
                task,
                get_s3_output_file_uri(get_source_id(input_file_path)),
                provenance=provenance,
            )
        return validated_output

    def save_to_dane_index(
        self,
        doc: Document,
        task: Task,
        s3_location: str,
        provenance: Provenance,
    ) -> None:
        logger.info("saving results to DANE, task id={0}".format(task._id))
        # TODO figure out the multiple lines per transcript (refresh my memory)
        r = Result(
            self.generator,
            payload={
                "doc_id": doc._id,
                "task_id": task._id if task else None,
                "doc_target_id": doc.target["id"],
                "doc_target_url": doc.target["url"],
                "s3_location": s3_location,
                "provenance": provenance.to_json(),
            },
            api=self.handler,
        )
        r.save(task._id)


# Start the worker
# passing --run-test-file will run the whole process on the file defined in cfg.VISXP_PREP.TEST_FILE
if __name__ == "__main__":
    from argparse import ArgumentParser
    from base_util import LOG_FORMAT

    # first read the CLI arguments
    parser = ArgumentParser(description="dane-video-segmentation-worker")
    parser.add_argument(
        "--run-test-file", action="store", dest="run_test_file", default="n", nargs="?"
    )
    parser.add_argument("--log", action="store", dest="loglevel", default="INFO")
    args = parser.parse_args()

    # initialises the root logger
    logging.basicConfig(
        stream=sys.stdout,  # configure a stream handler only for now (single handler)
        format=LOG_FORMAT,
    )

    # setting the loglevel
    log_level = args.loglevel.upper()
    logger.setLevel(log_level)
    logger.info(f"Logger initialized (log level: {log_level})")
    logger.info(f"Got the following CMD line arguments: {args}")

    # see if the test file must be run
    if args.run_test_file != "n":
        logger.info("Running main_data_processor with VISXP_PREP.TEST_INPUT_FILE ")
        if cfg.VISXP_PREP and cfg.VISXP_PREP.TEST_INPUT_FILE:
            process_configured_input_file()
        else:
            logger.error("Please configure an input file in VISXP_PREP.TEST_INPUT_FILE")
            sys.exit()
    else:
        logger.info("Starting the worker")
        # start the worker
        w = VideoSegmentationWorker(cfg)
        try:
            w.run()
        except ChannelClosedByBroker:
            """
            (406, 'PRECONDITION_FAILED - delivery acknowledgement on channel 1 timed out.
            Timeout value used: 1800000 ms.
            This timeout value can be configured, see consumers doc guide to learn more')
            """
            logger.critical(
                "Please increase the consumer_timeout in your RabbitMQ server"
            )
            w.stop()
        except (KeyboardInterrupt, SystemExit):
            w.stop()
