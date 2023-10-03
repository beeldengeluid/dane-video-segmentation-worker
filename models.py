from dataclasses import dataclass
from enum import Enum
from typing import Optional, TypedDict


# These are the types of output this worker (possibly) provides (depending on configuration)
class OutputType(Enum):
    KEYFRAMES = "keyframes"  # produced by keyframe_extraction.py
    METADATA = "metadata"  # produced by hecate.py
    PROVENANCE = "provenance"  # produced by provenance.py
    SPECTOGRAMS = "spectograms"  # produced by spectogram.py
    TMP = "tmp"  # produced by spectogram.py


# Hecate outputs these files into OutputType.METADATA
class HecateOutput(Enum):
    KEYFRAME_INDICES = "keyframes_indices.txt"
    KEYFRAMES_TIMESTAMPS = "keyframes_timestamps_ms.txt"
    SHOT_BOUNDARIES = "shot_boundaries_timestamps_ms.txt"


# returned by callback()
class CallbackResponse(TypedDict):
    state: int
    message: str


@dataclass
class Provenance:
    activity_name: str
    activity_description: str
    start_time_unix: float
    processing_time_ms: float
    input: dict[str, str]
    output: dict[str, str]
    parameters: Optional[dict] = None
    software_version: Optional[dict[str, str]] = None
    steps: Optional[list["Provenance"]] = None  # a list of subactivity provenance items

    def to_json(self):
        return {
            "activity_name": self.activity_name,
            "activity_description": self.activity_description,
            "processing_time_ms": self.processing_time_ms,
            "start_time_unix": self.start_time_unix,
            "parameters": self.parameters,  # .to_json
            "software_version": self.software_version,  # .to_json
            "input": self.input,  # .to_json
            "output": self.output,  # .to_json
            "steps": [step.to_json for step in self.steps],
        }


# NOTE copied from dane-beng-download-worker (move this to DANE later)
@dataclass
class DownloadResult:
    file_path: str  # target_file_path,  # TODO harmonize with dane-download-worker
    download_time: float = -1  # time (secs) taken to receive data after request
    mime_type: str = "unknown"  # download_data.get("mime_type", "unknown"),
    content_length: int = -1  # download_data.get("content_length", -1),


@dataclass
class VisXPFeatureExtractionInput:
    state: int
    message: str
    processing_time: float
    provenance: Provenance


""" NOTE the output should contain the following dir structure + files
./testob/spectograms/22960_48000.npz
./testob/spectograms/19680_48000.npz
./testob/spectograms/9520_24000.npz
./testob/spectograms/85680_48000.npz
./testob/spectograms/18520_24000.npz

./testob/keyframes/101880.jpg
./testob/keyframes/40320.jpg
./testob/keyframes/85680.jpg

./testob/metadata/keyframes_timestamps_ms.txt
./testob/metadata/keyframes_indices.txt
./testob/metadata/shot_boundaries_timestamps_ms.txt

./testob/provenance.json --> change to ./testob/provenance/overal_provenance.json (possibly per processing unit a file as well)

./testob/tmp/output_24000.wav
./testob/tmp/output_48000.wav
"""
