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
        output_data={
            "spectogram_files": str(spectogram_files["spectograms"]),
            "spectogram_images": str(spectogram_files["images"]),
            "audio_samples": str(spectogram_files["audio"]),
        },
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
    generate_image: bool,
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
            image_path = os.path.join(
                locations["spectogram_images"], f"{keyframe_ms}_{sample_rate}.jpg"
            )
            generate_spec_image(spectogram=spectogram, destination=image_path)
            fns["images"].append(image_path)
        if z_normalize:
            spectogram = (spectogram - 1.93) / 17.89
        spec_path = os.path.join(
            locations["spectograms"], f"{keyframe_ms}_{sample_rate}.npz"
        )
        out_dict = {"audio": spectogram}
        np.savez(spec_path, out_dict)  # type: ignore
        fns["spectograms"].append(spec_path)
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
        from_time = timestamp - window_size_ms // 2
        to_time = timestamp + window_size_ms // 2
        audio.output(
            out_file,
            **{
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
    fft[fft == 0] = 0.0000000000001  # prevent zero division
    fig = plt.figure(figsize=(64, 64), dpi=10)
    ax = fig.add_subplot()
    ax.imshow(fft.squeeze(), norm="log", aspect="auto")
    plt.savefig(destination)
    plt.close()


def extract_audio_spectograms(
    media_file: str,
    keyframe_timestamps: list[int],
    locations: dict,
    sample_rate: int,
    window_size_ms: int,
    generate_images: bool,
    extract_audio: bool,
):
    logger.info(f"Convert audio to wav at {sample_rate}Hz.")
    raw_audio = get_raw_audio(media_file=media_file, sample_rate=sample_rate)
    logger.info("obtain spectograms")
    fns = raw_audio_to_spectograms(
        raw_audio=raw_audio,
        keyframe_timestamps=keyframe_timestamps,
        locations=locations,
        sample_rate=sample_rate,
        window_size_ms=window_size_ms,
        z_normalize=True,
        generate_image=generate_images,
    )
    if extract_audio:
        audio_files = generate_mp3_samples(
            media_file=media_file,
            keyframe_timestamps=keyframe_timestamps,
            location=locations["audio"],
            window_size_ms=window_size_ms,
        )
        fns["audio"] = audio_files
    return fns


if __name__ == "__main__":
    media_file = (
        "data/input-files/1411058.1366653.WEEKNUMMER404-HRE000042FF_924200_1089200.mp4"
    )
    keyframe_timestamps = [
        2680,
        3640,
        3800,
        3960,
        4640,
        5640,
        6640,
        8200,
        8600,
        9280,
        10600,
        11640,
        12640,
        13240,
        13320,
        13440,
        13880,
        14320,
        14640,
        15760,
        16000,
        16240,
        16600,
        17320,
        18080,
        19000,
        20640,
        21560,
        23080,
        23640,
        23840,
        24840,
        25600,
        26000,
        27000,
        27840,
        28080,
        28280,
        29200,
        29360,
        29600,
        29760,
        29880,
        30040,
        30280,
        30360,
        30560,
        30600,
        30960,
        31600,
        31760,
        31840,
        32080,
        32440,
        32560,
        32720,
        32760,
        32840,
        32960,
        33080,
        33360,
        33400,
        33560,
        34600,
        35560,
        37600,
        38560,
        39360,
        40560,
        44520,
        44760,
        45160,
        47520,
        49880,
        51520,
        52560,
        54520,
        54920,
        56000,
        56360,
        57200,
        57520,
        58520,
        58960,
        59480,
        60080,
        60280,
        60880,
        63720,
        64080,
        64160,
        64280,
        64480,
        64520,
        64800,
        64880,
        65000,
        65120,
        65240,
        65320,
        65440,
        65480,
        65600,
        68480,
        71520,
        72120,
        72520,
        74920,
        75040,
        75520,
        75720,
        76440,
        77360,
        77440,
        77760,
        77960,
        78160,
        78280,
        78480,
        78840,
        78960,
        79120,
        79880,
        81200,
        81480,
        82240,
        82440,
        82480,
        82560,
        82720,
        82800,
        83040,
        83120,
        83200,
        83280,
        83480,
        84120,
        84280,
        84480,
        84720,
        85040,
        85120,
        85200,
        85440,
        86280,
        86440,
        86480,
        87480,
        87560,
        87720,
        87760,
        88040,
        88120,
        89120,
        89280,
        89360,
        89440,
        89560,
        91000,
        92560,
        95400,
        97040,
        98440,
        100400,
        100880,
        101680,
        101720,
        102440,
        102800,
        102960,
        103240,
        103280,
        103400,
        103440,
        103520,
        103720,
        103760,
        103880,
        103960,
        104120,
        104400,
        104800,
        105080,
        105960,
        106120,
        106200,
        106280,
        106360,
        106400,
        107960,
        108040,
        108400,
        108720,
        108960,
        109080,
        109200,
        109280,
        109560,
        109800,
        110200,
        110360,
        110400,
        110560,
        110640,
        111640,
        111960,
        112360,
        113640,
        113960,
        114480,
        114520,
        115560,
        115800,
        115880,
        116400,
        116560,
        116680,
        117120,
        117240,
        117360,
        117400,
        117480,
        117560,
        117640,
        117800,
        117960,
        118120,
        118400,
        118640,
        118880,
        118960,
        119400,
        120360,
        120720,
        120760,
        122400,
        124360,
        126360,
        130360,
        132480,
        132720,
        132800,
        132920,
        132960,
        133200,
        133320,
        133360,
        133560,
        133640,
        133720,
        133920,
        134360,
        134520,
        134680,
        135000,
        135080,
        135160,
        135360,
        135560,
        135640,
        135720,
        135800,
        135880,
        135920,
        136040,
        136320,
        136360,
        136480,
        136560,
        136840,
        137120,
        137200,
        137360,
        137440,
        137720,
        137880,
        137920,
        138200,
        138320,
        138600,
        138760,
        138800,
        139320,
        139480,
        139720,
        139800,
        139880,
        139960,
        140040,
        140080,
        140200,
        140240,
        140320,
        140480,
        140600,
        140720,
        140840,
        140920,
        140960,
        141040,
        141200,
        141240,
        141320,
        141520,
        141560,
        141640,
        141840,
        141920,
        142080,
        142120,
        142320,
        142360,
        142480,
        142520,
        142600,
        142720,
        142920,
        143040,
        143120,
        143240,
        143320,
        143480,
        143520,
        143640,
        143680,
        143760,
        143840,
        143920,
        144040,
        144080,
        144280,
        144320,
        144400,
        144640,
        144720,
        144760,
        144840,
        145000,
        145080,
        145120,
        145200,
        145320,
        145480,
        145560,
        145640,
        145960,
        146080,
        146120,
        146200,
        146280,
        146360,
        146480,
        146520,
        146640,
        146800,
        146840,
        147040,
        147240,
        147320,
        147400,
        147560,
        147680,
        147800,
        147840,
        148280,
        148320,
        148480,
        148640,
        149280,
        150280,
        151000,
        151240,
        151280,
        151720,
        151960,
        152280,
        152600,
        152920,
        153320,
        154280,
        154600,
        155120,
        155320,
        155440,
        156040,
        156640,
        156840,
        157000,
        157280,
        159280,
        159320,
        160280,
        161080,
        161920,
        162240,
        163240,
        164080,
        164240,
    ]
    location = "data/test_mp3"
    window_size_ms = 1000
    generate_mp3_samples(
        media_file=media_file,
        location=location,
        keyframe_timestamps=keyframe_timestamps,
        window_size_ms=window_size_ms,
    )
