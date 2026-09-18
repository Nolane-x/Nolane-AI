import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution_types import ExecutionCounters, InferenceRequest


def _request_kwargs(**overrides):
    schema = ("inspect", "complete")
    values = {
        "agent_id": "agent-r260",
        "neural_version": "Neural-R2.3-Ultra-Recursive-DAgger-Gated",
        "task_id": "task-r260",
        "context_digest": canonical_digest({"context": "r260"}),
        "encoder_version": "encoder-r260",
        "checkpoint_digest": "checkpoint-r260",
        "action_schema": schema,
        "action_schema_digest": canonical_digest(list(schema)),
        "counters": ExecutionCounters(),
        "step_index": 0,
        "execution_lineage_version": 1,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize("step_index", (False, 0.0, "0"))
def test_r260_direct_request_rejects_non_exact_integer_step_index(step_index) -> None:
    with pytest.raises(ValueError, match="step index must be an exact integer"):
        InferenceRequest(**_request_kwargs(step_index=step_index))


@pytest.mark.parametrize("lineage_version", (True, 1.0, "1"))
def test_r260_direct_request_rejects_non_exact_legacy_lineage_version(lineage_version) -> None:
    with pytest.raises(ValueError, match="execution lineage version must be an exact integer"):
        InferenceRequest(**_request_kwargs(execution_lineage_version=lineage_version))


@pytest.mark.parametrize("lineage_version", (2.0, "2"))
def test_r260_direct_request_rejects_non_exact_modern_lineage_version(lineage_version) -> None:
    with pytest.raises(ValueError, match="execution lineage version must be an exact integer"):
        InferenceRequest(
            **_request_kwargs(
                execution_lineage_version=lineage_version,
                execution_session_id="session-r260",
                workspace_epoch_id="epoch-r260",
            )
        )


@pytest.mark.parametrize("step_index", (False, 0.0, "0"))
def test_r260_restore_rejects_non_exact_integer_step_index(step_index) -> None:
    canonical = InferenceRequest(**_request_kwargs())
    state = canonical.to_state()
    state["step_index"] = step_index

    with pytest.raises(ValueError, match="step index must be an exact integer"):
        InferenceRequest.from_state(state)


@pytest.mark.parametrize("lineage_version", (True, 1.0, "1"))
def test_r260_restore_rejects_non_exact_legacy_lineage_version(lineage_version) -> None:
    canonical = InferenceRequest(**_request_kwargs())
    state = canonical.to_state()
    state["execution_lineage_version"] = lineage_version

    with pytest.raises(ValueError, match="execution lineage version must be an exact integer"):
        InferenceRequest.from_state(state)


@pytest.mark.parametrize("lineage_version", (2.0, "2"))
def test_r260_restore_rejects_non_exact_modern_lineage_version(lineage_version) -> None:
    canonical = InferenceRequest(
        **_request_kwargs(
            execution_lineage_version=2,
            execution_session_id="session-r260",
            workspace_epoch_id="epoch-r260",
        )
    )
    state = canonical.to_state()
    state["execution_lineage_version"] = lineage_version

    with pytest.raises(ValueError, match="execution lineage version must be an exact integer"):
        InferenceRequest.from_state(state)


def test_r260_canonical_integer_request_roundtrips_unchanged() -> None:
    canonical = InferenceRequest(
        **_request_kwargs(
            step_index=4,
            execution_lineage_version=2,
            execution_session_id="session-r260",
            workspace_epoch_id="epoch-r260",
        )
    )

    restored = InferenceRequest.from_state(canonical.to_state())

    assert restored == canonical
    assert type(restored.step_index) is int
    assert type(restored.execution_lineage_version) is int
