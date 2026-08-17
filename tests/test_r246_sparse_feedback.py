from cogcoder.r246_sparse_feedback import _default_initial_test_ids


def test_initial_sparse_anchor_selection_is_target_independent_and_bounded():
    ids = tuple(f't{i:03d}' for i in range(256))
    anchors = _default_initial_test_ids(ids)
    assert len(anchors) == 8
    assert len(set(anchors)) == 8
    assert set(anchors) <= set(ids)
    assert anchors == _default_initial_test_ids(tuple(reversed(ids)))


def test_small_suite_uses_each_available_test_once():
    ids = ('a', 'b', 'c')
    assert _default_initial_test_ids(ids) == ids
