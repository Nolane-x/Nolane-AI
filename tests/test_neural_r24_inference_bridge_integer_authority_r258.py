from types import SimpleNamespace

import pytest

from nolane.external_core.context import ContextCapsule
from nolane.external_core.execution_types import ExecutionCounters
from nolane.neural.inference_bridge import CognitiveStateEncoder


def _capsule() -> ContextCapsule:
    return ContextCapsule(
        agent_id="agent-r258",
        task_id="task-r258",
        plan_version=1,
        since_event_id=None,
        memories=(),
        event_delta=(),
        authoritative_artifacts=(("master-plan", 1),),
        tools=("filesystem",),
        external_cores=("memory",),
        authority_boundary=("workspace",),
    )


def _build_request(
    *,
    step_index=0,
    execution_lineage_version=1,
    execution_session_id=None,
    workspace_epoch_id=None,
):
    return CognitiveStateEncoder().build_request(
        identity=SimpleNamespace(
            agent_id="agent-r258",
            neural_version="Neural-R2.3-Ultra-Recursive-DAgger-Gated",
        ),
        capsule=_capsule(),
        task_id="task-r258",
        action_schema=("inspect", "complete"),
        counters=ExecutionCounters(),
        step_index=step_index,
        checkpoint_digest="checkpoint-r258",
        execution_lineage_version=execution_lineage_version,
        execution_session_id=execution_session_id,
        workspace_epoch_id=workspace_epoch_id,
    )


@pytest.mark.parametrize("step_index", (False, 0.0, "0"))
def test_r258_encoder_rejects_non_exact_integer_step_frontier(step_index) -> None:
    with pytest.raises(ValueError, match="step index must be an exact integer"):
        _build_request(step_index=step_index)


@pytest.mark.parametrize("lineage_version", (True, 1.0, "1"))
def test_r258_encoder_rejects_non_exact_integer_execution_lineage_version(lineage_version) -> None:
    with pytest.raises(ValueError, match="execution lineage version must be an exact integer"):
        _build_request(execution_lineage_version=lineage_version)


@pytest.mark.parametrize("lineage_version", (2.0, "2"))
def test_r258_encoder_rejects_modern_lineage_alias_before_session_binding(lineage_version) -> None:
    with pytest.raises(ValueError, match="execution lineage version must be an exact integer"):
        _build_request(
            execution_lineage_version=lineage_version,
            execution_session_id="session-r258",
            workspace_epoch_id="epoch-r258",
        )


def test_r258_encoder_preserves_canonical_integer_frontiers() -> None:
    legacy = _build_request(step_index=0, execution_lineage_version=1)
    assert type(legacy.step_index) is int
    assert legacy.step_index == 0
    assert type(legacy.execution_lineage_version) is int
    assert legacy.execution_lineage_version == 1

    modern = _build_request(
        step_index=3,
        execution_lineage_version=2,
        execution_session_id="session-r258",
        workspace_epoch_id="epoch-r258",
    )
    assert type(modern.step_index) is int
    assert modern.step_index == 3
    assert type(modern.execution_lineage_version) is int
    assert modern.execution_lineage_version == 2
