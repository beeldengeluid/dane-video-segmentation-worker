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


def make_spectrogram(
    audio,  # some waveform of shape 1 x n_samples, tensorflow tensor
    mel_sample_rate,
    stft_length=2048,
    stft_step=1024,
    stft_pad_end=True,
    use_mel=True,
    mel_lower_edge_hertz=80.0,
    mel_upper_edge_hertz=7600.0,
    mel_num_bins=40,
    use_log=True,
    log_eps=1.0,
    log_scale=10000.0,
):
    """Computes (mel) spectrograms for signals t."""

    stfts = tf.signal.stft(
        audio,
        frame_length=stft_length,
        frame_step=stft_step,
        fft_length=stft_length,
        pad_end=stft_pad_end,
    )
    spectrogram = tf.abs(stfts)
    if use_mel:
        num_spectrogram_bins = spectrogram.shape[-1]
        linear_to_mel_weight_matrix = tf.signal.linear_to_mel_weight_matrix(
            mel_num_bins,
            num_spectrogram_bins,
            float(mel_sample_rate),
            mel_lower_edge_hertz,
            mel_upper_edge_hertz,
        )
        spectrogram = tf.tensordot(spectrogram, linear_to_mel_weight_matrix, 1)
        spectrogram.set_shape(
            spectrogram.shape[:-1] + linear_to_mel_weight_matrix.shape[-1:]
        )

    if use_log:
        spectrogram = tf.math.log(log_eps + log_scale * spectrogram)
    return spectrogram


def raw_audio_to_spectrogram(
    raw_audio,  # some waveform of shape 1 x n_samples, tensorflow tensor
    sample_rate,
    stft_length=0.032,
    stft_step=0.016,
    mel_bins=80,
    rm_audio=False,
):
    """Computes audio spectrogram and eventually removes raw audio."""
    stft_length = int(sample_rate * stft_length)
    stft_step = int(sample_rate * stft_step)
    mel_spectrogram = make_spectrogram(
        audio=raw_audio,
        mel_sample_rate=sample_rate,
        stft_length=stft_length,
        stft_step=stft_step,
        mel_num_bins=mel_bins,
        use_mel=True,
    )
    return mel_spectrogram


def get_raw_audio(media_file:str, sample_rate:int, z_normalize:bool):
    out, _ = (
        ffmpeg
        .input(media_file)
        .output('-', format='s16le', acodec='pcm_s16le', ac=1, ar=sample_rate)
        .run(quiet=True)
    )
    raw_audio = np.frombuffer(out, np.int16)
    if z_normalize:
        raw_audio = (raw_audio - 1.93) / 17.89
    return raw_audio


def wav_to_raw_audio(wav_file_location: str):
    wav_file = wave.open(wav_file_location, "r")
    n_channels, sampwidth, _frame_rate, n_frames = wav_file.getparams()[:4]
    logger.info(f"Wav framerate is {_frame_rate}.")
    data = wav_file.readframes(n_frames)
    raw_audio = (
        np.frombuffer(data, dtype=np.int16)
        .reshape((n_channels, n_frames), order="F")
        .astype(np.float32)
        / 32768.0  # normalize
    )
    return raw_audio


def convert_audiobit_to_wav(media_file: str, target_location: str, sample_rate: int):
    # audio = AudioSegment.from_file(media_file)
    audio = AudioSegment.from_file(media_file)
    logger.info(f"Converting. Original rate is {audio.frame_rate}")
    audio = audio.set_frame_rate(sample_rate)
    audio = audio.set_channels(1)
    audio.export(target_location, format="wav")


def raw_audio_to_spectograms(
    raw_audio: np.ndarray,
    keyframe_timestamps: list[int],  # ms timestamps
    location: str,
    sample_rate,
    window_size_ms: int = 1000,
):
    # margin = int(
    #     (window_size_ms / 2000) * frame_rate
    # )  # Margin is 1/2 window. Framerate per second, window size in ms.

    for keyframe in keyframe_timestamps:
        # TODO: edge case if keyframe is very close to start/end video
        from_frame = (keyframe - window_size_ms // 2) * sample_rate // 1000
        to_frame = (keyframe + window_size_ms // 2) * sample_rate // 1000
        logger.info(
            f"Extracting window at {keyframe} ms. Frames {from_frame} to {to_frame}."
        )
        fns = []
        audio_bit = raw_audio[from_frame:to_frame]
        # spectogram = raw_audio_to_spectrogram(audio_bit, sample_rate=sample_rate)
        spectogram = get_spec(audio_bit, sample_rate)
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
    convert_audiobit_to_wav(
        media_file=media_file,
        target_location=os.path.join(tmp_location, f"output_{sample_rate}.wav"),
        sample_rate=sample_rate,
    )
    logger.info("obtain spectograms")
    fns = raw_audio_to_spectograms(
        raw_audio=raw_audio,
        keyframe_timestamps=keyframe_timestamps,
        location=location,
        sample_rate=sample_rate,
        window_size_ms=window_size_ms,
    )
    return fns


def main():
    import hecate
    import sys
    from models import HecateOutput
        # initialises the root logger
    logging.basicConfig(
        stream=sys.stdout,  # configure a stream handler only for now (single handler)
        format="%(asctime)s|%(levelname)s|%(process)d|%(module)s|%(funcName)s|%(lineno)d|%(message)s",
    )
    logger.info('Going to start')
    # keyframe_timestamps = hecate.get_output(
    #          'data/output-files/visxp_prep/ZQWO_DYnq5Q_000000/metadata/', 
    #          hecate_output_type=HecateOutput.KEYFRAMES_TIMESTAMPS)
    keyframe_timestamps = [500,1500,2500,3500,4500,5500,6500,7500,8500,9500]

    extract_audio_spectograms(
            media_file='data/ZQWO_DYnq5Q_000000.mp4',
            keyframe_timestamps=keyframe_timestamps,
            location='tmp',
            tmp_location='tmp',
            sample_rate=24000,
            window_size_ms=1000,
        )
    
    
if __name__ == '__main__': 
    main()
