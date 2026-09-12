from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.planning import PlanNode


def _runtime_state_with_one_plan_revision() -> dict[str, object]:
    runtime = OrganizationRuntime.first_generation()
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="establish canonical restore-grammar witness",
        evidence_refs=("ev-plan-restore-grammar",),
        upsert_nodes=(PlanNode("plan-restore-grammar", "Plan restore grammar"),),
    )
    state = runtime.to_state()

    revision = state["planning"]["graph"]["revisions"][0]
    assert revision["version"] == 1
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.planning.graph.version == 1
    return state


@pytest.mark.parametrize("malformed_version", (True, "1", 1.0))
def test_master_plan_revision_restore_grammar_rejects_coercible_version_types(
    malformed_version: object,
) -> None:
    state = _runtime_state_with_one_plan_revision()
    state["planning"]["graph"]["revisions"][0]["version"] = malformed_version

    with pytest.raises(ValueError, match="plan revision version must be a positive integer"):
        OrganizationRuntime.from_state(state)
