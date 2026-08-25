from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.core.canonical_digest import canonical_digest, canonical_json


_PUBLIC_SYMBOLS = (
    "ExecutionActionKind",
    "ToolAction",
    "ExecutionAction",
    "ExecutionBudget",
    "ExecutionCounters",
    "InferenceRequest",
    "AgentDecisionReceipt",
)


def test_wave5u_canonical_execution_schemas_own_complete_public_implementation() -> None:
    import nolane.external_core.execution_types as canonical

    assert all(
        getattr(canonical, name).__module__ == "nolane.external_core.execution_types"
        for name in _PUBLIC_SYMBOLS
    )


def test_wave5u_historical_execution_types_are_exact_public_object_bridge() -> None:
    import cogcoder.organization.execution_types as legacy
    import nolane.external_core.execution_types as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5u_canonical_execution_schemas_have_no_reverse_authority_import() -> None:
    import nolane.external_core.execution_types as canonical

    source_path = Path(canonical.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    has_native_digest = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cogcoder.organization.execution_types" or alias.name.startswith(
                    "cogcoder.organization.execution_types."
                ):
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cogcoder.organization.execution_types" or module.startswith(
                "cogcoder.organization.execution_types."
            ):
                offenders.append(f"from:{node.lineno}:{module}")
            if module == "nolane.core.canonical_digest":
                names = {alias.name for alias in node.names}
                has_native_digest = {"canonical_digest", "canonical_json"} <= names

    assert offenders == [], (
        "canonical execution schemas reverse-import historical execution types: "
        + "; ".join(offenders)
    )
    assert has_native_digest, "execution schemas must use canonical JSON/digest authority"


def test_wave5u_tool_action_preserves_canonical_json_and_mutation_scope_fail_closed() -> None:
    from nolane.external_core.execution_types import ToolAction

    row = ToolAction.from_arguments(
        "filesystem",
        "write_text",
        {"content": "hello", "path": "src/a.py"},
    )
    assert row.arguments_json == canonical_json({"content": "hello", "path": "src/a.py"})
    assert row.mutation_paths == ("src/a.py",)
    assert row.arguments == {"content": "hello", "path": "src/a.py"}
    assert ToolAction.from_state(row.to_state()) == row

    with pytest.raises(ValueError, match="declared mutation scope conflicts"):
        ToolAction.from_arguments(
            "filesystem",
            "write_text",
            {"content": "hello", "path": "src/a.py"},
            mutation_paths=("src/b.py",),
        )

    corrupt = row.to_state()
    corrupt["mutation_paths"] = []
    with pytest.raises(ValueError, match="snapshot omits or corrupts"):
        ToolAction.from_state(corrupt)


def test_wave5u_execution_action_budget_counters_and_receipt_round_trip() -> None:
    from nolane.external_core.execution_types import (
        AgentDecisionReceipt,
        ExecutionAction,
        ExecutionBudget,
        ExecutionCounters,
        InferenceRequest,
        ToolAction,
    )

    tool = ToolAction.from_arguments("shell", "run", {"argv": ["python", "-V"]})
    action = ExecutionAction.tool(tool)
    assert ExecutionAction.from_state(action.to_state()) == action

    budget = ExecutionBudget(5, 4, 3, 2)
    assert ExecutionBudget.from_state(budget.to_state()) == budget
    counters = ExecutionCounters(steps=1, tool_calls=1, external_core_calls=0, compute_units=1)
    assert ExecutionCounters.from_state(counters.to_state()) == counters

    schema = ("tool", "complete", "wait", "fail")
    request = InferenceRequest(
        agent_id="coding.impl.1",
        neural_version="r2.3",
        task_id="task-5u",
        context_digest="context-digest",
        encoder_version="encoder-v1",
        checkpoint_digest="checkpoint-digest",
        action_schema=schema,
        action_schema_digest=canonical_digest(list(schema)),
        counters=counters,
        step_index=1,
    )
    restored_request = InferenceRequest.from_state(request.to_state())
    assert restored_request == request
    assert restored_request.digest == request.digest

    receipt = AgentDecisionReceipt.create(
        backend_id="backend.test",
        request=request,
        action=action,
        compute_units=1,
    )
    assert AgentDecisionReceipt.from_state(receipt.to_state()) == receipt

    corrupted = receipt.to_state()
    corrupted["digest"] = "0" * 64
    with pytest.raises(ValueError, match="decision receipt digest/id mismatch"):
        AgentDecisionReceipt.from_state(corrupted)


def test_wave5u_is_prerequisite_only_and_does_not_falsely_retire_execution_debt() -> None:
    ledger = build_component_implementation_ledger()
    assert ledger["external.execution.executor"].status is ImplementationStatus.COMPATIBILITY_FACADE
    assert ledger["external.execution.control"].status is ImplementationStatus.COMPATIBILITY_FACADE

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {row["component_id"] for row in state["components"]}
    assert "external.execution.executor" in ids
    assert "external.execution.control" in ids
    assert len(state["components"]) == 26


def test_wave5u_current_status_tracks_canonical_execution_schema_prerequisite() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")

    assert "Wave 5U" in status
    assert "canonical execution schemas" in status.lower()
