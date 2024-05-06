from scenedetect_util import get_shot_boundaries
import pytest

@pytest.mark.parametrize("scene_list,boundaries", [
    ([],[]),
    ])
def test_get_shot_boundaries(scene_list, boundaries):
    assert get_shot_boundaries(scene_list=scene_list) == boundaries
