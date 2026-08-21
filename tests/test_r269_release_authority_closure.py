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


def test_world_bounded_adjudication_is_content_addressed_across_release_chain():
    freeze = _text('.github/workflows/r269-freeze-evidence.yml')
    canonical = _text('.github/workflows/r269-canonical-gate.yml')
    bundle = _text('.github/workflows/r269-release-bundle.yml')
    postmerge = _text('.github/workflows/r269-post-merge-release-bundle.yml')
    builder = _text('scripts/r269_build_complete_bundle.py')
    verifier = _text('scripts/r269_world_adjudication.py')

    required_paths = (
        'R2_69_WORLD_BOUNDED_ADJUDICATION.json',
        'R2_69_WORLD_STATE_SNAPSHOT.json',
        'R2_69_WORLD_GATE_SNAPSHOT.json',
        'scripts/r269_world_adjudication.py',
    )
    for path in required_paths:
        assert path in freeze, ('freeze missing World authority path', path)
        assert path in builder, ('bundle missing World authority path', path)

    for field in (
        'content_addressed_world_adjudication_required',
        'world_bounded_receipt_digest',
        'world_state_sha256',
        'world_gate_sha256',
    ):
        assert field in freeze, ('freeze missing World lock field', field)
        assert field in canonical or field in builder, ('release verifier missing World lock field', field)

    for workflow, label in ((canonical, 'canonical'), (bundle, 'bundle'), (postmerge, 'postmerge')):
        assert 'verify_world_receipt' in workflow, (label, 'World receipt replay missing')
        assert "world['full_w5_gate_pass'] is False" in workflow or label == 'postmerge', (
            label, 'bounded release must not become a W5 convergence claim'
        )
        assert "lock['world_bounded_receipt_digest']" in workflow, (label, 'World receipt lock binding missing')

    assert "gate.get('pass_gate') is not False" in verifier
    assert "release-scoped critical World unknowns remain unresolved" in verifier
    assert "promotion evidence does not contain genuine champion/challenger advantage" in verifier
    assert "final_bounded_release': 'ACCEPT'" in verifier
    assert "'w5_convergence_claimed': False" in verifier


def test_complete_bundle_refuses_pre_world_lock_and_receipt_drift():
    builder = _text('scripts/r269_build_complete_bundle.py')
    assert "lock.get('schema_version', 0) < 4" in builder
    assert "lock.get('promotion_gate_pass') is not True" in builder
    assert "promotion.get('semantic_result_digest') != lock.get('promotion_semantic_digest')" in builder
    assert "promotion.get('authority_root_digest') != lock.get('promotion_authority_root_digest')" in builder
    assert "promotion.get('hosted_attestation_digest') != lock.get('promotion_hosted_attestation_digest')" in builder
    assert "promotion.get('authority_envelope_digest') != lock.get('promotion_authority_envelope_digest')" in builder
    assert "promotion.get('verifier_workflow_blob') != lock.get('promotion_verifier_workflow_blob')" in builder
    assert "world.get('receipt_digest') != lock.get('world_bounded_receipt_digest')" in builder
    assert "world.get('world_state_sha256') != lock.get('world_state_sha256')" in builder
    assert "world.get('world_gate_sha256') != lock.get('world_gate_sha256')" in builder


def test_freeze_requires_all_mutating_r269_verifiers_retired_before_lock():
    freeze = _text('.github/workflows/r269-freeze-evidence.yml')
    for workflow in (
        'r269-red-green.yml',
        'r269-external-numpy-transfer.yml',
        'r269-promotion-authority.yml',
        'r269-multi-prior-hardening.yml',
    ):
        assert f"! grep -q 'contents: write' .github/workflows/{workflow}" in freeze
    for temporary in (
        'r269-lazy-scratch-hotfix.yml',
        'r269-fast-validation.yml',
    ):
        assert f'test ! -f .github/workflows/{temporary}' in freeze
    assert 'git rm R2_69_FREEZE_REQUEST .github/workflows/r269-freeze-evidence.yml' in freeze


def test_postmerge_requires_exact_main_and_frozen_authority_lineage():
    postmerge = _text('.github/workflows/r269-post-merge-release-bundle.yml')
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in postmerge
    assert "lock['source_head_sha']" in postmerge
    assert "lock['integration_base_sha']" in postmerge
    assert "lock['host_attested_promotion_authority_required'] is True" in postmerge
    assert "lock['promotion_authority_source_frozen'] is True" in postmerge
    assert "lock['content_addressed_world_adjudication_required'] is True" in postmerge
    assert "lock['exact_rollback_registry_required'] is True" in postmerge


def test_active_evidence_writers_do_not_mistake_untracked_receipts_for_already_materialized():
    writers = {
        '.github/workflows/r269-red-green.yml': 'R2_69_SEQUENTIAL_INTEGRATION_EVIDENCE.json',
        '.github/workflows/r269-external-numpy-transfer.yml': 'R2_69_EXTERNAL_TRANSFER.json',
    }
    for path, receipt in writers.items():
        workflow = _text(path)
        unsafe = f'git diff --quiet -- {receipt}'
        assert unsafe not in workflow, (path, 'git diff ignores untracked receipt files')
        assert f'git status --porcelain -- {receipt}' in workflow, (
            path,
            'active writer must inspect tracked and untracked receipt materialization',
        )


def test_retired_promotion_workflow_is_verification_only_and_cannot_rewrite_receipt():
    workflow = _text('.github/workflows/r269-promotion-authority.yml')
    assert 'contents: write' not in workflow
    assert 'git push origin' not in workflow
    assert "git add R2_69_PROMOTION_AUTHORITY.json" not in workflow
    assert 'Writer retired' in workflow
