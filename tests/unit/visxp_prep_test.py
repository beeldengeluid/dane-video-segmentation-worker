from visxp_prep import _filter_edge_keyframes


def test_filter_edge_keyframes():
    fps = 29.97
    duration = 10
    framecount = int(duration * fps)
    edge_1 = int(fps / 2)  # 14
    edge_2 = int(framecount - fps / 2)  # 284
    # fmt: off
    frame_indices = [
        -2, 0, 3, edge_1,  # too close to the start
        edge_1 + 1, 29, 30, 100, edge_2,  # OK
        edge_2 + 1, framecount, framecount + 1  # too close to the end
    ]
    # fmt: on
    expected_result = [edge_1 + 1, 29, 30, 100, edge_2]
    result = _filter_edge_keyframes(frame_indices, fps=fps, framecount=framecount)
    assert result == expected_result
