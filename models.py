from dataclasses import dataclass
from typing import Optional


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
    steps: Optional[list['Provenance']] = None  # a list of subactivity provenance items

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
            "steps": [step.to_json for step in self.steps]
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
