from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.context import ContextCapsule
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionCounters,
)
from nolane.neural.inference_bridge import CognitiveStateEncoder


def _request():
    capsule = ContextCapsule(
        agent_id="agent-1",
        task_id="task-1",
        plan_version=3,
        since_event_id=None,
        memories=(),
        event_delta=(),
        authoritative_artifacts=(("master-plan", 3),),
        tools=("filesystem",),
        external_cores=("memory",),
        authority_boundary=("workspace",),
    )
    return CognitiveStateEncoder().build_request(
        identity=SimpleNamespace(
            agent_id="agent-1",
            neural_version="Neural-R2.3-Ultra-Recursive-DAgger-Gated",
        ),
        capsule=capsule,
        task_id="task-1",
        action_schema=("inspect", "complete"),
        counters=ExecutionCounters(),
        step_index=0,
        checkpoint_digest="checkpoint-digest",
    )


def _decision() -> AgentDecisionReceipt:
    return AgentDecisionReceipt.create(
        backend_id="neural-test-backend",
        request=_request(),
        action=ExecutionAction.wait(reason="hold"),
    )


def test_direct_decision_receipt_constructor_rejects_forged_digest_identity():
    canonical = _decision()

    with pytest.raises(ValueError, match="decision receipt direct construction"):
        AgentDecisionReceipt(
            receipt_id="decision-forged",
            backend_id=canonical.backend_id,
            request_digest=canonical.request_digest,
            agent_id=canonical.agent_id,
            neural_version=canonical.neural_version,
            checkpoint_digest=canonical.checkpoint_digest,
            encoder_version=canonical.encoder_version,
            context_digest=canonical.context_digest,
            action_schema_digest=canonical.action_schema_digest,
            step_index=canonical.step_index,
            action=canonical.action,
            compute_units=canonical.compute_units,
            digest="0" * 64,
            cognitive_state_digest=canonical.cognitive_state_digest,
            request_provenance_version=canonical.request_provenance_version,
            request=canonical.request,
        )


def test_direct_decision_receipt_constructor_rejects_zero_compute_authority():
    canonical = _decision()
    payload = canonical.payload()
    payload["compute_units"] = 0
    digest = canonical_digest(payload)

    with pytest.raises(ValueError, match="decision receipt direct construction"):
        AgentDecisionReceipt(
            receipt_id="decision-" + digest[:24],
            backend_id=canonical.backend_id,
            request_digest=canonical.request_digest,
            agent_id=canonical.agent_id,
            neural_version=canonical.neural_version,
            checkpoint_digest=canonical.checkpoint_digest,
            encoder_version=canonical.encoder_version,
            context_digest=canonical.context_digest,
            action_schema_digest=canonical.action_schema_digest,
            step_index=canonical.step_index,
            action=canonical.action,
            compute_units=0,
            digest=digest,
            cognitive_state_digest=canonical.cognitive_state_digest,
            request_provenance_version=canonical.request_provenance_version,
            request=canonical.request,
        )
