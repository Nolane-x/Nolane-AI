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


_BASE_SYMBOLS = ("ContextCapsule", "ContextCompiler")
_INTELLIGENCE_SYMBOLS = (
    "ContextBudget",
    "ContextDeltaKind",
    "SemanticContextDeltaItem",
    "SemanticContextDelta",
    "ContinuityCheckpoint",
    "ContextCompilationReceipt",
    "ContextCompilationResult",
    "ContextIntelligenceCompiler",
)
_PROFILE_SYMBOLS = (
    "MemoryIntelligenceDomain",
    "MemoryIntelligenceProfile",
    "MemoryWorkRequest",
    "MemoryCandidateScore",
    "MemoryAssignmentReceipt",
    "MemoryIntelligenceProfileRegistry",
)
_CONTROL_SYMBOLS = ("MemoryRepairReceipt", "MemoryContextControlPlane")
_ADAPTER_SYMBOLS = ("MemoryAwareContextCompiler",)

_CANONICAL_OWNERS = {
    "nolane.external_core.context": _BASE_SYMBOLS,
    "nolane.memory.context_intelligence": _INTELLIGENCE_SYMBOLS,
    "nolane.memory.context_profiles": _PROFILE_SYMBOLS,
    "nolane.memory.context": _CONTROL_SYMBOLS,
    "nolane.memory.context_adapter": _ADAPTER_SYMBOLS,
}

_HISTORICAL_BRIDGES = {
    "cogcoder.organization.context": ("nolane.external_core.context", ("ContextCapsule", "ContextCompiler")),
    "cogcoder.organization.context_intelligence": ("nolane.memory.context_intelligence", _INTELLIGENCE_SYMBOLS),
    "cogcoder.organization.memory_profiles": ("nolane.memory.context_profiles", _PROFILE_SYMBOLS),
    "cogcoder.organization.memory_context": ("nolane.memory.context", _CONTROL_SYMBOLS),
    "cogcoder.organization.memory_context_adapter": ("nolane.memory.context_adapter", _ADAPTER_SYMBOLS),
}

_FORBIDDEN_HISTORICAL_MODULES = {
    "cogcoder.organization.context",
    "cogcoder.organization.context_intelligence",
    "cogcoder.organization.memory_profiles",
    "cogcoder.organization.memory_context",
    "cogcoder.organization.memory_context_adapter",
}


def test_wave5y_canonical_context_layers_own_semantic_public_implementation() -> None:
    failures: list[str] = []
    for module_name, symbols in _CANONICAL_OWNERS.items():
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            failures.append(f"missing canonical module {module_name}: {exc}")
            continue
        for name in symbols:
            value = getattr(module, name, None)
            if value is None:
                failures.append(f"{module_name} missing {name}")
            elif value.__module__ != module_name:
                failures.append(f"{module_name}.{name} owned by {value.__module__}")
    assert failures == [], "; ".join(failures)


def test_wave5y_historical_context_modules_are_exact_public_object_bridges() -> None:
    failures: list[str] = []
    for legacy_name, (canonical_name, symbols) in _HISTORICAL_BRIDGES.items():
        legacy = importlib.import_module(legacy_name)
        try:
            canonical = importlib.import_module(canonical_name)
        except ModuleNotFoundError as exc:
            failures.append(f"missing canonical module {canonical_name}: {exc}")
            continue
        for name in symbols:
            if not hasattr(legacy, name):
                failures.append(f"{legacy_name} missing historical public symbol {name}")
            elif not hasattr(canonical, name):
                failures.append(f"{canonical_name} missing canonical public symbol {name}")
            elif getattr(legacy, name) is not getattr(canonical, name):
                failures.append(f"{legacy_name}.{name} is not exact canonical object")
    assert failures == [], "; ".join(failures)


def test_wave5y_canonical_context_tree_has_no_reverse_historical_authority() -> None:
    root = Path(__file__).resolve().parents[1]
    expected_paths = (
        root / "nolane" / "external_core" / "context.py",
        root / "nolane" / "memory" / "context_intelligence.py",
        root / "nolane" / "memory" / "context_profiles.py",
        root / "nolane" / "memory" / "context.py",
        root / "nolane" / "memory" / "context_adapter.py",
    )
    missing = [path.relative_to(root).as_posix() for path in expected_paths if not path.exists()]
    offenders: list[str] = []
    for source_path in expected_paths:
        if not source_path.exists():
            continue
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        relative = source_path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in _FORBIDDEN_HISTORICAL_MODULES or alias.name.startswith("cogcoder.organization"):
                        offenders.append(f"{relative}:{node.lineno}:import:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in _FORBIDDEN_HISTORICAL_MODULES or module.startswith("cogcoder.organization"):
                    offenders.append(f"{relative}:{node.lineno}:from:{module}")
    assert missing == [], "missing canonical context modules: " + ", ".join(missing)
    assert offenders == [], "canonical context authority reverse-imports historical organization code: " + "; ".join(offenders)


def test_wave5y_context_primitives_preserve_validation_and_fail_closed_digests() -> None:
    intelligence = importlib.import_module("nolane.memory.context_intelligence")
    control = importlib.import_module("nolane.memory.context")
    profiles = importlib.import_module("nolane.memory.context_profiles")

    with pytest.raises(ValueError, match="context budget values must be positive"):
        intelligence.ContextBudget(0, 1, 1)

    delta_payload = {
        "agent_id": "memory.context-compiler.01",
        "task_id": "task-5y",
        "checkpoint_id": None,
        "items": [],
    }
    delta_digest = canonical_digest(delta_payload)
    delta_state = {
        "delta_id": "context-delta-" + delta_digest[:20],
        **delta_payload,
        "digest": delta_digest,
    }
    delta = intelligence.SemanticContextDelta.from_state(delta_state)
    assert delta.to_state() == delta_state
    corrupt_delta = dict(delta_state)
    corrupt_delta["digest"] = "0" * 64
    with pytest.raises(ValueError, match="semantic context delta digest mismatch"):
        intelligence.SemanticContextDelta.from_state(corrupt_delta)

    repair_payload = {
        "repair_id": "memory-repair-00000001",
        "chief_agent_id": "memory.chief",
        "rejected_memory_ids": ["mem-00000001"],
        "corrected_memory_id": "mem-00000002",
        "affected_agent_id": "memory.context-compiler.01",
        "lifecycle_receipt_ids": ["memory-lifecycle-00000001"],
        "context_compilation_receipt_id": "context-compilation-00000001",
        "selected_memory_ids": ["mem-00000002"],
        "reason": "replace contradicted memory",
        "evidence_refs": ["EV-5Y"],
    }
    repair_state = {**repair_payload, "digest": canonical_digest(repair_payload)}
    repair = control.MemoryRepairReceipt.from_state(repair_state)
    assert repair.to_state() == repair_state
    corrupt_repair = dict(repair_state)
    corrupt_repair["digest"] = "f" * 64
    with pytest.raises(ValueError, match="memory repair receipt digest mismatch"):
        control.MemoryRepairReceipt.from_state(corrupt_repair)

    domain = profiles.MemoryIntelligenceDomain.CONTEXT_COMPILATION
    request = profiles.MemoryWorkRequest(
        work_id="work-5y",
        object_id="task-5y",
        requested_domains=(domain,),
        scope_hints=("context",),
        priority=50,
        requester_agent_id="memory.chief",
        evidence_refs=("EV-5Y",),
    )
    assert request.to_state()["requested_domains"] == ["context_compilation"]
    with pytest.raises(ValueError, match="requires evidence refs"):
        profiles.MemoryWorkRequest(
            work_id="work-bad",
            object_id="task-5y",
            requested_domains=(domain,),
            scope_hints=(),
            priority=50,
            requester_agent_id="memory.chief",
            evidence_refs=(),
        )


def test_wave5y_context_component_has_native_version_authority_and_no_facade() -> None:
    assert str(component_version("external.context")) == "0.0.1"
    assert str(next_component_version("external.context")) == "0.0.2"

    ledger = build_component_implementation_ledger()
    row = ledger["external.context"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.memory.context"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    expected_sources = {
        "cogcoder/organization/context.py",
        "cogcoder/organization/context_intelligence.py",
        "cogcoder/organization/memory_profiles.py",
        "cogcoder/organization/memory_context.py",
        "cogcoder/organization/memory_context_adapter.py",
    }
    assert expected_sources <= set(row.legacy_sources)

    active = {binding.component_id for binding in build_active_facade_bindings()}
    assert "external.context" not in active


def test_wave5y_generated_native_debt_remains_monotonic_after_later_cutovers() -> None:
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {row["component_id"] for row in state["components"]}
    assert "external.context" not in ids
    assert "external.execution.control" in ids
    assert len(state["components"]) <= 23


def test_wave5y_current_status_tracks_native_context_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5Y" in status
    assert "external.context" in status
    assert "23 non-native" in status
