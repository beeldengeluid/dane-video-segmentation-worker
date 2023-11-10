from dane.provenance import Provenance
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, TypedDict


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
    provenance_chain: Optional[List[Provenance]]
