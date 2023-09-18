import pytest
from spectogram_util import extract_audio_spectograms
import os
import numpy as np

DUMMY_FILE_PATH = "/src/tests/data/ZQWO_DYnq5Q_000000.mp4"
TMP_OUTPUT_PATH = "/tmp"
EXAMPLE_OUTPUT_PATH = "/src/tests/data/ZQWO_DYnq5Q_000000_example_output"


def generate_example_output(
    media_file=DUMMY_FILE_PATH, output_path=EXAMPLE_OUTPUT_PATH
):  # Copied from https://github.com/beeldengeluid/dane-visual-feature-extraction-worker/blob/main/example.py
    from pathlib import Path
    import wave
    import numpy as np
    from pydub import AudioSegment
    import tensorflow as tf

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

    # Convert MP4 to WAV
    audio = AudioSegment.from_file(media_file)
    audio.set_frame_rate(48000)
    wav_fn = os.path.join(output_path, "output.wav")
    audio.export(wav_fn, format="wav")

    # Read WAV file
    wav_file = wave.open(wav_fn)
    n_channels, sampwidth, framerate, n_frames = wav_file.getparams()[:4]
    data = wav_file.readframes(n_frames)
    raw_audio = np.frombuffer(data, dtype=np.int16)
    raw_audio = raw_audio.reshape((n_channels, n_frames), order="F")
    raw_audio = raw_audio.astype(np.float32) / 32768.0

    # Segment audio into 1 second chunks
    n_samples = raw_audio.shape[1]
    n_samples_per_second = 48000
    n_samples_per_chunk = n_samples_per_second
    n_chunks = int(n_samples / n_samples_per_chunk)
    chunks = []
    for i in range(n_chunks):
        chunks.append(
            raw_audio[:, i * n_samples_per_chunk : (i + 1) * n_samples_per_chunk]
        )

    # Compute spectrogram for each chunk
    spectrograms = []
    for chunk in chunks:
        spectrograms.append(raw_audio_to_spectrogram(chunk))

    # Save spectrogram to file
    for i, spectrogram in enumerate(spectrograms):
        spec_path =os.path.join(output_path, f'{i}.npz')
        out_dict = {"audio": spectrogram}
        np.savez(spec_path, out_dict)


def assert_example_output(example_output_path=EXAMPLE_OUTPUT_PATH, n_files: int=9):
    if not os.path.exists(example_output_path):
        os.makedirs(example_output_path)
    for i in range(n_files):
        if not os.path.isfile(os.path.join(example_output_path, f"{i}.npz")):
            return False
    return True


@pytest.mark.parametrize(
    "media_file, keyframe_timestamps, tmp_location, example_output_path",
    [
        (
            DUMMY_FILE_PATH,
            [500, 1500, 2500, 3500, 4500, 5500, 6500, 7500, 8500],  # , 9500],
            TMP_OUTPUT_PATH,
            EXAMPLE_OUTPUT_PATH,
        ),
    ],
)
def test_extract_audio_spectograms(
    media_file, keyframe_timestamps, tmp_location, example_output_path
):
    if not assert_example_output():
        generate_example_output()

    extract_audio_spectograms(
        media_file=media_file,
        keyframe_timestamps=keyframe_timestamps,
        location=tmp_location,
        tmp_location=tmp_location,
    )
    for i, timestamp in enumerate(keyframe_timestamps):
        # Load example spectogram (following https://github.com/beeldengeluid/dane-visual-feature-extraction-worker/blob/main/example.py)
        example_path = os.path.join(example_output_path, f"{i}.npz")
        example_data = np.load(example_path, allow_pickle=True)
        example_spectogram = example_data["arr_0"].item()["audio"]

        real_path = os.path.join(tmp_location, f'{timestamp}.npz')
        real_data = np.load(real_path, allow_pickle=True)
        real_spectogram = real_data["arr_0"].item()["audio"]

        assert np.equal(real_spectogram, example_spectogram).all()
