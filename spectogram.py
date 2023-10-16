import logging
import numpy as np
import os
from pydub import AudioSegment  # type: ignore
# import tensorflow as tf  # type: ignore
from time import time
from typing import List
import wave
from dane.config import cfg
from models import Provenance
from python_speech_features import logfbank  # type: ignore
import ffmpeg

logger = logging.getLogger(__name__)


# TODO this main function should be configurable via config.yml
def run(
    input_file_path: str, keyframe_timestamps: List[int], output_dir: str, tmp_dir: str
) -> Provenance:
    start_time = time()
    logger.info("Extracting audio spectograms")
    sample_rates = cfg.VISXP_PREP.SPECTOGRAM_SAMPLERATE_HZ

    spectogram_files = []
    for sample_rate in sample_rates:
        logger.info(f"Extracting {sample_rate}Hz spectograms")
        sf = extract_audio_spectograms(
            media_file=input_file_path,
            keyframe_timestamps=keyframe_timestamps,
            location=output_dir,
            tmp_location=tmp_dir,
            sample_rate=sample_rate,
            window_size_ms=cfg.VISXP_PREP.SPECTOGRAM_WINDOW_SIZE_MS,
        )
        spectogram_files.extend(sf)
    return Provenance(
        activity_name="Spectogram extraction",
        activity_description=(
            "Extract audio spectogram (Numpy array)"
            "corresponding to 1 sec. of audio around each listed keyframe"
        ),
        start_time_unix=start_time,
        processing_time_ms=time() - start_time,
        input={
            "input_file_path": input_file_path,
            "keyframe_timestamps": str(keyframe_timestamps),
        },
        output={"spectogram_files": str(spectogram_files)},
    )


def get_raw_audio(media_file:str, sample_rate:int, z_normalize:bool):
    out, _ = (
        ffmpeg
        .input(media_file)
        .output('-', format='s16le', acodec='pcm_s16le', ac=1, ar=sample_rate)
        .run(quiet=True)
    )
    raw_audio = np.frombuffer(out, np.int16)
    # if z_normalize:
    #     raw_audio = (raw_audio - 1.93) / 17.89
    return raw_audio


def raw_audio_to_spectograms(
    raw_audio: np.ndarray,
    keyframe_timestamps: list[int],  # ms timestamps
    location: str,
    sample_rate,
    window_size_ms: int = 1000,
):
    for keyframe in keyframe_timestamps:
        # TODO: edge case if keyframe is very close to start/end video
        from_frame = (keyframe - window_size_ms // 2) * sample_rate // 1000
        to_frame = (keyframe + window_size_ms // 2) * sample_rate // 1000
        logger.info(
            f"Extracting window at {keyframe} ms. Frames {from_frame} to {to_frame}."
        )
        fns = []
        spectogram = get_spec(raw_audio[from_frame:to_frame], sample_rate)
        logger.info(
            f"Spectogram is a np array with dimensions: {np.array(spectogram).shape}"
        )
        spec_path = os.path.join(location, f"{keyframe}_{sample_rate}.npz")
        out_dict = {"audio": spectogram}
        np.savez(spec_path, out_dict)  # type: ignore
        fns.append(spec_path)
    return fns


def get_spec(wav_bit, sample_rate):  
    spec = logfbank(wav_bit,
                    sample_rate,
                    winlen=0.02,
                    winstep=0.01,
                    nfilt=257,
                    nfft=1024
                    )
    
    # Convert to 32-bit float and expand dim
    spec = spec.astype('float32')
    spec = spec.T 
    spec = np.expand_dims(spec, axis=0)
    spec = (spec - 1.93) / 17.89 # TODO: do z-normalize elsehwere
    # spec = torch.as_tensor(spec) This will be done in the second worker
    # (so that we don't require torch in this one)
    return spec


def extract_audio_spectograms(
    media_file: str,
    keyframe_timestamps: list[int],
    location: str,
    tmp_location: str,
    sample_rate: int = 48000,
    window_size_ms: int = 1000,
):
    logger.info(f"Convert audio to wav at {sample_rate}Hz.")
    raw_audio = get_raw_audio(media_file=media_file, sample_rate=sample_rate, z_normalize=True)
    logger.info("obtain spectograms")
    fns = raw_audio_to_spectograms(
        raw_audio=raw_audio,
        keyframe_timestamps=keyframe_timestamps,
        location=location,
        sample_rate=sample_rate,
        window_size_ms=window_size_ms,
    )
    return fns


