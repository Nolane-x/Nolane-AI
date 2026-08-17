from benchmarks.kfigg.r243_cross_family_macro_composition import DEV_SEEDS, HELDOUT_SEEDS, run_episode, run_suite


def test_dev_cross_family_recombination_is_exact_and_synergistic():
    rows = run_suite(DEV_SEEDS)
    assert len(rows) == 8
    assert all(row['accepted'] for row in rows)
    assert all(row['exact_truth_table'] for row in rows)
    assert not any(row['false_accept'] for row in rows)
    assert all(row['connective'] == 'and' for row in rows)
    assert all(row['synergy'] > 0.02 for row in rows)
    assert all(row['information_gain'] > row['best_parent_information_gain'] for row in rows)
    assert all(not row['left_parent_exact'] and not row['right_parent_exact'] for row in rows)


def test_frozen_heldout_recombination_transfers_under_atom_renaming():
    rows = run_suite(HELDOUT_SEEDS)
    assert len(rows) == 6
    assert sum(row['accepted'] and row['exact_truth_table'] for row in rows) == 6
    assert sum(row['false_accept'] for row in rows) == 0
    assert all(tuple(row['selected_macro_ids']) == ('pm:source-left-and', 'pm:source-right-or') for row in rows)


def test_composition_collapses_a_larger_raw_recombination_space():
    rows = run_suite(HELDOUT_SEEDS)
    # We do not claim raw cannot solve the target. We claim learned abstractions
    # reduce the bounded synthesis space while retaining exact truth-table proof.
    assert all(row['raw_semantic_space_size'] > row['composition_candidates_evaluated'] for row in rows)
    assert all(row['composition_candidates_evaluated'] <= 16 for row in rows)


def test_frozen_heldout_replay_is_deterministic():
    first = [run_episode(seed) for seed in HELDOUT_SEEDS]
    second = [run_episode(seed) for seed in HELDOUT_SEEDS]
    assert first == second
