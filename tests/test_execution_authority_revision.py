from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.organization.identity import AgentRegistry
from nolane.schemas.identity import AgentStatus


def test_execution_authority_revision_tracks_only_true_revoking_transitions() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    agent_id = identity.agent_id

    assert runtime.registry.get(agent_id).status is AgentStatus.SLEEPING
    assert runtime.registry.execution_authority_revision(agent_id) == 0

    # Reasserting the same revoking state is not a new revocation event.
    runtime.registry.set_status(agent_id, AgentStatus.SLEEPING)
    assert runtime.registry.execution_authority_revision(agent_id) == 0

    # Entering and traversing non-revoking lifecycle states must not poison
    # execution authority merely because the identity row changed.
    runtime.registry.set_status(agent_id, AgentStatus.ACTIVE)
    assert runtime.registry.execution_authority_revision(agent_id) == 0
    for status in (
        AgentStatus.WAITING,
        AgentStatus.BLOCKED,
        AgentStatus.CHECKPOINTING,
        AgentStatus.QUARANTINED,
        AgentStatus.WAKING,
    ):
        runtime.registry.set_status(agent_id, status)
        assert runtime.registry.execution_authority_revision(agent_id) == 0
        runtime.registry.set_status(agent_id, AgentStatus.ACTIVE)
        assert runtime.registry.execution_authority_revision(agent_id) == 0

    # A true transition into SLEEPING revokes the authority generation exactly
    # once; restoring ACTIVE does not erase historical revocation evidence.
    runtime.registry.set_status(agent_id, AgentStatus.SLEEPING)
    assert runtime.registry.execution_authority_revision(agent_id) == 1
    runtime.registry.set_status(agent_id, AgentStatus.SLEEPING)
    assert runtime.registry.execution_authority_revision(agent_id) == 1
    runtime.registry.set_status(agent_id, AgentStatus.ACTIVE)
    assert runtime.registry.execution_authority_revision(agent_id) == 1

    # PAUSED is the other execution-revoking state already enforced by the
    # shared post-inference authority guard.
    runtime.registry.set_status(agent_id, AgentStatus.PAUSED)
    assert runtime.registry.execution_authority_revision(agent_id) == 2
    runtime.registry.set_status(agent_id, AgentStatus.PAUSED)
    assert runtime.registry.execution_authority_revision(agent_id) == 2
    runtime.registry.set_status(agent_id, AgentStatus.ACTIVE)
    assert runtime.registry.execution_authority_revision(agent_id) == 2


def test_neural_version_authority_revision_tracks_only_true_version_switches() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    agent_id = identity.agent_id
    initial_version = identity.neural_version
    alternate_version = initial_version + ".authority-revision"

    assert runtime.registry.neural_version_authority_revision(agent_id) == 0

    # Reasserting the currently active model authority is idempotent.
    runtime.registry.accept_neural_version(agent_id, initial_version)
    assert runtime.registry.neural_version_authority_revision(agent_id) == 0

    # Switching the active neural authority invalidates the prior neural
    # generation even when the target version was or becomes accepted.
    runtime.registry.accept_neural_version(agent_id, alternate_version)
    assert runtime.registry.neural_version_authority_revision(agent_id) == 1
    runtime.registry.accept_neural_version(agent_id, alternate_version)
    assert runtime.registry.neural_version_authority_revision(agent_id) == 1

    # Restoring the original version is another true authority switch; it must
    # not erase the fact that in-flight decisions crossed a model boundary.
    runtime.registry.accept_neural_version(agent_id, initial_version)
    assert runtime.registry.neural_version_authority_revision(agent_id) == 2

    # Neural version changes are independent from lifecycle revocation state.
    assert runtime.registry.execution_authority_revision(agent_id) == 0


def _advance_all_identity_authority_revisions(runtime: OrganizationRuntime) -> str:
    agent_id = runtime.registry.identities()[0].agent_id

    runtime.registry.set_status(agent_id, AgentStatus.ACTIVE)
    runtime.registry.set_status(agent_id, AgentStatus.SLEEPING)
    runtime.registry.set_status(agent_id, AgentStatus.ACTIVE)

    initial_neural_version = runtime.registry.get(agent_id).neural_version
    alternate_neural_version = initial_neural_version + ".restore-revision"
    runtime.registry.accept_neural_version(agent_id, alternate_neural_version)
    runtime.registry.accept_neural_version(agent_id, initial_neural_version)

    initial_self_model_version = runtime.registry.get(agent_id).self_model_version
    alternate_self_model_version = initial_self_model_version + ".restore-revision"
    runtime.registry.set_self_model_version(agent_id, alternate_self_model_version)
    runtime.registry.set_self_model_version(agent_id, initial_self_model_version)
    return agent_id


def _authority_revision_tuple(registry: AgentRegistry, agent_id: str) -> tuple[int, int, int]:
    return (
        registry.execution_authority_revision(agent_id),
        registry.neural_version_authority_revision(agent_id),
        registry.self_model_authority_revision(agent_id),
    )


def test_identity_authority_revisions_survive_runtime_snapshot_restore() -> None:
    runtime = OrganizationRuntime.first_generation()
    agent_id = _advance_all_identity_authority_revisions(runtime)

    expected = _authority_revision_tuple(runtime.registry, agent_id)
    assert expected == (1, 2, 2)

    restored = OrganizationRuntime.from_state(runtime.to_state())

    assert _authority_revision_tuple(restored.registry, agent_id) == expected


def test_legacy_registry_snapshot_without_authority_revisions_defaults_to_zero() -> None:
    runtime = OrganizationRuntime.first_generation()
    agent_id = _advance_all_identity_authority_revisions(runtime)
    state = runtime.registry.to_state()
    state.pop("authority_revisions")

    restored = AgentRegistry.from_state(state)

    assert _authority_revision_tuple(restored, agent_id) == (0, 0, 0)


@pytest.mark.parametrize(
    "malformation",
    (
        "top_level_non_mapping",
        "missing_agent",
        "unknown_agent",
        "row_non_mapping",
        "row_missing_field",
        "row_extra_field",
        "boolean_revision",
        "negative_revision",
        "string_revision",
        "float_revision",
    ),
)
def test_present_authority_revision_snapshot_rejects_noncanonical_state(
    malformation: str,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    agent_id = _advance_all_identity_authority_revisions(runtime)
    state = runtime.registry.to_state()
    revisions = state["authority_revisions"]
    assert isinstance(revisions, dict)
    assert isinstance(revisions[agent_id], dict)

    if malformation == "top_level_non_mapping":
        state["authority_revisions"] = []
    elif malformation == "missing_agent":
        revisions.pop(agent_id)
    elif malformation == "unknown_agent":
        revisions["unknown.agent"] = {
            "execution": 0,
            "neural_version": 0,
            "self_model": 0,
        }
    elif malformation == "row_non_mapping":
        revisions[agent_id] = []
    elif malformation == "row_missing_field":
        revisions[agent_id].pop("self_model")
    elif malformation == "row_extra_field":
        revisions[agent_id]["unexpected"] = 0
    elif malformation == "boolean_revision":
        revisions[agent_id]["execution"] = True
    elif malformation == "negative_revision":
        revisions[agent_id]["execution"] = -1
    elif malformation == "string_revision":
        revisions[agent_id]["execution"] = "1"
    elif malformation == "float_revision":
        revisions[agent_id]["execution"] = 1.0
    else:  # pragma: no cover - the parameter set above is exhaustive.
        raise AssertionError(f"unknown malformation fixture: {malformation}")

    with pytest.raises(ValueError):
        AgentRegistry.from_state(state)
