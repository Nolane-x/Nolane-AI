from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from nolane.organization.authority import AuthorityGraph
from nolane.organization.identity import AgentRegistry


def _registry() -> AgentRegistry:
    return AgentRegistry(build_first_generation_blueprint())


def _state_with_authority_history() -> tuple[AgentRegistry, dict[str, object]]:
    registry = _registry()
    graph = AuthorityGraph(registry)
    graph.claim_owner("artifact-r217", "coding.chief")
    graph.record_block(
        "artifact-r217",
        "verification.chief",
        reason="independent R2.17 verification block",
    )
    graph.central_override(
        artifact_id="artifact-r217",
        reason="evidence-backed R2.17 intervention",
        evidence_ids=("EV-R217",),
    )
    return registry, deepcopy(graph.to_state())


def test_authority_restore_requires_exact_top_level_state_shape() -> None:
    registry, state = _state_with_authority_history()
    del state["block_counter"]

    with pytest.raises(ValueError, match="canonical serialized state"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_unknown_top_level_state_fields() -> None:
    registry, state = _state_with_authority_history()
    state["unexpected"] = "laundered"

    with pytest.raises(ValueError, match="canonical serialized state"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_unknown_owner_identity() -> None:
    registry, state = _state_with_authority_history()
    owners = state["owners"]
    assert isinstance(owners, dict)
    owners["artifact-r217"] = "ghost.owner"

    with pytest.raises(ValueError, match="owner"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_block_artifact_rebinding() -> None:
    registry, state = _state_with_authority_history()
    blocks = state["blocks"]
    assert isinstance(blocks, dict)
    rows = blocks["artifact-r217"]
    assert isinstance(rows, list)
    rows[0]["artifact_id"] = "different-artifact"

    with pytest.raises(ValueError, match="block.*artifact"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_unknown_blocker_identity() -> None:
    registry, state = _state_with_authority_history()
    blocks = state["blocks"]
    assert isinstance(blocks, dict)
    rows = blocks["artifact-r217"]
    assert isinstance(rows, list)
    rows[0]["blocker_agent_id"] = "ghost.blocker"

    with pytest.raises(ValueError, match="blocker"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_override_identity_rebinding() -> None:
    registry, state = _state_with_authority_history()
    overrides = state["overrides"]
    assert isinstance(overrides, dict)
    row = overrides.pop("override-00000001")
    overrides["override-99999999"] = row

    with pytest.raises(ValueError, match="override.*identity"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_non_central_override_actor() -> None:
    registry, state = _state_with_authority_history()
    overrides = state["overrides"]
    assert isinstance(overrides, dict)
    overrides["override-00000001"]["actor_agent_id"] = "coding.chief"

    with pytest.raises(ValueError, match="override.*actor"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_empty_override_reason() -> None:
    registry, state = _state_with_authority_history()
    overrides = state["overrides"]
    assert isinstance(overrides, dict)
    overrides["override-00000001"]["reason"] = ""

    with pytest.raises(ValueError, match="override.*reason"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_empty_override_evidence() -> None:
    registry, state = _state_with_authority_history()
    overrides = state["overrides"]
    assert isinstance(overrides, dict)
    overrides["override-00000001"]["evidence_ids"] = []

    with pytest.raises(ValueError, match="override.*evidence"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_coerced_override_block_flag() -> None:
    registry, state = _state_with_authority_history()
    overrides = state["overrides"]
    assert isinstance(overrides, dict)
    overrides["override-00000001"]["overrode_block"] = "false"

    with pytest.raises(ValueError, match="overrode_block"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_block_counter_rollback() -> None:
    registry, state = _state_with_authority_history()
    state["block_counter"] = 0

    with pytest.raises(ValueError, match="block counter"):
        AuthorityGraph.from_state(registry, state)


def test_authority_restore_rejects_override_counter_rollback() -> None:
    registry, state = _state_with_authority_history()
    state["override_counter"] = 0

    with pytest.raises(ValueError, match="override counter"):
        AuthorityGraph.from_state(registry, state)


def test_forged_restored_override_cannot_bypass_independent_block() -> None:
    registry, state = _state_with_authority_history()
    overrides = state["overrides"]
    assert isinstance(overrides, dict)
    row = overrides["override-00000001"]
    row["reason"] = ""
    row["evidence_ids"] = []

    with pytest.raises(ValueError):
        AuthorityGraph.from_state(registry, state)
