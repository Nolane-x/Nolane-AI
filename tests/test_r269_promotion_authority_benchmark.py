from __future__ import annotations

import hashlib

from benchmarks.kfigg.r269_promotion_authority import run_promotion_authority_benchmark


def test_host_authority_bound_promotion_reuse_and_exact_rollback():
    result = run_promotion_authority_benchmark(
        authority_root_digest=hashlib.sha256(b'r269-promotion-authority-test-root').hexdigest(),
        hosted_run_identity='pytest:r269-promotion-authority',
        source_tree_digest=hashlib.sha256(b'r269-promotion-authority-test-tree').hexdigest(),
    )
    assert result['milestone'] == 'R2.69'
    assert result['capability'] == 'host-authority-bound-scoped-promotion-and-rollback'
    assert result['source_adapter_type'] == 'verified_meta_episode_v1'
    assert result['source_meta_episode_passed'] is True
    assert result['heldout_targets'] == 8
    assert result['champion_accepted_targets'] == 8
    assert (
        result['champion_accepted_targets'] > result['challenger_accepted_targets']
        or result['oracle_call_advantage'] > 0
        or result['search_work_advantage'] > 0
    )
    assert result['false_accepts'] == 0
    assert result['promotion_accepted'] is True
    assert result['promotion_reason'] == 'scoped_promotion_accepted'
    assert result['governed_reuse_passed'] is True
    assert result['rollback_revoked'] is True
    assert result['trainable_parameter_count'] == 0
    assert result['promotion_gate_pass'] is True
    assert result['hosted_attestation_digest'].startswith('r269.hosted-promotion-attestation.')
    assert result['authority_envelope_digest'].startswith('r269.authority-bound-promotion.')
