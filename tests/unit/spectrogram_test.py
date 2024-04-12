import pytest
import shutil
from spectrogram import extract_audio_spectrograms
import os
from io_util import get_source_id
import numpy as np

MP4_INPUT_DIR = (
    "./tests/data/mp4s"  # any file in this dir will be subjected to this test
)
SPECTROGRAM_OUTPUT_DIR = (
    "./tests/data/spectrograms"  # will be cleaned up after each test run
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
    return f"{SPECTROGRAM_OUTPUT_DIR}/{source_id}_example_output"


def to_input_file(source_id: str) -> str:
    return f"{MP4_INPUT_DIR}/{source_id}.mp4"


def cleanup_output(source_id: str):
    output_path = to_output_dir(source_id)
    try:
        shutil.rmtree(output_path)
    except Exception:
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
            ],  # for now the same for each mp4
            TMP_OUTPUT_PATH,
        )
        for source_id in generate_source_ids()
    ],
)
def test_extract_audio_spectrograms(
    source_id: str, keyframe_timestamps: list, tmp_location: str
):
    media_file = to_input_file(source_id)
    example_output_path = to_output_dir(source_id)
    locations = {
        k: tmp_location for k in ["spectrograms", "spectrogram_images", "audio"]
    }
    sample_rate = 24000
    extract_audio_spectrograms(
        media_file=media_file,
        keyframe_timestamps=keyframe_timestamps,
        locations=locations,
        sample_rate=sample_rate,
        window_size_ms=1000,
        generate_images=False,  # TODO: Write test for this
        extract_audio=False,  # TODO: Write test for this
    )
    for i, timestamp in enumerate(keyframe_timestamps):
        # Load example spectrogram (following https://github.com/beeldengeluid/dane-visual-feature-extraction-worker/blob/main/example.py)
        example_path = os.path.join(example_output_path, f"{i}.npz")
        example_data = np.load(example_path, allow_pickle=True)
        example_spectrogram = example_data["arr_0"].item()["audio"]

        real_path = os.path.join(tmp_location, f"{timestamp}_{sample_rate}.npz")
        real_data = np.load(real_path, allow_pickle=True)
        real_spectrogram = real_data["arr_0"].item()["audio"]

        assert np.equal(real_spectrogram, example_spectrogram).all()
    # assert cleanup_output(source_id) # Do not clean up!
