from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version, next_component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution_types import ExecutionBudget, ExecutionCounters


_PUBLIC_SYMBOLS = (
    "ExecutionState",
    "ExecutionSession",
    "ExecutionStepReceipt",
    "ExecutionTerminalReceipt",
    "OrganizationExecutionControlPlane",
)
_FORBIDDEN_LEGACY_PREFIX = "cogcoder.organization"


def test_wave5za_canonical_execution_control_owns_semantic_public_implementation() -> None:
    canonical = importlib.import_module("nolane.external_core.execution")
    failures: list[str] = []
    for name in _PUBLIC_SYMBOLS:
        value = getattr(canonical, name, None)
        if value is None:
            failures.append(f"missing {name}")
        elif value.__module__ != "nolane.external_core.execution":
            failures.append(f"{name} owned by {value.__module__}")
    assert failures == [], "; ".join(failures)


def test_wave5za_historical_execution_module_is_exact_public_object_bridge() -> None:
    canonical = importlib.import_module("nolane.external_core.execution")
    legacy = importlib.import_module("cogcoder.organization.execution")
    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5za_canonical_execution_control_has_no_reverse_historical_authority() -> None:
    root = Path(__file__).resolve().parents[1]
    source_path = root / "nolane" / "external_core" / "execution.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(_FORBIDDEN_LEGACY_PREFIX):
                    offenders.append(f"{node.lineno}:import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(_FORBIDDEN_LEGACY_PREFIX):
                offenders.append(f"{node.lineno}:from:{module}")
    assert offenders == [], "canonical execution control reverse-imports historical authority: " + "; ".join(offenders)


def test_wave5za_execution_session_and_receipts_preserve_state_and_fail_closed_digests() -> None:
    execution = importlib.import_module("nolane.external_core.execution")
    budget = ExecutionBudget(
        max_steps=3,
        max_tool_calls=2,
        max_external_core_calls=1,
        max_compute_units=100,
    )
    session = execution.ExecutionSession(
        session_id="execution-00000001",
        agent_id="coding.worker.01",
        task_id="task-5za",
        action_schema=("filesystem.write_text",),
        budget=budget,
        counters=ExecutionCounters(),
        step_index=0,
        state=execution.ExecutionState.RUNNING,
        backend_id="fixture-backend",
        checkpoint_digest="checkpoint-5za",
        workspace_base_revision="a" * 40,
    )
    assert execution.ExecutionSession.from_state(session.to_state()) == session

    step = execution.ExecutionStepReceipt.create(
        session_id=session.session_id,
        step_index=0,
        decision_receipt_id="decision-5za",
        core_receipt_id=None,
        before_workspace_digest="b" * 64,
        after_workspace_digest="c" * 64,
        state_after=execution.ExecutionState.RUNNING,
    )
    assert execution.ExecutionStepReceipt.from_state(step.to_state()) == step
    corrupt_step = step.to_state()
    corrupt_step["digest"] = "0" * 64
    with pytest.raises(ValueError, match="execution step receipt digest/id mismatch"):
        execution.ExecutionStepReceipt.from_state(corrupt_step)

    terminal_payload = {
        "session_id": session.session_id,
        "agent_id": session.agent_id,
        "task_id": session.task_id,
        "state": execution.ExecutionState.COMPLETED.value,
        "termination_reason": "verified completion",
        "steps": 1,
        "tool_calls": 0,
        "external_core_calls": 0,
        "compute_units": 1,
        "wall_clock_ms": 0,
        "decision_receipt_ids": ["decision-5za"],
        "step_receipt_ids": [step.receipt_id],
        "core_receipt_ids": [],
        "output_artifact_ids": ["artifact-5za"],
    }
    digest = canonical_digest(terminal_payload)
    terminal_state = {
        "receipt_id": "terminal-" + digest[:24],
        **terminal_payload,
        "digest": digest,
    }
    terminal = execution.ExecutionTerminalReceipt.from_state(terminal_state)
    assert terminal.to_state() == terminal_state
    corrupt_terminal = dict(terminal_state)
    corrupt_terminal["receipt_id"] = "terminal-" + "0" * 24
    with pytest.raises(ValueError, match="execution terminal receipt digest/id mismatch"):
        execution.ExecutionTerminalReceipt.from_state(corrupt_terminal)


def test_wave5za_execution_control_has_native_version_authority_and_no_facade() -> None:
    assert str(component_version("external.execution.control")) == "0.0.1"
    assert str(next_component_version("external.execution.control")) == "0.0.2"

    ledger = build_component_implementation_ledger()
    row = ledger["external.execution.control"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.execution"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert "cogcoder/organization/execution.py" in row.legacy_sources

    active = {binding.component_id for binding in build_active_facade_bindings()}
    assert "external.execution.control" not in active


def test_wave5za_generated_native_debt_retires_execution_control_only() -> None:
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {row["component_id"] for row in state["components"]}
    assert "external.execution.control" not in ids
    assert "external.coding.control" in ids
    assert "external.debugging" in ids
    assert len(state["components"]) <= 21


def test_wave5za_current_status_tracks_native_execution_control_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5ZA" in status
    assert "external.execution.control" in status
    assert "21 non-native" in status
