from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.planning import PlanNode


def _state() -> dict[str, object]:
    runtime = OrganizationRuntime.first_generation()
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="first lineage witness",
        evidence_refs=("ev-lineage-1",),
        upsert_nodes=(PlanNode("plan-a", "Plan A"),),
    )
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="second lineage witness",
        evidence_refs=("ev-lineage-2",),
        upsert_nodes=(PlanNode("plan-b", "Plan B"),),
    )
    state = runtime.to_state()
    assert OrganizationRuntime.from_state(deepcopy(state)).planning.graph.version == 2
    return state


def test_restore_requires_root_revision_without_parent() -> None:
    state = _state()
    state["planning"]["graph"]["revisions"][0]["parent_version"] = 1
    with pytest.raises(ValueError, match="non-canonical plan parent lineage"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("parent", (None, 2, 3))
def test_restore_requires_immediate_parent_for_later_revision(parent: int | None) -> None:
    state = _state()
    state["planning"]["graph"]["revisions"][1]["parent_version"] = parent
    with pytest.raises(ValueError, match="non-canonical plan parent lineage"):
        OrganizationRuntime.from_state(state)


def test_restore_requires_each_revision_digest_to_match_its_snapshot() -> None:
    state = _state()
    state["planning"]["graph"]["revisions"][0]["graph_digest"] = "noncanonical-digest"
    with pytest.raises(ValueError, match="plan revision digest mismatch"):
        OrganizationRuntime.from_state(state)


def test_restore_requires_each_historical_snapshot_to_match_its_revision_digest() -> None:
    state = _state()
    state["planning"]["graph"]["snapshots"]["1"]["nodes"][0]["title"] = "Alternate historical plan"
    with pytest.raises(ValueError, match="plan revision digest mismatch"):
        OrganizationRuntime.from_state(state)
