from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def _optional_text(path: str) -> str | None:
    target = ROOT / path
    return target.read_text(encoding='utf-8') if target.is_file() else None


def _lock() -> dict[str, object] | None:
    path = ROOT / 'R2_69_PRE_HOSTED_LOCK.json'
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding='utf-8'))
    assert isinstance(value, dict)
    return value


def test_freeze_canonical_bundle_and_postmerge_all_bind_promotion_authority():
    freeze = _optional_text('.github/workflows/r269-freeze-evidence.yml')
    lock = _lock()
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
        if freeze is not None:
            assert path in freeze, ('freeze missing promotion authority path', path)
        else:
            assert lock is not None and path in lock['frozen_git_blobs'], (
                'post-freeze lock missing promotion authority blob', path
            )
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
        if freeze is not None:
            assert field in freeze, ('freeze missing promotion lock field', field)
        else:
            assert lock is not None and field in lock, ('post-freeze lock missing promotion field', field)
        assert field in canonical or field in builder, ('release verifier missing promotion lock field', field)

    for workflow, label in ((canonical, 'canonical'), (bundle, 'bundle'), (postmerge, 'postmerge')):
        assert 'run_promotion_authority_benchmark' in workflow, (label, 'promotion replay missing')
        assert "promotion['semantic_result_digest']" in workflow, (label, 'semantic digest replay missing')
        assert "lock['promotion_semantic_digest']" in workflow, (label, 'lock semantic binding missing')
        assert "lock['promotion_authority_root_digest']" in workflow, (label, 'authority root binding missing')
        assert "promotion['promotion_gate_pass'] is True" in workflow, (label, 'promotion gate missing')


def test_world_bounded_adjudication_is_content_addressed_across_release_chain():
    freeze = _optional_text('.github/workflows/r269-freeze-evidence.yml')
    lock = _lock()
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
        if freeze is not None:
            assert path in freeze, ('freeze missing World authority path', path)
        else:
            assert lock is not None and path in lock['frozen_git_blobs'], (
                'post-freeze lock missing World authority blob', path
            )
        assert path in builder, ('bundle missing World authority path', path)

    for field in (
        'content_addressed_world_adjudication_required',
        'world_bounded_receipt_digest',
        'world_state_sha256',
        'world_gate_sha256',
    ):
        if freeze is not None:
            assert field in freeze, ('freeze missing World lock field', field)
        else:
            assert lock is not None and field in lock, ('post-freeze lock missing World field', field)
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


def test_freeze_lifecycle_requires_mutating_verifiers_retired_before_and_after_lock():
    freeze = _optional_text('.github/workflows/r269-freeze-evidence.yml')
    lock = _lock()
    verifier_workflows = (
        'r269-red-green.yml',
        'r269-external-numpy-transfer.yml',
        'r269-promotion-authority.yml',
        'r269-multi-prior-hardening.yml',
    )
    temporary_workflows = (
        'r269-lazy-scratch-hotfix.yml',
        'r269-fast-validation.yml',
    )

    if freeze is not None:
        for workflow in verifier_workflows:
            assert f"! grep -q 'contents: write' .github/workflows/{workflow}" in freeze
        for temporary in temporary_workflows:
            assert f'test ! -f .github/workflows/{temporary}' in freeze
        assert 'git rm R2_69_FREEZE_REQUEST .github/workflows/r269-freeze-evidence.yml' in freeze
        return

    assert lock is not None and lock.get('writers_retired') is True
    assert not (ROOT / '.github/workflows/r269-freeze-evidence.yml').exists()
    assert not (ROOT / 'R2_69_FREEZE_REQUEST').exists()
    for workflow in verifier_workflows:
        assert 'contents: write' not in _text(f'.github/workflows/{workflow}'), workflow
    for temporary in temporary_workflows:
        assert not (ROOT / '.github/workflows' / temporary).exists(), temporary


def test_postmerge_requires_exact_main_and_frozen_authority_lineage():
    postmerge = _text('.github/workflows/r269-post-merge-release-bundle.yml')
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in postmerge
    assert "lock['source_head_sha']" in postmerge
    assert "lock['integration_base_sha']" in postmerge
    assert "lock['host_attested_promotion_authority_required'] is True" in postmerge
    assert "lock['promotion_authority_source_frozen'] is True" in postmerge
    assert "lock['content_addressed_world_adjudication_required'] is True" in postmerge
    assert "lock['exact_rollback_registry_required'] is True" in postmerge


def test_retired_evidence_workflows_are_verification_only_and_cannot_rewrite_receipts():
    workflows = {
        '.github/workflows/r269-red-green.yml': 'R2_69_SEQUENTIAL_INTEGRATION_EVIDENCE.json',
        '.github/workflows/r269-external-numpy-transfer.yml': 'R2_69_EXTERNAL_TRANSFER.json',
        '.github/workflows/r269-promotion-authority.yml': 'R2_69_PROMOTION_AUTHORITY.json',
    }
    for path, receipt in workflows.items():
        workflow = _text(path)
        assert 'contents: write' not in workflow, (path, 'retired verifier regained write authority')
        assert 'git push origin' not in workflow, (path, 'retired verifier can still push')
        assert f'git add {receipt}' not in workflow, (path, 'retired verifier can still stage receipt rewrites')
        assert 'retired' in workflow.lower(), (path, 'retired verifier must declare its retired state')
