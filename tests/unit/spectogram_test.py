import pytest
import shutil
from spectogram import extract_audio_spectograms
import os
from io_util import get_source_id
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
def test_extract_audio_spectograms(
    source_id: str, keyframe_timestamps: list, tmp_location: str
):
    media_file = to_input_file(source_id)
    example_output_path = to_output_dir(source_id)

    sample_rate = 24000
    extract_audio_spectograms(
        media_file=media_file,
        keyframe_timestamps=keyframe_timestamps,
        location=tmp_location,
        tmp_location=tmp_location,
        sample_rate=sample_rate,
    )
    for i, timestamp in enumerate(keyframe_timestamps):
        # Load example spectogram (following https://github.com/beeldengeluid/dane-visual-feature-extraction-worker/blob/main/example.py)
        example_path = os.path.join(example_output_path, f"{i}.npz")
        example_data = np.load(example_path, allow_pickle=True)
        example_spectogram = example_data["arr_0"].item()["audio"]

        real_path = os.path.join(tmp_location, f"{timestamp}_{sample_rate}.npz")
        real_data = np.load(real_path, allow_pickle=True)
        real_spectogram = real_data["arr_0"].item()["audio"]

        assert np.equal(real_spectogram, example_spectogram).all()
    # assert cleanup_output(source_id) # Do not clean up!
