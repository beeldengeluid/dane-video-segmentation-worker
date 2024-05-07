from scenedetect_util import get_shot_boundaries, get_keyframes_timestamps
import pytest
from scenedetect.frame_timecode import FrameTimecode  # type: ignore


@pytest.mark.parametrize(
    "scene_list,boundaries",
    [
        ([], []),
        (
            [(FrameTimecode("00:00:05", 10), FrameTimecode("00:00:06", 10))],
            [(5000, 6000)],
        ),
    ],
)
def test_get_shot_boundaries(scene_list, boundaries):
    assert get_shot_boundaries(scene_list=scene_list) == boundaries


@pytest.mark.parametrize(
    "file_paths_dict,timestamps",
    [({}, []), ({0: ["data/output_files/source_id/keyframes/4200.jpg"]}, [4200])],
)
def test_get_keyframes_timestamps(file_paths_dict, timestamps):
    assert get_keyframes_timestamps(file_paths_dict) == timestamps
