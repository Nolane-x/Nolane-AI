from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.execution_types import AgentDecisionReceipt, InferenceRequest


class _Backend:
    def __init__(self, *, backend_id: str, checkpoint_digest: str) -> None:
        self.backend_id = backend_id
        self.checkpoint_digest = checkpoint_digest

    def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
        raise AssertionError("backend binding revision contract does not execute inference")


def test_backend_binding_authority_revision_tracks_distinct_successful_bindings() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    backend_a = _Backend(
        backend_id="backend-binding-revision-v1",
        checkpoint_digest="backend-binding-revision-checkpoint-v1",
    )
    backend_b = _Backend(
        backend_id=backend_a.backend_id,
        checkpoint_digest=backend_a.checkpoint_digest,
    )

    assert runtime.execution.backend_binding_authority_revision(identity.agent_id) == 0

    runtime.execution.bind_backend(identity.agent_id, backend_a)
    assert runtime.execution.backend_binding_authority_revision(identity.agent_id) == 1

    # Reasserting the exact same backend object is idempotent authority.
    runtime.execution.bind_backend(identity.agent_id, backend_a)
    assert runtime.execution.backend_binding_authority_revision(identity.agent_id) == 1

    # A proof-equivalent but distinct backend is a fresh binding generation.
    runtime.execution.bind_backend(identity.agent_id, backend_b)
    assert runtime.execution.backend_binding_authority_revision(identity.agent_id) == 2


def test_backend_binding_authority_revision_is_not_advanced_by_failed_bind() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    backend = _Backend(
        backend_id="backend-binding-failed-bind-v1",
        checkpoint_digest="backend-binding-failed-bind-checkpoint-v1",
    )
    runtime.execution.bind_backend(identity.agent_id, backend)
    revision = runtime.execution.backend_binding_authority_revision(identity.agent_id)

    invalid = _Backend(
        backend_id="",
        checkpoint_digest=backend.checkpoint_digest,
    )
    with pytest.raises(ValueError):
        runtime.execution.bind_backend(identity.agent_id, invalid)

    assert runtime.execution.backend_binding_authority_revision(identity.agent_id) == revision
    assert runtime.execution._backends[identity.agent_id] is backend
