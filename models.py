from dane.provenance import Provenance
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, TypedDict


# These are the types of output this worker (possibly) provides (depending on configuration)
class OutputType(Enum):
    KEYFRAMES = "keyframes"  # produced by keyframe_extraction.py
    METADATA = "metadata"  # produced by scenedetect.py
    PROVENANCE = "provenance"  # produced by provenance.py
    SPECTROGRAMS = "spectrograms"  # produced by spectrogram.py
    AUDIO = "audio"  # produced by spectrogram.py
    SPECTROGRAM_IMAGES = "spectrogram_images"  # produced by spectrogram.py


class ScenedetectOutput(Enum):
    KEYFRAME_TIMESTAMPS = "keyframes_timestamps_ms.txt"
    SHOT_BOUNDARIES = "shot_boundaries_timestamps_ms.txt"


@dataclass
class MediaFile:
    file_path: str  # file location
    source_id: str  # serves as a unique processing ID


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
    media_file: Optional[MediaFile] = None
    provenance_chain: Optional[List[Provenance]] = None
