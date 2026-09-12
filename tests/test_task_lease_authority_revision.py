from __future__ import annotations

from cogcoder.organization.runtime import OrganizationRuntime


def test_task_lease_authority_revision_tracks_only_real_lease_revocation() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = next(
        row for row in runtime.registry.identities() if row.agent_id != "nolane.central"
    )
    task_id = "task-lease-authority-revision"
    runtime.tasks.add_task(task_id, title="lease authority revision", plan_node_id="P1")

    assert runtime.tasks.lease_authority_revision(task_id) == 0

    runtime.tasks.lease(task_id, identity.agent_id)
    assert runtime.tasks.lease_authority_revision(task_id) == 0

    # Reasserting the same holder is not a revocation and must not stale an in-flight decision.
    runtime.tasks.lease(task_id, identity.agent_id)
    assert runtime.tasks.lease_authority_revision(task_id) == 0

    runtime.tasks.release_lease(task_id, identity.agent_id)
    assert runtime.tasks.lease_authority_revision(task_id) == 1

    # Restoring authority never erases the revocation generation.
    runtime.tasks.lease(task_id, identity.agent_id)
    assert runtime.tasks.lease_authority_revision(task_id) == 1

    runtime.tasks.release_lease(task_id, identity.agent_id)
    assert runtime.tasks.lease_authority_revision(task_id) == 2


def test_task_lease_authority_revision_survives_full_runtime_restore() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = next(
        row for row in runtime.registry.identities() if row.agent_id != "nolane.central"
    )
    task_id = "task-lease-authority-restore"
    runtime.tasks.add_task(task_id, title="lease authority restore", plan_node_id="P1")

    runtime.tasks.lease(task_id, identity.agent_id)
    runtime.tasks.release_lease(task_id, identity.agent_id)
    runtime.tasks.lease(task_id, identity.agent_id)
    runtime.tasks.release_lease(task_id, identity.agent_id)

    assert runtime.tasks.get(task_id).leased_to is None
    assert runtime.tasks.lease_authority_revision(task_id) == 2

    restored = OrganizationRuntime.from_state(runtime.to_state())

    assert restored.tasks.get(task_id).leased_to is None
    assert restored.tasks.lease_authority_revision(task_id) == 2

    # A post-restore revocation must continue from the historical generation,
    # never restart a competing authority timeline at zero.
    restored.tasks.lease(task_id, identity.agent_id)
    assert restored.tasks.lease_authority_revision(task_id) == 2
    restored.tasks.release_lease(task_id, identity.agent_id)
    assert restored.tasks.lease_authority_revision(task_id) == 3


def test_task_lease_authority_revision_ignores_heartbeat_and_same_holder_grant() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = next(
        row for row in runtime.registry.identities() if row.agent_id != "nolane.central"
    )
    task_id = "task-lease-authority-renewal-control"
    runtime.tasks.add_task(task_id, title="lease renewal control", plan_node_id="P1")

    lease = runtime.coordination.leases.grant(task_id, identity.agent_id, token=1)
    assert runtime.tasks.lease_authority_revision(task_id) == 0

    same = runtime.coordination.leases.grant(task_id, identity.agent_id, token=2)
    assert same.lease_id == lease.lease_id
    assert same.epoch == lease.epoch
    assert runtime.tasks.lease_authority_revision(task_id) == 0

    renewed = runtime.coordination.leases.heartbeat(
        task_id,
        identity.agent_id,
        lease_id=lease.lease_id,
        epoch=lease.epoch,
        token=2,
    )
    assert renewed.renewal_count == lease.renewal_count + 1
    assert runtime.tasks.lease_authority_revision(task_id) == 0
