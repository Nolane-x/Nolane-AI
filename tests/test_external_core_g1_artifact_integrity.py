from __future__ import annotations

import copy
import math

import pytest

from nolane.external_core.artifacts import ArtifactCurrentness, ArtifactStore


def _put_v2(
    store: ArtifactStore,
    *,
    content: str,
    dependencies: tuple[str, ...] = (),
    created_epoch: int = 3,
    max_age: int | None = 5,
):
    return store.put_v2(
        kind="research-synthesis",
        schema_version="2",
        producer_component_id="external.research",
        producer_agent_id="research.chief",
        content=content,
        source_state_digest="s" * 64,
        evidence_refs=("evidence-1",),
        evidence_digests=("e" * 64,),
        dependency_artifact_ids=dependencies,
        predecessor_artifact_ids=(),
        contract_id="g.research-synthesis",
        contract_version="2",
        created_epoch=created_epoch,
        currentness_max_age_epochs=max_age,
        metadata={"mode": "current_external"},
    )


def test_v2_artifact_identity_is_content_addressed_and_restore_recomputed():
    store = ArtifactStore()
    row = _put_v2(store, content="payload")

    assert row.artifact_id.startswith("artifact-v2-")
    assert row.content_digest
    assert row.digest
    assert ArtifactStore.from_state(store.to_state()).get_v2(row.artifact_id) == row

    forged = copy.deepcopy(store.to_state())
    forged["artifact_envelopes"][0]["artifact_id"] = "artifact-v2-forged"
    with pytest.raises(ValueError, match="artifact identity"):
        ArtifactStore.from_state(forged)


def test_v2_artifact_semantic_id_cannot_be_rebound():
    store = ArtifactStore()
    first = _put_v2(store, content="same")
    second = _put_v2(store, content="same")
    assert second == first

    state = copy.deepcopy(store.to_state())
    state["artifact_envelopes"].append(copy.deepcopy(state["artifact_envelopes"][0]))
    state["artifact_envelopes"][1]["content"] = "different"
    with pytest.raises(ValueError):
        ArtifactStore.from_state(state)


def test_dependency_must_exist_and_cycle_is_rejected():
    store = ArtifactStore()
    root = _put_v2(store, content="root")

    with pytest.raises(KeyError, match="dependency"):
        _put_v2(store, content="orphan", dependencies=("artifact-v2-missing",))

    with pytest.raises(ValueError, match="cycle"):
        store.provenance.bind_dependency(root.artifact_id, root.artifact_id)


def test_revoked_ancestor_invalidates_descendants_without_deleting_history():
    store = ArtifactStore()
    root = _put_v2(store, content="root")
    child = _put_v2(store, content="child", dependencies=(root.artifact_id,))
    grandchild = _put_v2(store, content="grandchild", dependencies=(child.artifact_id,))

    receipt = store.revoke_artifact(
        root.artifact_id,
        actor_component_id="external.artifacts",
        reason="source-retracted",
        evidence_refs=("revocation-evidence",),
    )

    assert receipt.artifact_id == root.artifact_id
    assert store.currentness(root.artifact_id, current_epoch=3).status is ArtifactCurrentness.REVOKED
    assert store.currentness(child.artifact_id, current_epoch=3).status is ArtifactCurrentness.DEPENDENCY_INVALID
    assert store.currentness(grandchild.artifact_id, current_epoch=3).status is ArtifactCurrentness.DEPENDENCY_INVALID
    assert store.get_v2(root.artifact_id) == root
    assert store.get_v2(child.artifact_id) == child
    assert store.get_v2(grandchild.artifact_id) == grandchild


def test_currentness_is_categorical_and_epoch_bounded():
    store = ArtifactStore()
    row = _put_v2(store, content="fresh", created_epoch=3, max_age=2)

    assert store.currentness(row.artifact_id, current_epoch=5).status is ArtifactCurrentness.CURRENT
    assert store.currentness(row.artifact_id, current_epoch=6).status is ArtifactCurrentness.STALE


def test_legacy_artifact_state_restores_without_silent_v2_upgrade():
    legacy = ArtifactStore()
    row = legacy.put(kind="legacy", producer_agent_id="research.chief", content="payload")

    restored = ArtifactStore.from_state(legacy.to_state())
    assert restored.get(row.artifact_id) == row
    assert restored.v2_records() == ()


def test_bool_epoch_non_finite_metadata_and_evidence_binding_mismatch_fail_closed():
    store = ArtifactStore()

    with pytest.raises(TypeError, match="created_epoch"):
        store.put_v2(
            kind="x",
            schema_version="2",
            producer_component_id="external.artifacts",
            producer_agent_id="infra.chief",
            content="x",
            source_state_digest="s",
            evidence_refs=("e",),
            evidence_digests=("d",),
            dependency_artifact_ids=(),
            predecessor_artifact_ids=(),
            contract_id="x",
            contract_version="2",
            created_epoch=True,
            currentness_max_age_epochs=None,
            metadata={},
        )

    with pytest.raises(ValueError, match="finite"):
        store.put_v2(
            kind="x",
            schema_version="2",
            producer_component_id="external.artifacts",
            producer_agent_id="infra.chief",
            content="x",
            source_state_digest="s",
            evidence_refs=("e",),
            evidence_digests=("d",),
            dependency_artifact_ids=(),
            predecessor_artifact_ids=(),
            contract_id="x",
            contract_version="2",
            created_epoch=1,
            currentness_max_age_epochs=None,
            metadata={"score": math.nan},
        )

    with pytest.raises(ValueError, match="evidence"):
        store.put_v2(
            kind="x",
            schema_version="2",
            producer_component_id="external.artifacts",
            producer_agent_id="infra.chief",
            content="x",
            source_state_digest="s",
            evidence_refs=("e1", "e2"),
            evidence_digests=("d1",),
            dependency_artifact_ids=(),
            predecessor_artifact_ids=(),
            contract_id="x",
            contract_version="2",
            created_epoch=1,
            currentness_max_age_epochs=None,
            metadata={},
        )
