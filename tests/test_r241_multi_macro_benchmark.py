import benchmarks.kfigg.r241_multi_macro_competition as b


def test_macro_library_is_learned_and_contains_multiple_non_equivalent_abstractions():
    macros = b.learn_r241_macro_library()
    assert len(macros) >= 2
    assert len({m.template.probe_id for m in macros}) == len(macros)
    assert all(m.support >= 2 for m in macros)
    assert all(m.compression_gain > 0 for m in macros)
    assert len({m.template.op for m in macros}) >= 2


def test_development_geometry_is_fresh_non_bit_and_high_reliability_shift():
    result = b.run_dev_matrix()
    assert result['family'] == 'z3_dual_semantic'
    assert result['regimes'] == ['multi_clean', 'semantic_shift']
    assert min(result['summary']['semantic_shift_reported_reliabilities']) >= 0.95
    assert result['summary']['semantic_shift_flip_count'] > 0


def test_competitive_router_passes_frozen_development_causal_gates():
    result = b.run_dev_matrix()
    assert result['all_gates_pass']
    assert result['gates']['competitive_all_correct']
    assert result['gates']['zero_false_accepts']
    assert result['gates']['strict_gain_over_single_or_unconditional']
    assert result['gates']['not_worse_than_no_macro']
    assert result['gates']['same_budgets']


def test_multi_macro_and_raw_routes_are_all_exercised_with_selective_demotion():
    result = b.run_dev_matrix()
    s = result['summary']
    assert len(s['competitive_macro_ids']) >= 2
    assert s['competitive_raw_route_count'] > 0
    assert s['selective_demotion_episodes'] > 0
    assert s['peer_preservation_episodes'] > 0


def test_semantic_shift_counterexample_failure_recovers_by_local_macro_quarantine():
    row = b.run_dev_episode(859, 'semantic_shift', 'competitive_calibrated')
    assert row['correct']
    assert row['semantic_shift_flip_count'] > 0
    assert len(row['quarantined_macro_ids']) == 1
    assert set(row['selected_macro_ids']) - set(row['quarantined_macro_ids'])


def test_unexposed_shift_macro_is_not_spuriously_quarantined():
    row = b.run_dev_episode(857, 'semantic_shift', 'competitive_calibrated')
    shifted = next(m.macro_id for m in b.learn_r241_macro_library() if m.template.op == 'eq' and any(
        child is not None and child.op == 'const3' and int(child.const_value) == 1
        for child in (m.template.left, m.template.right)
    ))
    assert row['correct']
    assert row['semantic_shift_flip_count'] == 0
    assert shifted not in row['selected_macro_ids']
    assert row['quarantined_macro_ids'] == []
    assert len(row['selected_macro_ids']) >= 2
