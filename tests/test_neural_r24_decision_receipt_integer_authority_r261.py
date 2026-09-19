import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionCounters,
    InferenceRequest,
)


def _request() -> InferenceRequest:
    schema = ("inspect", "complete")
    return InferenceRequest(
        agent_id="agent-r261",
        neural_version="Neural-R2.3-Ultra-Recursive-DAgger-Gated",
        task_id="task-r261",
        context_digest=canonical_digest({"context": "r261"}),
        encoder_version="encoder-r261",
        checkpoint_digest="checkpoint-r261",
        action_schema=schema,
        action_schema_digest=canonical_digest(list(schema)),
        counters=ExecutionCounters(),
        step_index=0,
        execution_lineage_version=2,
        execution_session_id="session-r261",
        workspace_epoch_id="epoch-r261",
    )


def _decision() -> AgentDecisionReceipt:
    return AgentDecisionReceipt.create(
        backend_id="backend-r261",
        request=_request(),
        action=ExecutionAction.wait(reason="hold"),
        compute_units=1,
    )


def _direct_variant(
    canonical: AgentDecisionReceipt,
    *,
    step_index=None,
    request_provenance_version=None,
) -> AgentDecisionReceipt:
    direct_step_index = canonical.step_index if step_index is None else step_index
    direct_version = (
        canonical.request_provenance_version
        if request_provenance_version is None
        else request_provenance_version
    )

    payload = canonical.payload()
    payload["step_index"] = direct_step_index
    if request_provenance_version is not None:
        # Current constructor launders aliases through int(...), so a self-consistent
        # accepted payload is still the canonical integer version after construction.
        payload["request_provenance_version"] = canonical.request_provenance_version
    digest = canonical_digest(payload)

    return AgentDecisionReceipt(
        receipt_id="decision-" + digest[:24],
        backend_id=canonical.backend_id,
        request_digest=canonical.request_digest,
        agent_id=canonical.agent_id,
        neural_version=canonical.neural_version,
        checkpoint_digest=canonical.checkpoint_digest,
        encoder_version=canonical.encoder_version,
        context_digest=canonical.context_digest,
        action_schema_digest=canonical.action_schema_digest,
        step_index=direct_step_index,
        action=canonical.action,
        compute_units=canonical.compute_units,
        digest=digest,
        cognitive_state_digest=canonical.cognitive_state_digest,
        request_provenance_version=direct_version,
        request=canonical.request,
    )


@pytest.mark.parametrize("step_index", (False, 0.0))
def test_r261_direct_decision_rejects_non_exact_integer_step_index(step_index) -> None:
    canonical = _decision()

    with pytest.raises(ValueError, match="decision step index must be an exact integer"):
        _direct_variant(canonical, step_index=step_index)


@pytest.mark.parametrize("version", (2.0, "2"))
def test_r261_direct_decision_rejects_non_exact_integer_request_provenance_version(version) -> None:
    canonical = _decision()

    with pytest.raises(
        ValueError,
        match="inference request provenance version must be an exact integer",
    ):
        _direct_variant(canonical, request_provenance_version=version)


@pytest.mark.parametrize("step_index", (False, 0.0, "0"))
def test_r261_restore_rejects_step_index_alias_before_digest_revalidation(step_index) -> None:
    state = _decision().to_state()
    state["step_index"] = step_index

    with pytest.raises(ValueError, match="decision step index must be an exact integer"):
        AgentDecisionReceipt.from_state(state)


@pytest.mark.parametrize("compute_units", (True, 1.0, "1"))
def test_r261_restore_rejects_compute_unit_alias_before_digest_revalidation(compute_units) -> None:
    state = _decision().to_state()
    state["compute_units"] = compute_units

    with pytest.raises(ValueError):
        AgentDecisionReceipt.from_state(state)


@pytest.mark.parametrize("version", (2.0, "2"))
def test_r261_restore_rejects_request_provenance_alias_before_digest_revalidation(version) -> None:
    state = _decision().to_state()
    state["request_provenance_version"] = version

    with pytest.raises(
        ValueError,
        match="inference request provenance version must be an exact integer",
    ):
        AgentDecisionReceipt.from_state(state)


def test_r261_canonical_decision_receipt_roundtrips_without_semantic_change() -> None:
    canonical = _decision()
    restored = AgentDecisionReceipt.from_state(canonical.to_state())

    assert restored == canonical
    assert type(restored.step_index) is int
    assert type(restored.compute_units) is int
    assert type(restored.request_provenance_version) is int
