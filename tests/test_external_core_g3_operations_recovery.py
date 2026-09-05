from __future__ import annotations

import copy

import pytest

from nolane.external_core.artifacts import ArtifactCurrentness, ArtifactStore
from nolane.external_core.assurance import AssuranceDisposition
from nolane.external_core.operations_journal import OperationsJournal
from nolane.external_core.operations_recovery import (
    CurrentReleaseDisposition,
    OperationalLeaseRegistry,
    OperationsSnapshot,
    RecoveryMode,
    ReleaseCurrentnessBasis,
    assess_current_release_readiness,
    recover_operations,
)


def test_operations_journal_is_hash_chained_and_restore_rejects_tamper():
    journal = OperationsJournal()
    first = journal.append(
        transition_id="build:b1:registered",
        kind="build_registered",
        subject_id="b1",
        payload={"artifact_digest": "a" * 64},
    )
    second = journal.append(
        transition_id="release:r1:registered",
        kind="release_registered",
        subject_id="r1",
        payload={"build_id": "b1"},
    )
    assert second.previous_digest == first.digest
    assert OperationsJournal.from_state(journal.to_state()).head_digest == second.digest

    forged = copy.deepcopy(journal.to_state())
    forged["events"][1]["previous_digest"] = "forged"
    with pytest.raises(ValueError, match="journal"):
        OperationsJournal.from_state(forged)


def test_transition_id_cannot_be_rebound_to_different_semantics():
    journal = OperationsJournal()
    journal.append(
        transition_id="build:b1:registered",
        kind="build_registered",
        subject_id="b1",
        payload={"artifact_digest": "a"},
    )
    with pytest.raises(ValueError, match="rebound"):
        journal.append(
            transition_id="build:b1:registered",
            kind="build_registered",
            subject_id="b1",
            payload={"artifact_digest": "different"},
        )


def test_recovery_distinguishes_exact_fast_forward_and_divergence():
    journal = OperationsJournal()
    first = journal.append(
        transition_id="build:b1:registered",
        kind="build_registered",
        subject_id="b1",
        payload={"artifact_digest": "a"},
    )
    snapshot = OperationsSnapshot.create(
        component_versions={"external.operations": "0.1.0"},
        journal_head_digest=first.digest,
        journal_length=1,
        artifact_graph_digest="artifact-graph-1",
        authority_graph_digest="authority-graph-1",
        readiness_state_digest="readiness-1",
        registry_digest="registry-1",
        active_operation_ids=("build:b1",),
    )
    exact = recover_operations(
        snapshot=snapshot,
        journal=journal,
        current_artifact_graph_digest="artifact-graph-1",
        current_authority_graph_digest="authority-graph-1",
        current_readiness_state_digest="readiness-1",
        current_registry_digest="registry-1",
    )
    assert exact.mode is RecoveryMode.EXACT
    assert exact.authoritative

    journal.append(
        transition_id="release:r1:registered",
        kind="release_registered",
        subject_id="r1",
        payload={"build_id": "b1"},
    )
    fast_forward = recover_operations(
        snapshot=snapshot,
        journal=journal,
        current_artifact_graph_digest="artifact-graph-1",
        current_authority_graph_digest="authority-graph-1",
        current_readiness_state_digest="readiness-1",
        current_registry_digest="registry-1",
    )
    assert fast_forward.mode is RecoveryMode.FAST_FORWARD
    assert fast_forward.authoritative

    foreign = OperationsSnapshot.create(
        component_versions={"external.operations": "0.1.0"},
        journal_head_digest="foreign-head",
        journal_length=1,
        artifact_graph_digest="artifact-graph-1",
        authority_graph_digest="authority-graph-1",
        readiness_state_digest="readiness-1",
        registry_digest="registry-1",
        active_operation_ids=("build:b1",),
    )
    quarantined = recover_operations(
        snapshot=foreign,
        journal=journal,
        current_artifact_graph_digest="artifact-graph-1",
        current_authority_graph_digest="authority-graph-1",
        current_readiness_state_digest="readiness-1",
        current_registry_digest="registry-1",
    )
    assert quarantined.mode is RecoveryMode.QUARANTINED
    assert not quarantined.authoritative


def test_recovery_quarantines_registry_or_authority_graph_drift():
    journal = OperationsJournal()
    event = journal.append(
        transition_id="build:b1:registered",
        kind="build_registered",
        subject_id="b1",
        payload={"artifact_digest": "a"},
    )
    snapshot = OperationsSnapshot.create(
        component_versions={"external.operations": "0.1.0"},
        journal_head_digest=event.digest,
        journal_length=1,
        artifact_graph_digest="artifact-graph-1",
        authority_graph_digest="authority-graph-1",
        readiness_state_digest="readiness-1",
        registry_digest="registry-1",
        active_operation_ids=(),
    )
    result = recover_operations(
        snapshot=snapshot,
        journal=journal,
        current_artifact_graph_digest="artifact-graph-1",
        current_authority_graph_digest="authority-graph-2",
        current_readiness_state_digest="readiness-1",
        current_registry_digest="registry-2",
    )
    assert result.mode is RecoveryMode.QUARANTINED
    assert "authority_graph_digest_drift" in result.reasons
    assert "registry_digest_drift" in result.reasons


def test_operational_lease_fence_is_monotonic_and_bool_safe():
    leases = OperationalLeaseRegistry()
    first = leases.acquire(
        resource_id="release:r1",
        owner_id="infra.chief",
        issued_epoch=10,
        expires_epoch=20,
    )
    leases.release(
        resource_id="release:r1",
        owner_id="infra.chief",
        fence_epoch=first.fence_epoch,
        terminal_ref="release-cancelled",
    )
    second = leases.acquire(
        resource_id="release:r1",
        owner_id="infra.specialist-1",
        issued_epoch=21,
        expires_epoch=30,
    )
    assert second.fence_epoch == first.fence_epoch + 1

    with pytest.raises(PermissionError, match="stale fence"):
        leases.release(
            resource_id="release:r1",
            owner_id="infra.chief",
            fence_epoch=first.fence_epoch,
            terminal_ref="forged-release",
        )
    with pytest.raises(TypeError, match="issued_epoch"):
        leases.acquire(
            resource_id="release:r2",
            owner_id="infra.chief",
            issued_epoch=True,
            expires_epoch=40,
        )


def _v2_artifact(store: ArtifactStore, content: str):
    return store.put_v2(
        kind="release-package",
        schema_version="2",
        producer_component_id="external.infrastructure_operations",
        producer_agent_id="infrastructure.chief",
        content=content,
        source_state_digest="s" * 64,
        evidence_refs=("e1",),
        evidence_digests=("d" * 64,),
        dependency_artifact_ids=(),
        predecessor_artifact_ids=(),
        contract_id="g.release-package",
        contract_version="2",
        created_epoch=1,
        currentness_max_age_epochs=10,
        metadata={},
    )


def test_current_release_readiness_rechecks_artifact_and_assurance_currentness():
    store = ArtifactStore()
    package = _v2_artifact(store, "package")
    rollback = _v2_artifact(store, "rollback")
    basis = ReleaseCurrentnessBasis(
        release_id="release-1",
        package_artifact_id=package.artifact_id,
        rollback_artifact_id=rollback.artifact_id,
        build_reproducible=True,
        observability_current=True,
        reliability_current=True,
        assurance_disposition=AssuranceDisposition.VERIFIED,
        source_baseline_current=True,
    )
    ready = assess_current_release_readiness(basis=basis, artifacts=store, current_epoch=2)
    assert ready.disposition is CurrentReleaseDisposition.READY
    assert store.currentness(package.artifact_id, current_epoch=2).status is ArtifactCurrentness.CURRENT

    store.revoke_artifact(
        package.artifact_id,
        actor_component_id="external.artifacts",
        reason="package-invalidated",
        evidence_refs=("e-revoke",),
    )
    blocked = assess_current_release_readiness(basis=basis, artifacts=store, current_epoch=2)
    assert blocked.disposition is CurrentReleaseDisposition.BLOCKED
    assert "package_not_current" in blocked.reasons


def test_missing_current_observation_yields_unknown_not_historical_ready():
    store = ArtifactStore()
    package = _v2_artifact(store, "package")
    rollback = _v2_artifact(store, "rollback")
    basis = ReleaseCurrentnessBasis(
        release_id="release-1",
        package_artifact_id=package.artifact_id,
        rollback_artifact_id=rollback.artifact_id,
        build_reproducible=True,
        observability_current=None,
        reliability_current=True,
        assurance_disposition=AssuranceDisposition.VERIFIED,
        source_baseline_current=True,
    )
    result = assess_current_release_readiness(basis=basis, artifacts=store, current_epoch=2)
    assert result.disposition is CurrentReleaseDisposition.UNKNOWN
    assert "observability_currentness_unknown" in result.reasons
