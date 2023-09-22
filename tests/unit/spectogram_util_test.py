import pytest
import shutil
from spectogram_util import extract_audio_spectograms, raw_audio_to_spectrogram
import os
from base_util import get_source_id
import numpy as np

MP4_INPUT_DIR = (
    "./tests/data/mp4s"  # any file in this dir will be subjected to this test
)
SPECTOGRAM_OUTPUT_DIR = (
    "./tests/data/spectograms"  # will be cleaned up after each test run
)
TMP_OUTPUT_PATH = "/tmp"  # should be available on most systems


def generate_source_ids():
    mp4_files = []
    for root, dirs, files in os.walk(MP4_INPUT_DIR):
        for f in files:
            if f.find(".mp4") != -1:
                mp4_files.append(get_source_id(f))
    return mp4_files


def to_output_dir(source_id: str) -> str:
    return f"{SPECTOGRAM_OUTPUT_DIR}/{source_id}_example_output"


def to_input_file(source_id: str) -> str:
    return f"{MP4_INPUT_DIR}/{source_id}.mp4"


def cleanup_output(source_id: str):
    output_path = to_output_dir(source_id)
    try:
        shutil.rmtree(output_path)
    except Exception:
        return False
    return True


# Copied from https://github.com/beeldengeluid/dane-visual-feature-extraction-worker/blob/main/example.py
def generate_example_output(media_file: str, output_path: str):
    import wave
    import numpy as np
    from pydub import AudioSegment

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
    raw_audio = raw_audio.astype(np.float32) / 32768.0  # type: ignore

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
        spectrograms.append(raw_audio_to_spectrogram(chunk, sample_rate=48000))

    # Save spectrogram to file
    for i, spectrogram in enumerate(spectrograms):
        spec_path = os.path.join(output_path, f"{i}.npz")
        out_dict = {"audio": spectrogram}
        np.savez(spec_path, out_dict)  # type: ignore


def assert_example_output(output_path: str, n_files: int):
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    for i in range(n_files):
        if not os.path.isfile(os.path.join(output_path, f"{i}.npz")):
            return False
    return True


@pytest.mark.parametrize(
    "source_id, keyframe_timestamps, tmp_location",
    [
        (
            source_id,
            [
                500,
                1500,
                2500,
                3500,
                4500,
                5500,
                6500,
                7500,
                8500,
            ],  # for now the same for each mp4
            TMP_OUTPUT_PATH,
        )
        for source_id in generate_source_ids()
    ],
)
def test_extract_audio_spectograms(
    source_id: str, keyframe_timestamps: list, tmp_location: str
):
    media_file = to_input_file(source_id)
    output_path = to_output_dir(source_id)

    if not assert_example_output(output_path, len(keyframe_timestamps)):
        generate_example_output(media_file, output_path)

    extract_audio_spectograms(
        media_file=media_file,
        keyframe_timestamps=keyframe_timestamps,
        location=tmp_location,
        tmp_location=tmp_location,
        sample_rate=48000,
    )
    for i, timestamp in enumerate(keyframe_timestamps):
        # Load example spectogram (following https://github.com/beeldengeluid/dane-visual-feature-extraction-worker/blob/main/example.py)
        example_path = os.path.join(output_path, f"{i}.npz")
        example_data = np.load(example_path, allow_pickle=True)
        example_spectogram = example_data["arr_0"].item()["audio"]

        real_path = os.path.join(tmp_location, f"{timestamp}.npz")
        real_data = np.load(real_path, allow_pickle=True)
        real_spectogram = real_data["arr_0"].item()["audio"]

        assert np.equal(real_spectogram, example_spectogram).all()
    assert cleanup_output(source_id)
