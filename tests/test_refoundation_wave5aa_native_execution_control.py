from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT
from nolane.external_core.execution_types import ExecutionBudget, ExecutionCounters


_PUBLIC_SYMBOLS = (
    "ExecutionState",
    "ExecutionSession",
    "ExecutionStepReceipt",
    "ExecutionTerminalReceipt",
    "OrganizationExecutionControlPlane",
)


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
    return modules


def _session(*, session_id: str = "execution-00000001"):
    from nolane.external_core.execution import ExecutionSession, ExecutionState

    return ExecutionSession(
        session_id=session_id,
        agent_id="agent-1",
        task_id="task-1",
        action_schema=("filesystem.read_text",),
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=2,
            max_external_core_calls=1,
            max_compute_units=4,
        ),
        counters=ExecutionCounters(),
        step_index=0,
        state=ExecutionState.RUNNING,
        backend_id="fixture-v1",
        checkpoint_digest="checkpoint-v1",
        workspace_base_revision="base-v1",
    )


def test_wave5aa_canonical_module_owns_execution_control_semantics() -> None:
    import nolane.external_core.execution as canonical

    assert canonical.COMPONENT_ID == "external.execution.control"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.execution"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.external_core.execution"


def test_wave5aa_historical_execution_objects_bridge_exact_canonical_identity() -> None:
    import cogcoder.organization.execution as legacy
    import nolane.external_core.execution as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5aa_canonical_execution_control_imports_only_canonical_authorities() -> None:
    root = Path(__file__).resolve().parents[1]
    canonical_path = root / "nolane" / "external_core" / "execution.py"
    legacy_path = root / "cogcoder" / "organization" / "execution.py"
    canonical_source = canonical_path.read_text(encoding="utf-8")
    legacy_source = legacy_path.read_text(encoding="utf-8")
    imports = _imported_modules(canonical_source)

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    expected = {
        "nolane.core.canonical_digest",
        "nolane.external_core.artifacts",
        "nolane.external_core.execution_executor",
        "nolane.external_core.execution_types",
        "nolane.external_core.execution_workspace",
        "nolane.external_core.invokable",
        "nolane.neural.inference_bridge",
        "nolane.organization.identity",
        "nolane.organization.tasks",
        "nolane.schemas.identity",
    }
    assert expected <= imports
    assert "nolane.external_core.execution" in legacy_source


def test_wave5aa_session_and_receipt_round_trips_remain_exact_and_fail_closed() -> None:
    from nolane.external_core.execution import (
        ExecutionSession,
        ExecutionState,
        ExecutionStepReceipt,
        ExecutionTerminalReceipt,
    )

    session = _session()
    assert ExecutionSession.from_state(session.to_state()) == session

    step = ExecutionStepReceipt.create(
        session_id=session.session_id,
        step_index=0,
        decision_receipt_id="decision-1",
        core_receipt_id="core-1",
        before_workspace_digest="before",
        after_workspace_digest="after",
        state_after=ExecutionState.RUNNING,
        output_artifact_ids=("artifact-1",),
    )
    assert ExecutionStepReceipt.from_state(step.to_state()) == step
    corrupt_step = step.to_state()
    corrupt_step["digest"] = "0" * 64
    with pytest.raises(ValueError, match="execution step receipt digest/id mismatch"):
        ExecutionStepReceipt.from_state(corrupt_step)

    terminal_payload = {
        "session_id": session.session_id,
        "agent_id": session.agent_id,
        "task_id": session.task_id,
        "state": ExecutionState.FAILED.value,
        "termination_reason": "test",
        "steps": 1,
        "tool_calls": 0,
        "external_core_calls": 0,
        "compute_units": 1,
        "wall_clock_ms": 0,
        "decision_receipt_ids": ["decision-1"],
        "step_receipt_ids": [],
        "core_receipt_ids": [],
        "output_artifact_ids": [],
    }
    from nolane.core.canonical_digest import canonical_digest

    digest = canonical_digest(terminal_payload)
    terminal_state = {
        "receipt_id": "terminal-" + digest[:24],
        **terminal_payload,
        "digest": digest,
    }
    terminal = ExecutionTerminalReceipt.from_state(terminal_state)
    assert terminal.to_state() == terminal_state
    corrupt_terminal = dict(terminal_state)
    corrupt_terminal["receipt_id"] = "terminal-" + "f" * 24
    with pytest.raises(ValueError, match="execution terminal receipt digest/id mismatch"):
        ExecutionTerminalReceipt.from_state(corrupt_terminal)


def test_wave5aa_control_plane_state_validation_remains_fail_closed() -> None:
    from nolane.external_core.execution import OrganizationExecutionControlPlane
    from nolane.neural.inference_bridge import CognitiveStateEncoder

    with pytest.raises(ValueError, match="non-canonical execution session id"):
        OrganizationExecutionControlPlane(
            registry=object(),
            tasks=object(),
            context=object(),
            artifacts=object(),
            external_cores=object(),
            coding=object(),
            encoder=CognitiveStateEncoder(),
            executor=object(),
            sessions=(_session(session_id="not-canonical"),),
            session_counter=1,
        )

    with pytest.raises(ValueError, match="execution session counter is behind history"):
        OrganizationExecutionControlPlane(
            registry=object(),
            tasks=object(),
            context=object(),
            artifacts=object(),
            external_cores=object(),
            coding=object(),
            encoder=CognitiveStateEncoder(),
            executor=object(),
            sessions=(_session(session_id="execution-00000002"),),
            session_counter=1,
        )


def test_wave5aa_authority_version_facade_inventory_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["external.execution.control"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.execution"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.execution.control")) == "0.0.1"
    assert all(
        binding.component_id != "external.execution.control"
        for binding in build_active_facade_bindings()
    )

    census = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT).to_census()
    assert census.get("cogcoder/organization/execution.py").canonical_destination == "nolane/external_core/execution.py"

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "external.execution.control" not in ids
    assert len(state["components"]) <= 21

    assert ledger["neural.inference_bridge"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["neural.shared"].status is ImplementationStatus.FROZEN_ASSET


def test_wave5aa_current_status_tracks_native_execution_control_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AA" in status
    assert "external.execution.control" in status
    assert "21 non-native" in status
