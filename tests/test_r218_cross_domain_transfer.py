from benchmarks.kfigg.r218_cross_domain_transfer import run_r218


def test_dev_run_requires_every_transfer_and_governance_gate():
    result = run_r218(21801)
    assert result['status'] == 'accepted'
    assert result['source_transfer']['survivors'] == ['source_target']
    assert result['external_transfer']['survivors'] == ['target_nist_fips197']
    assert result['external_transfer']['route_before_evidence'] == 'trial'
    assert result['external_transfer']['route_after_evidence'] == 'active'
    assert result['external_transfer']['core_ablation_false_survivors'] >= 4
    assert result['negative_transfer']['alien_route_after_failure'] == []
    assert result['negative_transfer']['source_route_after_failure'] == 'active'
    assert result['negative_transfer']['alien_state'] == 'quarantined'
    assert result['deduplication']['capacity_before_duplicate'] == result['deduplication']['capacity_after_duplicate']
    assert result['deduplication']['record_count_after_duplicate'] == result['deduplication']['record_count_before_duplicate']
    assert result['capacity_governance']['within_budget']
    assert result['capacity_governance']['target_skill_retained']
    assert result['rollback']['records_exactly_restored']
    assert result['rollback']['new_audit_version']
    assert not result['claims']['agi_claim']
    assert not result['claims']['broad_generalization_claim']


def test_dev_run_is_bitwise_deterministic_for_same_seed():
    assert run_r218(21817) == run_r218(21817)


def test_multiple_dev_seeds_preserve_semantics_without_reusing_heldout_ids():
    rows = [run_r218(seed) for seed in (21803, 21809, 21823)]
    assert all(row['status'] == 'accepted' for row in rows)
    assert len({row['seed'] for row in rows}) == 3
    assert all(row['all_gates_pass'] for row in rows)
