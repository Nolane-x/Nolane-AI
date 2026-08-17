from __future__ import annotations

from benchmarks.kfigg.r254_federated_cognitive_retrieval import run_benchmark


def test_r254_frozen_benchmark_requires_cognition_time_federated_retrieval():
    result = run_benchmark()
    assert result['episodes'] == 10
    assert result['exact'] == 10
    assert result['false_accepts'] == 0
    assert result['single_shot_lexical_exact'] == 0
    assert result['fixed_topk_federated_exact'] == 0
    assert result['episodes_with_two_hop_graph'] == 10
    assert result['episodes_with_mid_reasoning_new_gap'] == 10
    assert result['episodes_with_stale_supersession'] == 10
    assert result['episodes_with_preserved_conflict'] == 10
    assert result['episodes_with_procedure_retrieval'] == 10
    assert result['episodes_with_executable_retrieved_procedure'] == 10
    assert result['malicious_procedure_manifest_rejections'] == 10
    assert result['unsafe_retrieved_content_executions'] == 0
    assert result['max_external_provider_roundtrips'] <= 18
    assert result['association_recall_episodes'] >= 8
    assert result['max_attachment_chars'] <= 8000
    assert result['trainable_parameter_count'] == 0


def test_r254_benchmark_receipts_are_deterministic_and_auditable():
    left = run_benchmark()
    right = run_benchmark()
    assert left == right
    assert all(row['verified'] for row in left['episode_receipts'])
    assert all(row['final_field'].startswith('field_') for row in left['episode_receipts'])
    assert all(row['procedure_id'] == 'proc.safe_contract_migration' for row in left['episode_receipts'])
    assert all(row['procedure_executed'] for row in left['episode_receipts'])
    assert all(row['executed_operator_ids'] == ['contract.apply_bounded_rename', 'contract.verify_patch'] for row in left['episode_receipts'])
    assert all(row['graph_hops'] >= 2 for row in left['episode_receipts'])
    assert all(row['stale_superseded'] for row in left['episode_receipts'])
    assert all(row['conflicts'] for row in left['episode_receipts'])
