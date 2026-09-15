from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution_executor import CoreInvocationReceipt


def _canonical_receipt_state() -> dict[str, object]:
    payload: dict[str, object] = {
        "agent_id": "coding.backend.01",
        "task_id": "task-r232-receipt-state-authority",
        "tool_id": "external.example",
        "operation": "invoke",
        "authorized": True,
        "success": True,
        "external_core": True,
        "failure_kind": None,
        "before_workspace_digest": "before",
        "after_workspace_digest": "after",
        "input_digest": "input",
        "output_artifact_ids": [],
        "evidence_artifact_id": "artifact-r232",
        "mirrored_tool_receipt_id": None,
    }
    digest = canonical_digest(payload)
    return {
        "receipt_id": "core-" + digest[:24],
        **payload,
        "digest": digest,
    }


@pytest.mark.parametrize("field", ("authorized", "success", "external_core"))
def test_core_receipt_state_rejects_non_boolean_authority_alias(field: str) -> None:
    state = _canonical_receipt_state()
    state[field] = "false"

    with pytest.raises(
        ValueError,
        match=rf"core invocation receipt {field} must be exact bool",
    ):
        CoreInvocationReceipt.from_state(state)
