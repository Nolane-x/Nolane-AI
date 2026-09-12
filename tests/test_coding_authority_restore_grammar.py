from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.coding_profiles import CodingDomain, CodingWorkRequest


def _runtime_with_coding_assignment_authority() -> OrganizationRuntime:
    runtime = OrganizationRuntime.first_generation()
    task_id = "task-coding-authority-restore-grammar"
    runtime.tasks.add_task(
        task_id,
        title="coding authority restore grammar",
        plan_node_id="P1",
    )
    work = CodingWorkRequest(
        work_id="work-coding-authority-restore-grammar",
        task_id=task_id,
        plan_node_id="P1",
        requirement_refs=(),
        architecture_version=runtime.architecture.graph.version,
        plan_version=runtime.planning.graph.version,
        requested_domains=(CodingDomain.CROSS_SYSTEM,),
        scope_hints=("cross-system",),
        acceptance_refs=(),
        priority=80,
        requester_agent_id="coding.chief",
        evidence_refs=("coding-authority-restore-grammar-evidence",),
    )
    runtime.coding.request_work(
        work,
        override_agent_id="coding.chief",
        override_actor_id="nolane.central",
    )
    assert runtime.coding.assignment_authority_revision == 1
    return runtime


@pytest.mark.parametrize("malformed_revision", [True, "1", 1.0])
def test_coding_assignment_authority_restore_rejects_noncanonical_revision_types(
    malformed_revision: object,
) -> None:
    runtime = _runtime_with_coding_assignment_authority()
    state = runtime.to_state()
    assert state["coding"]["assignment_authority_revision"] == 1
    state["coding"]["assignment_authority_revision"] = malformed_revision

    with pytest.raises(
        ValueError,
        match="assignment authority revision.*non-negative integer",
    ):
        OrganizationRuntime.from_state(state)
