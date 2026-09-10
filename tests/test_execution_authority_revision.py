from __future__ import annotations

from cogcoder.organization.runtime import OrganizationRuntime
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


def test_execution_authority_revision_tracks_true_neural_version_switches() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    agent_id = identity.agent_id
    initial_version = identity.neural_version
    alternate_version = initial_version + ".authority-revision"

    assert runtime.registry.execution_authority_revision(agent_id) == 0

    # Reasserting the currently active model authority is idempotent.
    runtime.registry.accept_neural_version(agent_id, initial_version)
    assert runtime.registry.execution_authority_revision(agent_id) == 0

    # Switching the active neural authority invalidates the prior execution
    # generation even when the target version was or becomes accepted.
    runtime.registry.accept_neural_version(agent_id, alternate_version)
    assert runtime.registry.execution_authority_revision(agent_id) == 1
    runtime.registry.accept_neural_version(agent_id, alternate_version)
    assert runtime.registry.execution_authority_revision(agent_id) == 1

    # Restoring the original version is another true authority switch; it must
    # not erase the fact that in-flight decisions crossed a model boundary.
    runtime.registry.accept_neural_version(agent_id, initial_version)
    assert runtime.registry.execution_authority_revision(agent_id) == 2
