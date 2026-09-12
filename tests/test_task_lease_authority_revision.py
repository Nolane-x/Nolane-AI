from __future__ import annotations

import pytest

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

    state = runtime.to_state()
    assert state["tasks"]["lease_authority_revisions"][task_id] == 2
    restored = OrganizationRuntime.from_state(state)

    assert restored.tasks.get(task_id).leased_to is None
    assert restored.tasks.lease_authority_revision(task_id) == 2

    # A post-restore revocation must continue from the historical generation,
    # never restart a competing authority timeline at zero.
    restored.tasks.lease(task_id, identity.agent_id)
    assert restored.tasks.lease_authority_revision(task_id) == 2
    restored.tasks.release_lease(task_id, identity.agent_id)
    assert restored.tasks.lease_authority_revision(task_id) == 3


def test_task_lease_authority_revision_legacy_snapshot_defaults_to_zero() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = next(
        row for row in runtime.registry.identities() if row.agent_id != "nolane.central"
    )
    task_id = "task-lease-authority-legacy"
    runtime.tasks.add_task(task_id, title="lease authority legacy", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)
    runtime.tasks.release_lease(task_id, identity.agent_id)
    assert runtime.tasks.lease_authority_revision(task_id) == 1

    state = runtime.to_state()
    state["tasks"].pop("lease_authority_revisions")
    restored = OrganizationRuntime.from_state(state)

    assert restored.tasks.lease_authority_revision(task_id) == 0


@pytest.mark.parametrize(
    "case",
    (
        "non_mapping",
        "non_string_key",
        "missing_task",
        "unknown_task",
        "bool_revision",
        "string_revision",
        "float_revision",
        "negative_revision",
    ),
)
def test_task_lease_authority_revision_present_state_fails_closed(case: str) -> None:
    runtime = OrganizationRuntime.first_generation()
    task_id = "task-lease-authority-malformed"
    runtime.tasks.add_task(task_id, title="lease authority malformed", plan_node_id="P1")
    state = runtime.to_state()
    revisions = state["tasks"]["lease_authority_revisions"]

    if case == "non_mapping":
        state["tasks"]["lease_authority_revisions"] = []
    elif case == "non_string_key":
        revisions[1] = revisions.pop(task_id)
    elif case == "missing_task":
        revisions.pop(task_id)
    elif case == "unknown_task":
        revisions["unknown-task"] = 0
    elif case == "bool_revision":
        revisions[task_id] = True
    elif case == "string_revision":
        revisions[task_id] = "1"
    elif case == "float_revision":
        revisions[task_id] = 1.0
    elif case == "negative_revision":
        revisions[task_id] = -1
    else:  # pragma: no cover - parameter list is intentionally closed.
        raise AssertionError(case)

    with pytest.raises(ValueError):
        OrganizationRuntime.from_state(state)


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
