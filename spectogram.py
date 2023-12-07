import numpy as np
from python_speech_features import logfbank  # type: ignore
import ffmpeg  # type: ignore
import logging
import os
from time import time
from typing import List
from dane.config import cfg
from dane.provenance import Provenance
from matplotlib import pyplot as plt
from media_file_util import (
    get_start_frame,
    get_end_frame,
    get_media_file_length,
)


logger = logging.getLogger(__name__)


# TODO this main function should be configurable via config.yml
def run(
    input_file_path: str, keyframe_timestamps: List[int], output_dirs: dict) -> Provenance:
    start_time = time()
    logger.info("Extracting audio spectograms")
    sample_rates = cfg.VISXP_PREP.SPECTOGRAM_SAMPLERATE_HZ

    spectogram_files = []
    for sample_rate in sample_rates:
        logger.info(f"Extracting {sample_rate}Hz spectograms")
        sf = extract_audio_spectograms(
            media_file=input_file_path,
            keyframe_timestamps=keyframe_timestamps,
            locations=output_dirs,
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
        input_data={
            "input_file_path": input_file_path,
            "keyframe_timestamps": str(keyframe_timestamps),
        },
        output_data={"spectogram_files": str(spectogram_files),
                     "spectogram_images": str(spectogram_images),
                     "audio_samples": str(audio_samples)},
    )


def get_raw_audio(media_file: str, sample_rate: int):
    out, _ = (
        ffmpeg.input(media_file)
        .output("-", format="s16le", acodec="pcm_s16le", ac=1, ar=sample_rate)
        .run(quiet=True)
    )
    raw_audio = np.frombuffer(out, np.int16)
    return raw_audio


"""
visxp  | 2023-12-04 15:06:11,636|INFO|8|spectogram|raw_audio_to_spectograms|71|104840, len = 2520064
visxp  | 2023-12-04 15:06:11,636|INFO|8|spectogram|raw_audio_to_spectograms|80|Extracting window at 104840 ms. Frames 2504160 to 2528160.
visxp  | 2023-12-04 15:06:11,652|INFO|8|spectogram|raw_audio_to_spectograms|86|Spectogram is a np array with dimensions: (1, 257, 66)
"""


def raw_audio_to_spectograms(
    raw_audio: np.ndarray,
    duration_ms: int,
    keyframe_timestamps: list[int],  # ms timestamps
    locations: dict,
    sample_rate,
    window_size_ms: int = 1000,
    z_normalize: bool = True,
    generate_image: bool = True
):
    fns = []
    for keyframe_ms in keyframe_timestamps:
        start_frame = get_start_frame(keyframe_ms, window_size_ms, sample_rate)
        end_frame = get_end_frame(keyframe_ms, window_size_ms, sample_rate)
        logger.info(
            f"Extracting window at {keyframe_ms} ms. Frames {start_frame} to {end_frame}."
        )
        spectogram = get_spec(raw_audio[start_frame:end_frame], sample_rate)
        logger.info(
            f"Spectogram is a np array with dimensions: {np.array(spectogram).shape}"
        )
        if generate_image:
            image_path = os.path.join(locations['spectogram_images'], f"{keyframe_ms}_{sample_rate}.jpg")
            generate_spec_image(spectogram=spectogram, destination=image_path)
        if z_normalize:
            spectogram = (spectogram - 1.93) / 17.89
        spec_path = os.path.join(locations['spectograms'], f"{keyframe_ms}_{sample_rate}.npz")
        out_dict = {"audio": spectogram}
        np.savez(spec_path, out_dict)  # type: ignore
        fns.append(spec_path)
    return fns


def generate_mp3_samples(
        media_file: str,
        location: str,
        keyframe_timestamps: list[int],
        window_size_ms: int = 1000,
        ):
    audio = ffmpeg.input(media_file)
    for timestamp in keyframe_timestamps:
        out_file = os.path.join(location, timestamp+'.mp3')
        from_time = (timestamp - window_size_ms // 2)
        to_time = (timestamp + window_size_ms // 2)
        audio.output(
                        out_file,
                        **{
                            "map": "0:a",
                            "c:a": "copy",
                            "ss": f"{from_time}ms",
                            "to": f"{to_time}ms",
                        },
                    ).run(quiet=True, overwrite_output=True)


def get_spec(wav_bit: np.ndarray, sample_rate: int):
    spec = logfbank(
        wav_bit, sample_rate, winlen=0.02, winstep=0.01, nfilt=257, nfft=1024
    )
    # Convert to 32-bit float and expand dim
    spec = spec.astype("float32")
    spec = spec.T
    spec = np.expand_dims(spec, axis=0)
    
    # spec = torch.as_tensor(spec) This will be done in the second worker
    # (so that we don't require torch in this one)
    return spec


def generate_spec_image(spectogram, destination):
    fft = np.abs(spectogram)
    fft[fft == 0] = 0.0000000000001 # prevent zero division
    fig = plt.figure(figsize=(64,64), dpi=10)
    ax = fig.add_subplot()
    ax.imshow(fft.squeeze(), norm='log',aspect='auto')
    plt.savefig(destination)
    plt.close()


def extract_audio_spectograms(
    media_file: str,
    keyframe_timestamps: list[int],
    locations: dict,
    sample_rate: int = 48000,
    window_size_ms: int = 1000,
):
    logger.info(f"Convert audio to wav at {sample_rate}Hz.")
    duration_ms = get_media_file_length(media_file)
    raw_audio = get_raw_audio(media_file=media_file, sample_rate=sample_rate)
    logger.info("obtain spectograms")
    fns = raw_audio_to_spectograms(
        raw_audio=raw_audio,
        duration_ms=duration_ms,
        keyframe_timestamps=keyframe_timestamps,
        locations= locations,
        sample_rate=sample_rate,
        window_size_ms=window_size_ms,
        z_normalize=True,
    )
    return fns
