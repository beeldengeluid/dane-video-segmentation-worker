from typing import Any, List
from yacs.config import CfgNode
import subprocess
import os
from pathlib import Path
import logging
import hashlib


LOG_FORMAT = "%(asctime)s|%(levelname)s|%(process)d|%(module)s|%(funcName)s|%(lineno)d|%(message)s"
logger = logging.getLogger(__name__)


def validate_config(config: CfgNode, validate_file_paths: bool = True) -> bool:
    try:
        __validate_environment_variables()
    except AssertionError as e:
        print("Error malconfigured worker: env vars incomplete")
        print(str(e))
        return False

    parent_dirs_to_check: List[str] = []  # parent dirs of file paths must exist
    # check the DANE.cfg (supplied by config.yml)
    try:
        # rabbitmq settings
        assert config.RABBITMQ, "RABBITMQ"
        assert check_setting(config.RABBITMQ.HOST, str), "RABBITMQ.HOST"
        assert check_setting(config.RABBITMQ.PORT, int), "RABBITMQ.PORT"
        assert check_setting(config.RABBITMQ.EXCHANGE, str), "RABBITMQ.EXCHANGE"
        assert check_setting(
            config.RABBITMQ.RESPONSE_QUEUE, str
        ), "RABBITMQ.RESPONSE_QUEUE"
        assert check_setting(config.RABBITMQ.USER, str), "RABBITMQ.USER"
        assert check_setting(config.RABBITMQ.PASSWORD, str), "RABBITMQ.PASSWORD"

        # Elasticsearch settings
        assert config.ELASTICSEARCH, "ELASTICSEARCH"
        assert check_setting(config.ELASTICSEARCH.HOST, list), "ELASTICSEARCH.HOST"
        assert (
            len(config.ELASTICSEARCH.HOST) == 1
            and type(config.ELASTICSEARCH.HOST[0]) is str
        ), "Invalid ELASTICSEARCH.HOST"

        assert check_setting(config.ELASTICSEARCH.PORT, int), "ELASTICSEARCH.PORT"
        assert check_setting(config.ELASTICSEARCH.USER, str, True), "ELASTICSEARCH.USER"
        assert check_setting(
            config.ELASTICSEARCH.PASSWORD, str, True
        ), "ELASTICSEARCH.PASSWORD"
        assert check_setting(config.ELASTICSEARCH.SCHEME, str), "ELASTICSEARCH.SCHEME"
        assert check_setting(config.ELASTICSEARCH.INDEX, str), "ELASTICSEARCH.INDEX"

        # DANE python lib settings
        assert config.PATHS, "PATHS"
        assert check_setting(config.PATHS.TEMP_FOLDER, str), "PATHS.TEMP_FOLDER"
        assert check_setting(config.PATHS.OUT_FOLDER, str), "PATHS.OUT_FOLDER"

        # the FILE_SYSTEM sub config
        assert config.FILE_SYSTEM, "FILE_SYSTEM"
        assert check_setting(
            config.FILE_SYSTEM.BASE_MOUNT, str
        ), "FILE_SYSTEM.BASE_MOUNT"
        assert check_setting(config.FILE_SYSTEM.INPUT_DIR, str), "FILE_SYSTEM.INPUT_DIR"
        assert check_setting(
            config.FILE_SYSTEM.OUTPUT_DIR, str
        ), "FILE_SYSTEM.OUTPUT_DIR"

        # Settings for this DANE worker
        assert config.VISXP_PREP, "VISXP_PREP sub-config missing"
        assert check_setting(
            config.VISXP_PREP.RUN_KEYFRAME_EXTRACTION, bool
        ), "VISXP_PREP.RUN_KEYFRAME_EXTRACTION"
        assert check_setting(
            config.VISXP_PREP.RUN_AUDIO_EXTRACTION, bool
        ), "VISXP_PREP.RUN_AUDIO_EXTRACTION"
        assert check_setting(
            config.VISXP_PREP.SPECTROGRAM_WINDOW_SIZE_MS, int
        ), "VISXP_PREP.SPECTROGRAM_WINDOW_SIZE_MS"
        assert check_setting(
            config.VISXP_PREP.SPECTROGRAM_SAMPLERATE_HZ, list
        ), "VISXP_PREP.SPECTROGRAM_SAMPLERATE_HZ"
        assert check_setting(
            config.VISXP_PREP.TEST_INPUT_FILE, str, True
        ), "VISXP_PREP.TEST_INPUT_FILE"

        # settings for input & output handling
        assert config.INPUT, "INPUT"
        assert check_setting(
            config.INPUT.DELETE_ON_COMPLETION, bool
        ), "INPUT.DELETE_ON_COMPLETION"

        assert config.OUTPUT, "OUTPUT"
        assert check_setting(
            config.OUTPUT.DELETE_ON_COMPLETION, bool
        ), "OUTPUT.DELETE_ON_COMPLETION"
        assert check_setting(
            config.OUTPUT.TRANSFER_ON_COMPLETION, bool
        ), "OUTPUT.TRANSFER_ON_COMPLETION"
        if config.OUTPUT.TRANSFER_ON_COMPLETION:
            # required only in case output must be transferred
            assert check_setting(
                config.OUTPUT.S3_ENDPOINT_URL, str
            ), "OUTPUT.S3_ENDPOINT_URL"
            assert check_setting(config.OUTPUT.S3_BUCKET, str), "OUTPUT.S3_BUCKET"
            assert check_setting(
                config.OUTPUT.S3_FOLDER_IN_BUCKET, str
            ), "OUTPUT.S3_FOLDER_IN_BUCKET"

        if "DANE_DEPENDENCIES" in config:
            assert __check_dane_dependencies(
                config.DANE_DEPENDENCIES
            ), "DANE_DEPENDENCIES"

        # validate file paths (not while unit testing)
        if validate_file_paths:
            __validate_parent_dirs(parent_dirs_to_check)
            __validate_dane_paths(config.PATHS.TEMP_FOLDER, config.PATHS.OUT_FOLDER)

    except AssertionError as e:
        print(f"Configuration error: {str(e)}")
        return False

    return True


def __validate_environment_variables() -> None:
    # self.UNIT_TESTING = os.getenv('DW_ASR_UNIT_TESTING', False)
    try:
        assert True  # TODO add secrets from the config.yml to the env
    except AssertionError as e:
        raise (e)


def __validate_dane_paths(dane_temp_folder: str, dane_out_folder: str) -> None:
    i_dir = Path(dane_temp_folder)
    o_dir = Path(dane_out_folder)

    try:
        assert os.path.exists(
            i_dir.parent.absolute()
        ), f"{i_dir.parent.absolute()} does not exist"
        assert os.path.exists(
            o_dir.parent.absolute()
        ), f"{o_dir.parent.absolute()} does not exist"
    except AssertionError as e:
        raise (e)


def check_setting(setting: Any, t: type, optional=False) -> bool:
    return (type(setting) is t and optional is False) or (
        optional and (setting is None or type(setting) is t)
    )


def __check_dane_dependencies(deps: Any) -> bool:
    deps_to_check: list = deps if type(deps) is list else []
    deps_allowed = ["DOWNLOAD"]
    return any(dep in deps_allowed for dep in deps_to_check)


def __validate_parent_dirs(paths: list) -> None:
    try:
        for p in paths:
            assert os.path.exists(
                Path(p).parent.absolute()
            ), f"Parent dir of file does not exist: {p}"
    except AssertionError as e:
        raise (e)


def run_shell_command(cmd: str) -> bytes:
    """Run cmd and return stdout"""
    logger.info(cmd)
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,  # needed to support file glob
        )

        stdout, stderr = process.communicate()
        assert process.returncode == 0
        logger.debug(stdout)
        logger.error(stderr)
        logger.info("Process is done: return stdout")
        return stdout

    except AssertionError:
        logger.error("Subprocess call was not successful. Abort.")
        raise

    except subprocess.CalledProcessError:
        logger.exception("CalledProcessError")
        raise Exception  # TODO use appropriate exception
    except Exception:
        logger.exception("Exception")
        raise Exception  # TODO use appropriate exception


def hash_string(s: str) -> str:
    return hashlib.sha224("{0}".format(s).encode("utf-8")).hexdigest()
