from functools import reduce
import logging
import os
from time import time
from typing import List
from base_util import get_source_id
from dane.config import cfg
from models import Provenance


logger = logging.getLogger(__name__)


# Generates
def generate_full_provenance_chain(
    start_time: float, input_file_path: str, provenance_chain: List[Provenance]
) -> Provenance:
    provenance = Provenance(
        activity_name="VisXP prep",
        activity_description=(
            "Detect shots and keyframes, "
            "extract keyframes and corresponding audio spectograms"
        ),
        start_time_unix=start_time,
        processing_time_ms=start_time - time(),
        parameters=cfg.VISXP_PREP,
        steps=provenance_chain,
        software_version=obtain_software_versions(["dane-video-segmentation-worker"]),
        input={"input_file_path": input_file_path},
        output=reduce(
            lambda a, b: {**a, **b},
            [p.output for p in provenance_chain],
        ),
    )

    output_file = os.path.join(
        cfg.VISXP_PREP.OUTPUT_DIR, get_source_id(input_file_path), "provenance.json"
    )
    with open(output_file, "w+") as f:
        f.write(str(provenance.to_json()))
        logger.info(f"Wrote provenance info to file: {output_file}")
    return provenance


# NOTE: software_provenance.txt is created while building the container image (see Dockerfile)
def obtain_software_versions(software_names):
    if isinstance(software_names, str):  # wrap a single software name in a list
        software_names = [software_names]
    try:
        with open("/software_provenance.txt") as f:
            urls = (
                {}
            )  # for some reason I couldnt manage a working comprehension for the below - SV
            for line in f.readlines():
                name, url = line.split(";")
                if name.strip() in software_names:
                    urls[name.strip()] = url.strip()
            assert len(urls) == len(software_names)
            return urls
    except FileNotFoundError:
        logger.info(
            f"Could not read {software_names} version"
            f"from file /software_provenance.txt: file does not exist"
        )
    except ValueError as e:
        logger.info(
            f"Could not parse {software_names} version"
            f"from file /software_provenance.txt. {e}"
        )
    except AssertionError:
        logger.info(
            f"Could not find {software_names} version"
            f"in file /software_provenance.txt"
        )
