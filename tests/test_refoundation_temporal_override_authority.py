from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from nolane.organization.authority import AuthorityGraph
from nolane.organization.identity import AgentRegistry


def _registry() -> AgentRegistry:
    return AgentRegistry(build_first_generation_blueprint())


def _graph() -> tuple[AgentRegistry, AuthorityGraph]:
    registry = _registry()
    graph = AuthorityGraph(registry)
    graph.claim_owner("artifact-r2171", "coding.chief")
    return registry, graph


def _blocked_graph() -> tuple[AgentRegistry, AuthorityGraph, str]:
    registry, graph = _graph()
    first = graph.record_block(
        "artifact-r2171",
        "verification.chief",
        reason="first independent temporal-authority block",
    )
    return registry, graph, first.block_id


def test_override_captures_exact_block_frontier_and_is_live_at_issue_time() -> None:
    _, graph, first_id = _blocked_graph()
    receipt = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )

    assert receipt.block_frontier_ids == (first_id,)
    assert graph.can_write(
        "nolane.central", "artifact-r2171", override_id=receipt.override_id
    )


def test_new_same_artifact_block_makes_old_override_stale() -> None:
    _, graph, _ = _blocked_graph()
    receipt = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )

    graph.record_block(
        "artifact-r2171",
        "verification.chief",
        reason="later independent temporal-authority block",
    )

    assert not graph.can_write(
        "nolane.central", "artifact-r2171", override_id=receipt.override_id
    )
    with pytest.raises(PermissionError, match="blocked"):
        graph.require_write(
            "nolane.central", "artifact-r2171", override_id=receipt.override_id
        )


def test_fresh_override_after_new_block_captures_new_frontier() -> None:
    _, graph, first_id = _blocked_graph()
    stale = graph.central_override(
        artifact_id="artifact-r2171",
        reason="first evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )
    second = graph.record_block(
        "artifact-r2171",
        "verification.chief",
        reason="later independent temporal-authority block",
    )

    assert not graph.can_write(
        "nolane.central", "artifact-r2171", override_id=stale.override_id
    )

    fresh = graph.central_override(
        artifact_id="artifact-r2171",
        reason="fresh evidence after later block",
        evidence_ids=("EV-R2171-B",),
    )
    assert fresh.block_frontier_ids == (first_id, second.block_id)
    assert graph.can_write(
        "nolane.central", "artifact-r2171", override_id=fresh.override_id
    )


def test_unrelated_artifact_block_does_not_stale_override() -> None:
    _, graph, first_id = _blocked_graph()
    receipt = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )
    graph.record_block(
        "artifact-other",
        "verification.chief",
        reason="unrelated independent block",
    )

    assert receipt.block_frontier_ids == (first_id,)
    assert graph.can_write(
        "nolane.central", "artifact-r2171", override_id=receipt.override_id
    )


def test_serialized_override_exposes_exact_ordered_block_frontier() -> None:
    _, graph, first_id = _blocked_graph()
    second = graph.record_block(
        "artifact-r2171",
        "verification.chief",
        reason="second independent temporal-authority block",
    )
    receipt = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )

    state = graph.to_state()
    row = state["overrides"][receipt.override_id]
    assert row["block_frontier_ids"] == [first_id, second.block_id]


def test_temporal_frontier_round_trip_is_exact() -> None:
    registry, graph, first_id = _blocked_graph()
    receipt = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )

    restored = AuthorityGraph.from_state(registry, deepcopy(graph.to_state()))
    assert restored.to_state() == graph.to_state()
    restored_row = restored.to_state()["overrides"][receipt.override_id]
    assert restored_row["block_frontier_ids"] == [first_id]


def test_restore_rejects_override_missing_temporal_frontier() -> None:
    registry, graph, _ = _blocked_graph()
    receipt = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )
    state = deepcopy(graph.to_state())
    row = state["overrides"][receipt.override_id]
    row.pop("block_frontier_ids", None)

    with pytest.raises(ValueError, match="frontier"):
        AuthorityGraph.from_state(registry, state)


def test_restore_rejects_unknown_temporal_frontier_block() -> None:
    registry, graph, _ = _blocked_graph()
    receipt = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )
    state = deepcopy(graph.to_state())
    state["overrides"][receipt.override_id]["block_frontier_ids"] = [
        "block-99999999"
    ]

    with pytest.raises(ValueError, match="frontier"):
        AuthorityGraph.from_state(registry, state)


def test_restore_rejects_temporal_frontier_from_other_artifact() -> None:
    registry, graph, _ = _blocked_graph()
    other = graph.record_block(
        "artifact-other",
        "verification.chief",
        reason="other artifact block",
    )
    receipt = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )
    state = deepcopy(graph.to_state())
    state["overrides"][receipt.override_id]["block_frontier_ids"] = [other.block_id]

    with pytest.raises(ValueError, match="frontier"):
        AuthorityGraph.from_state(registry, state)


def test_restore_rejects_duplicate_temporal_frontier_ids() -> None:
    registry, graph, first_id = _blocked_graph()
    receipt = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )
    state = deepcopy(graph.to_state())
    state["overrides"][receipt.override_id]["block_frontier_ids"] = [
        first_id,
        first_id,
    ]

    with pytest.raises(ValueError, match="frontier"):
        AuthorityGraph.from_state(registry, state)


def test_restore_rejects_reordered_temporal_frontier() -> None:
    registry, graph, first_id = _blocked_graph()
    second = graph.record_block(
        "artifact-r2171",
        "verification.chief",
        reason="second independent temporal-authority block",
    )
    receipt = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )
    state = deepcopy(graph.to_state())
    state["overrides"][receipt.override_id]["block_frontier_ids"] = [
        second.block_id,
        first_id,
    ]

    with pytest.raises(ValueError, match="frontier"):
        AuthorityGraph.from_state(registry, state)


def test_restore_preserves_historical_stale_receipt_but_does_not_reauthorize_it() -> None:
    registry, graph, first_id = _blocked_graph()
    stale = graph.central_override(
        artifact_id="artifact-r2171",
        reason="evidence-backed temporal intervention",
        evidence_ids=("EV-R2171-A",),
    )
    graph.record_block(
        "artifact-r2171",
        "verification.chief",
        reason="later independent temporal-authority block",
    )

    state = deepcopy(graph.to_state())
    state["overrides"][stale.override_id]["block_frontier_ids"] = [first_id]
    restored = AuthorityGraph.from_state(registry, state)

    assert restored.to_state()["overrides"][stale.override_id][
        "block_frontier_ids"
    ] == [first_id]
    assert not restored.can_write(
        "nolane.central", "artifact-r2171", override_id=stale.override_id
    )
