from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from nolane.organization.authority import AuthorityGraph
from nolane.organization.identity import AgentRegistry


def _stale_override_state():
    registry = AgentRegistry(build_first_generation_blueprint())
    graph = AuthorityGraph(registry)
    graph.claim_owner("artifact-r2171-forward", "coding.chief")
    first = graph.record_block(
        "artifact-r2171-forward",
        "verification.chief",
        reason="first independent block",
    )
    stale = graph.central_override(
        artifact_id="artifact-r2171-forward",
        reason="evidence-backed intervention before later block",
        evidence_ids=("EV-R2171-FORWARD-A",),
    )
    second = graph.record_block(
        "artifact-r2171-forward",
        "verification.chief",
        reason="later independent block",
    )
    return registry, graph, first, stale, second


def test_override_pins_global_block_counter_at_issue() -> None:
    _, graph, first, stale, _ = _stale_override_state()

    assert stale.block_frontier_ids == (first.block_id,)
    assert stale.block_counter_at_issue == 1
    assert graph.to_state()["overrides"][stale.override_id][
        "block_counter_at_issue"
    ] == 1


def test_restore_rejects_override_missing_issue_counter() -> None:
    registry, graph, _, stale, _ = _stale_override_state()
    state = deepcopy(graph.to_state())
    state["overrides"][stale.override_id].pop("block_counter_at_issue", None)

    with pytest.raises(ValueError, match="counter"):
        AuthorityGraph.from_state(registry, state)


def test_restore_rejects_forward_bound_stale_override_frontier() -> None:
    registry, graph, first, stale, second = _stale_override_state()

    assert not graph.can_write(
        "nolane.central",
        "artifact-r2171-forward",
        override_id=stale.override_id,
    )

    forged = deepcopy(graph.to_state())
    forged["overrides"][stale.override_id]["block_frontier_ids"] = [
        first.block_id,
        second.block_id,
    ]

    with pytest.raises(ValueError, match="frontier"):
        AuthorityGraph.from_state(registry, forged)


def test_restore_rejects_coordinated_forward_binding_of_frontier_and_issue_counter() -> None:
    registry, graph, first, stale, second = _stale_override_state()
    honest = graph.to_state()

    restored = AuthorityGraph.from_state(registry, deepcopy(honest))
    assert restored.to_state() == honest
    assert not restored.can_write(
        "nolane.central",
        "artifact-r2171-forward",
        override_id=stale.override_id,
    )

    forged = deepcopy(honest)
    forged["overrides"][stale.override_id]["block_counter_at_issue"] = 2
    forged["overrides"][stale.override_id]["block_frontier_ids"] = [
        first.block_id,
        second.block_id,
    ]

    with pytest.raises(ValueError, match="causal|order|temporal"):
        AuthorityGraph.from_state(registry, forged)
