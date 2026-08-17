from benchmarks.kfigg.r246_sparse_feedback_binding import HELDOUT_EPISODES, run_frozen_heldout, run_heldout_episode


def test_sparse_feedback_heldout_converges_without_dense_scoring():
    result = run_frozen_heldout()
    assert result['all_gates_pass'], result
    s = result['summary']
    assert s['episodes'] == len(HELDOUT_EPISODES) == 6
    assert s['exact'] == 6
    assert s['false_accepts'] == 0
    assert s['initial_tests_per_episode'] == 8
    assert s['max_feedback_fraction'] <= 0.25
    assert s['final_exhaustive_rows_per_episode'] == 256
    assert s['privileged_role_scopes_used'] is False


def test_sparse_feedback_protocol_is_stable_across_renamed_worlds():
    first = run_heldout_episode(HELDOUT_EPISODES[0])
    last = run_heldout_episode(HELDOUT_EPISODES[-1])
    assert first['exact'] and last['exact']
    assert first['initial_tests'] == last['initial_tests'] == 8
    assert first['observed_tests'] <= 64
    assert last['observed_tests'] <= 64
