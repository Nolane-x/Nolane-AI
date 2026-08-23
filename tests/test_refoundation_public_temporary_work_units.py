from __future__ import annotations

from nolane.runtime import build_runtime
from nolane.work_units import TemporaryWorkUnitBudget


def test_public_work_unit_lifecycle_never_changes_permanent_agent_cardinality() -> None:
    runtime = build_runtime()
    before_ids = {row.agent_id for row in runtime.identities()}
    assert len(before_ids) == 67

    request = runtime.request_work_unit(
        sponsor_agent_id="nolane.central",
        parent_task_id=None,
        template_id="repository-archaeologist",
        mission="inspect historical source without becoming a permanent AI",
        team_id="team-refoundation",
        budget=TemporaryWorkUnitBudget(
            compute_units=20,
            tool_calls=10,
            external_core_calls=5,
            max_workers=1,
            lifetime_tokens=100,
        ),
        current_token=10,
    )
    assert request.kind == "temporary_work_unit_request"
    assert request.status == "requested"

    approved = runtime.approve_work_unit(request.request_id, actor_agent_id="nolane.central")
    assert approved.status == "approved"

    unit = runtime.instantiate_work_unit(request.request_id, current_token=11)
    assert unit.identity_kind == "temporary_work_unit"
    assert unit.permanent_identity is False
    assert unit.agent_registry_membership is False
    assert unit.sponsor_agent_id == "nolane.central"
    assert unit.legacy_request_id == request.request_id

    after_ids = {row.agent_id for row in runtime.identities()}
    assert after_ids == before_ids
    assert unit.work_unit_id not in after_ids


def test_public_work_unit_api_does_not_publish_spawn_or_ephemeral_agent_methods() -> None:
    runtime = build_runtime()
    for forbidden in ("request_spawn", "approve_spawn", "spawn_requests", "ephemeral_agents"):
        assert not hasattr(runtime, forbidden)


def test_public_work_unit_listing_roundtrips_legacy_manifests_without_loss() -> None:
    runtime = build_runtime()
    request = runtime.request_work_unit(
        sponsor_agent_id="nolane.central",
        parent_task_id=None,
        template_id="hypothesis-explorer",
        mission="bounded hypothesis exploration",
        team_id="team-hypothesis",
        budget=TemporaryWorkUnitBudget(10, 10, 10, 1, 20),
        current_token=3,
    )
    runtime.approve_work_unit(request.request_id, actor_agent_id="nolane.central")
    created = runtime.instantiate_work_unit(request.request_id, current_token=4)
    listed = {row.work_unit_id: row for row in runtime.work_units()}
    assert listed[created.work_unit_id] == created
    assert listed[created.work_unit_id].legacy_manifest_digest
