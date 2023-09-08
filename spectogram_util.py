import wave
import numpy as np
from pydub import AudioSegment
import tensorflow as tf
import logging
import os

logger = logging.getLogger(__name__)


def make_spectrogram(
    audio,  # some waveform of shape 1 x n_samples, tensorflow tensor
    stft_length=2048,
    stft_step=1024,
    stft_pad_end=True,
    use_mel=True,
    mel_lower_edge_hertz=80.0,
    mel_upper_edge_hertz=7600.0,
    mel_sample_rate=48000.0,
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
            mel_sample_rate,
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
    sample_rate=48000,
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


def wav_to_raw_audio(wav_file_location: str):
    wav_file = wave.open(wav_file_location, "r")
    n_channels, sampwidth, framerate, n_frames = wav_file.getparams()[:4]
    data = wav_file.readframes(n_frames)
    raw_audio = np.frombuffer(data, dtype=np.int16)
    raw_audio = raw_audio.reshape((n_channels, n_frames), order="F")
    raw_audio = raw_audio.astype(np.float32) / 32768.0
    return raw_audio


def convert_audiobit_to_wav(media_file: str, target_location: str, frame_rate=48000):
    audio = AudioSegment.from_file(media_file)
    audio.set_frame_rate(frame_rate)
    audio.export(target_location, format="wav")


def raw_audio_to_spectograms(
    raw_audio: np.array,
    keyframe_timestamps: list[int],
    location: str,
    frame_rate: int = 48000,
    window_size_ms: int = 1000,
):
    margin = int(
        (window_size_ms / 2000) * frame_rate
    )  # Margin is 1/2 window. Framerate per second, window size in ms.

    for keyframe in keyframe_timestamps:
        spectogram = raw_audio_to_spectrogram(  # TODO: edge case if keyframe is very close to start/end video
            raw_audio[
                :, keyframe * frame_rate - margin : keyframe * frame_rate + margin
            ]
        )
        np.array(spectogram).tofile(os.path.join(location, f"{keyframe}.npz"))


def extract_audio_spectograms(
    media_file: str, keyframe_timestamps: list[int], location: str, tmp_location: str
):
    logger.info("Convert to wav.")
    convert_audiobit_to_wav(
        media_file=media_file, target_location=os.path.join(tmp_location, "output.wav")
    )
    logger.info("obtain spectograms")
    raw_audio_to_spectograms(
        wav_to_raw_audio(os.path.join(tmp_location, "output.wav")),
        keyframe_timestamps=keyframe_timestamps,
        location=location,
    )
