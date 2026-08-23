from __future__ import annotations

import inspect
from pathlib import Path

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT


ROOT = Path(__file__).resolve().parents[1]


def test_wave5_artifacts_and_verification_are_native_and_independently_versioned() -> None:
    ledger = build_component_implementation_ledger()
    expected = {
        "external.artifacts": "nolane.external_core.artifacts",
        "external.verification": "nolane.external_core.verification",
    }
    for component_id, module in expected.items():
        row = ledger[component_id]
        assert row.status is ImplementationStatus.CANONICAL_NATIVE
        assert row.canonical_module == module
        assert row.canonical_write_authority is True
        assert row.component_version == "0.0.1"
        assert str(component_version(component_id)) == "0.0.1"


def test_wave5_native_pair_is_removed_from_compatibility_facades() -> None:
    facade_ids = {row.component_id for row in build_active_facade_bindings()}
    assert {"external.artifacts", "external.verification"}.isdisjoint(facade_ids)


def test_wave5_migration_destinations_remain_exact_and_fail_closed() -> None:
    census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
    assert census.get("cogcoder/organization/artifacts.py").canonical_destination == "nolane/external_core/artifacts.py"
    assert census.get("cogcoder/organization/verification.py").canonical_destination == "nolane/external_core/verification.py"


def test_wave5_legacy_modules_bridge_to_canonical_class_authority() -> None:
    from cogcoder.organization.artifacts import ArtifactRecord as LegacyArtifactRecord
    from cogcoder.organization.artifacts import ArtifactStore as LegacyArtifactStore
    from cogcoder.organization.verification import CandidateEvaluation as LegacyCandidateEvaluation
    from cogcoder.organization.verification import PromotionReceipt as LegacyPromotionReceipt
    from cogcoder.organization.verification import RollbackReceipt as LegacyRollbackReceipt
    from cogcoder.organization.verification import VerificationAuthority as LegacyVerificationAuthority
    from nolane.external_core.artifacts import ArtifactRecord, ArtifactStore
    from nolane.external_core.verification import (
        CandidateEvaluation,
        PromotionReceipt,
        RollbackReceipt,
        VerificationAuthority,
    )

    assert LegacyArtifactRecord is ArtifactRecord
    assert LegacyArtifactStore is ArtifactStore
    assert LegacyCandidateEvaluation is CandidateEvaluation
    assert LegacyPromotionReceipt is PromotionReceipt
    assert LegacyRollbackReceipt is RollbackReceipt
    assert LegacyVerificationAuthority is VerificationAuthority

    assert ArtifactRecord.__module__ == "nolane.external_core.artifacts"
    assert ArtifactStore.__module__ == "nolane.external_core.artifacts"
    assert CandidateEvaluation.__module__ == "nolane.external_core.verification"
    assert PromotionReceipt.__module__ == "nolane.external_core.verification"
    assert RollbackReceipt.__module__ == "nolane.external_core.verification"
    assert VerificationAuthority.__module__ == "nolane.external_core.verification"


def test_wave5_native_modules_do_not_import_historical_implementation_owners() -> None:
    import nolane.external_core.artifacts as artifacts
    import nolane.external_core.verification as verification

    artifact_source = inspect.getsource(artifacts)
    verification_source = inspect.getsource(verification)
    assert "cogcoder.organization.artifacts import" not in artifact_source
    assert "cogcoder.organization.verification import" not in verification_source


def test_wave5_native_artifact_store_preserves_content_identity_and_round_trip() -> None:
    from nolane.external_core.artifacts import ArtifactStore

    store = ArtifactStore()
    first = store.put(
        kind="patch",
        producer_agent_id="coding.backend.01",
        content="diff --git a/a.py b/a.py",
        evidence_refs=("evidence-b", "evidence-a", "evidence-b"),
        metadata={"z": 2, "a": 1},
    )
    duplicate = store.put(
        kind="patch",
        producer_agent_id="coding.backend.01",
        content="diff --git a/a.py b/a.py",
        evidence_refs=("evidence-a", "evidence-b"),
        metadata={"a": 1, "z": 2},
    )

    assert duplicate is first
    assert first.artifact_id.startswith("artifact-")
    assert len(first.digest) == 64
    assert first.evidence_refs == ("evidence-a", "evidence-b")
    assert first.metadata_json == '{"a":1,"z":2}'
    assert first.metadata == {"a": 1, "z": 2}

    restored = ArtifactStore.from_state(store.to_state())
    assert restored.to_state() == store.to_state()
    assert restored.get(first.artifact_id) == first


def test_wave5_native_verification_preserves_rejection_promotion_rollback_and_events() -> None:
    from nolane.external_core.verification import CandidateEvaluation, VerificationAuthority
    from nolane.organization.events import EventLedger
    from nolane.organization.identity import AgentRegistry

    registry = AgentRegistry(build_first_generation_blueprint())
    events = EventLedger()
    authority = VerificationAuthority(registry=registry, ledger=events)
    agent_id = "coding.backend.01"
    original_version = registry.get(agent_id).neural_version

    rejected = authority.evaluate_candidate(
        CandidateEvaluation(
            agent_id=agent_id,
            candidate_version="wave5-rejected",
            physical_parameters=90_000_000,
            passed=True,
            false_accepts=1,
            regressions=0,
            evidence_ids=("evidence-reject",),
        )
    )
    assert not rejected.accepted
    assert rejected.reason == "false_accepts_detected"

    accepted = authority.evaluate_candidate(
        CandidateEvaluation(
            agent_id=agent_id,
            candidate_version="wave5-accepted",
            physical_parameters=90_000_000,
            passed=True,
            false_accepts=0,
            regressions=0,
            evidence_ids=("evidence-pass",),
        )
    )
    assert accepted.accepted
    assert accepted.reason == "accepted_bounded_candidate"

    promoted = authority.promote_candidate(accepted.receipt_id)
    assert promoted.promoted
    assert promoted.previous_version == original_version
    assert registry.get(agent_id).neural_version == "wave5-accepted"

    rollback = authority.rollback(agent_id, reason="wave5 parity rollback")
    assert rollback.from_version == "wave5-accepted"
    assert rollback.restored_version == original_version
    assert registry.get(agent_id).neural_version == original_version

    event_kinds = tuple(row.kind.value for row in events.records())
    assert event_kinds == (
        "neural_candidate_evaluated",
        "neural_candidate_evaluated",
        "neural_promoted",
        "neural_rollback",
    )

    restored = VerificationAuthority.from_state(
        registry=registry,
        ledger=events,
        state=authority.to_state(),
    )
    assert restored.to_state() == authority.to_state()


def test_wave5_native_debt_reduces_only_the_two_promoted_facades() -> None:
    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1

    assert len(non_native) == 44
    assert counts == {
        "compatibility_facade": 31,
        "frozen_asset": 1,
        "historical_only": 7,
        "legacy_internal": 5,
    }
    assert ledger["core.canonical_digest"].status is ImplementationStatus.LEGACY_INTERNAL
    assert ledger["schemas.identity"].status is ImplementationStatus.LEGACY_INTERNAL
    assert ledger["external.evidence"].status is ImplementationStatus.LEGACY_INTERNAL


def test_wave5_legacy_source_paths_remain_present_as_compatibility_bridges() -> None:
    assert (ROOT / "cogcoder" / "organization" / "artifacts.py").is_file()
    assert (ROOT / "cogcoder" / "organization" / "verification.py").is_file()
