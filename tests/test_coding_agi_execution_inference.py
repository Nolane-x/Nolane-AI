from __future__ import annotations

import json

import pytest

from cogcoder.organization.execution_inference import CognitiveStateEncoder, DeterministicFixtureBackend, R23InferenceBackend
from cogcoder.organization.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionCounters,
)
from cogcoder.organization.runtime import OrganizationRuntime


def test_fixture_backend_decision_receipt_is_deterministic_and_roundtrips():
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.get('coding.backend.01')
    capsule = runtime.context.compile(identity.agent_id, task_id='exec-task')
    action = ExecutionAction.complete(reason='fixture-complete')
    backend = DeterministicFixtureBackend(actions=(action,), checkpoint_digest='fixture-checkpoint-v1')
    encoder = CognitiveStateEncoder(version='org-hash-v1')
    request = encoder.build_request(
        identity=identity,
        capsule=capsule,
        task_id='exec-task',
        action_schema=('filesystem.write_text', 'complete'),
        counters=ExecutionCounters(),
        step_index=0,
        checkpoint_digest=backend.checkpoint_digest,
    )

    first = backend.decide(request)
    second = backend.decide(request)

    assert first == second
    assert first.agent_id == identity.agent_id
    assert first.neural_version == identity.neural_version
    assert first.checkpoint_digest == 'fixture-checkpoint-v1'
    assert first.context_digest == request.context_digest
    assert first.action == action
    assert AgentDecisionReceipt.from_state(first.to_state()) == first


def test_r23_backend_rejects_wrong_checkpoint_hash_before_model_load(tmp_path):
    checkpoint = tmp_path / 'r23.pt'
    checkpoint.write_bytes(b'not-the-accepted-checkpoint')
    metadata = tmp_path / 'CURRENT_BEST.json'
    metadata.write_text(json.dumps({'one_weight_sha256': '0' * 64, 'version': 'Neural-R2.3-Ultra-Recursive-DAgger-Gated'}))

    with pytest.raises(ValueError, match='checkpoint digest'):
        R23InferenceBackend.from_checkpoint(
            checkpoint_path=checkpoint,
            metadata_path=metadata,
            model_root=tmp_path,
        )
