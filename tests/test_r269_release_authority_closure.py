from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_freeze_canonical_bundle_and_postmerge_all_bind_promotion_authority():
    freeze = _text('.github/workflows/r269-freeze-evidence.yml')
    canonical = _text('.github/workflows/r269-canonical-gate.yml')
    bundle = _text('.github/workflows/r269-release-bundle.yml')
    postmerge = _text('.github/workflows/r269-post-merge-release-bundle.yml')
    builder = _text('scripts/r269_build_complete_bundle.py')

    required_paths = (
        'R2_69_PROMOTION_AUTHORITY.json',
        'cogcoder/r269_promotion_authority.py',
        'benchmarks/kfigg/r269_promotion_authority.py',
        '.github/workflows/r269-promotion-authority.yml',
    )
    for path in required_paths:
        assert path in freeze, ('freeze missing promotion authority path', path)
        assert path in builder, ('bundle builder missing promotion authority path', path)

    lock_fields = (
        'promotion_semantic_digest',
        'promotion_authority_root_digest',
        'promotion_hosted_attestation_digest',
        'promotion_authority_envelope_digest',
        'promotion_verifier_workflow_blob',
        'host_attested_promotion_authority_required',
        'promotion_authority_source_frozen',
        'exact_rollback_registry_required',
    )
    for field in lock_fields:
        assert field in freeze, ('freeze missing promotion lock field', field)
        assert field in canonical or field in builder, ('release verifier missing promotion lock field', field)

    for workflow, label in ((canonical, 'canonical'), (bundle, 'bundle'), (postmerge, 'postmerge')):
        assert 'run_promotion_authority_benchmark' in workflow, (label, 'promotion replay missing')
        assert "promotion['semantic_result_digest']" in workflow, (label, 'semantic digest replay missing')
        assert "lock['promotion_semantic_digest']" in workflow, (label, 'lock semantic binding missing')
        assert "lock['promotion_authority_root_digest']" in workflow, (label, 'authority root binding missing')
        assert "promotion['promotion_gate_pass'] is True" in workflow, (label, 'promotion gate missing')


def test_complete_bundle_refuses_pre_promotion_lock_and_receipt_drift():
    builder = _text('scripts/r269_build_complete_bundle.py')
    assert "lock.get('schema_version', 0) < 3" in builder
    assert "lock.get('promotion_gate_pass') is not True" in builder
    assert "promotion.get('semantic_result_digest') != lock.get('promotion_semantic_digest')" in builder
    assert "promotion.get('authority_root_digest') != lock.get('promotion_authority_root_digest')" in builder
    assert "promotion.get('hosted_attestation_digest') != lock.get('promotion_hosted_attestation_digest')" in builder
    assert "promotion.get('authority_envelope_digest') != lock.get('promotion_authority_envelope_digest')" in builder
    assert "promotion.get('verifier_workflow_blob') != lock.get('promotion_verifier_workflow_blob')" in builder


def test_freeze_requires_all_mutating_r269_verifiers_retired_before_lock():
    freeze = _text('.github/workflows/r269-freeze-evidence.yml')
    for workflow in (
        'r269-red-green.yml',
        'r269-external-numpy-transfer.yml',
        'r269-promotion-authority.yml',
        'r269-multi-prior-hardening.yml',
    ):
        assert f"! grep -q 'contents: write' .github/workflows/{workflow}" in freeze
    assert 'git rm R2_69_FREEZE_REQUEST .github/workflows/r269-freeze-evidence.yml' in freeze


def test_postmerge_requires_exact_main_and_frozen_promotion_lineage():
    postmerge = _text('.github/workflows/r269-post-merge-release-bundle.yml')
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in postmerge
    assert "lock['source_head_sha']" in postmerge
    assert "lock['integration_base_sha']" in postmerge
    assert "lock['host_attested_promotion_authority_required'] is True" in postmerge
    assert "lock['promotion_authority_source_frozen'] is True" in postmerge
    assert "lock['exact_rollback_registry_required'] is True" in postmerge


def test_evidence_writers_do_not_mistake_untracked_receipts_for_already_materialized():
    writers = {
        '.github/workflows/r269-red-green.yml': 'R2_69_SEQUENTIAL_INTEGRATION_EVIDENCE.json',
        '.github/workflows/r269-external-numpy-transfer.yml': 'R2_69_EXTERNAL_TRANSFER.json',
        '.github/workflows/r269-promotion-authority.yml': 'R2_69_PROMOTION_AUTHORITY.json',
    }
    for path, receipt in writers.items():
        workflow = _text(path)
        unsafe = f'git diff --quiet -- {receipt}'
        assert unsafe not in workflow, (path, 'git diff ignores untracked receipt files')
        assert f'git status --porcelain -- {receipt}' in workflow, (
            path,
            'writer must inspect tracked and untracked receipt materialization',
        )
