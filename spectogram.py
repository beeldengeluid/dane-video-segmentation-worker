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
from collections import defaultdict
from media_file_util import (
    get_start_frame,
    get_end_frame,
)


logger = logging.getLogger(__name__)


# TODO this main function should be configurable via config.yml
def run(
    input_file_path: str, 
    keyframe_timestamps: List[int], 
    output_dirs: dict,
    ) -> Provenance:
    start_time = time()
    logger.info("Extracting audio spectograms")

    spectogram_files = defaultdict(list)
    for sample_rate in cfg.VISXP_PREP.SPECTOGRAM_SAMPLERATE_HZ:
        logger.info(f"Extracting {sample_rate}Hz spectograms")
        sf = extract_audio_spectograms(
            media_file=input_file_path,
            keyframe_timestamps=keyframe_timestamps,
            locations=output_dirs,
            sample_rate=sample_rate,
            window_size_ms=cfg.VISXP_PREP.SPECTOGRAM_WINDOW_SIZE_MS,
            generate_images=cfg.VISXP_PREP.GENERATE_SPECTOGRAM_IMAGES,
            extract_audio=cfg.VISXP_PREP.EXTRACT_AUDIO_SAMPLES,
        )
        for k, v in sf.items():
            spectogram_files[k].extend(v)
    return Provenance(
        activity_name="Spectogram extraction",
        activity_description=(
            "Extract audio spectogram (Numpy array)"
            "corresponding to 1 sec. of audio around each listed keyframe"
            "Optionally, also extract the audio to mp3 and generate spectogram image"
        ),
        start_time_unix=start_time,
        processing_time_ms=time() - start_time,
        input_data={
            "input_file_path": input_file_path,
            "keyframe_timestamps": str(keyframe_timestamps),
        },
        output_data={"spectogram_files": str(spectogram_files['spectograms']),
                     "spectogram_images": str(spectogram_files['images']),
                     "audio_samples": str(spectogram_files['audio']),},
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
    keyframe_timestamps: list[int],  # ms timestamps
    locations: dict,
    sample_rate: int,
    window_size_ms: int,
    z_normalize: bool,
    generate_image: bool
):
    fns = defaultdict(list)
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
            fns['images'].append(image_path)
        if z_normalize:
            spectogram = (spectogram - 1.93) / 17.89
        spec_path = os.path.join(locations['spectograms'], f"{keyframe_ms}_{sample_rate}.npz")
        out_dict = {"audio": spectogram}
        np.savez(spec_path, out_dict)  # type: ignore
        fns['spectograms'].append(spec_path)
    return fns


def generate_mp3_samples(
        media_file: str,
        location: str,
        keyframe_timestamps: list[int],
        window_size_ms: int,
        ):
    audio = ffmpeg.input(media_file)
    fns = []
    for timestamp in keyframe_timestamps:
        out_file = os.path.join(location, f"{timestamp}.mp3")
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
                    ).run(quiet=False, overwrite_output=True)
        fns.append(out_file)
    return fns


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
    sample_rate: int,
    window_size_ms: int,
    generate_images: bool, 
    extract_audio: bool
):
    logger.info(f"Convert audio to wav at {sample_rate}Hz.")
    raw_audio = get_raw_audio(media_file=media_file, sample_rate=sample_rate)
    logger.info("obtain spectograms")
    fns = raw_audio_to_spectograms(
        raw_audio=raw_audio,
        keyframe_timestamps=keyframe_timestamps,
        locations= locations,
        sample_rate=sample_rate,
        window_size_ms=window_size_ms,
        z_normalize=True,
        generate_image=generate_images
    )
    if extract_audio:
        audio_files = generate_mp3_samples(
            media_file= media_file, 
            keyframe_timestamps=keyframe_timestamps, 
            location= locations['audio'],
            window_size_ms=window_size_ms)
        fns['audio'] = audio_files
    return fns
