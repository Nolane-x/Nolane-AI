from __future__ import annotations

import ast
import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


_MAIN_SYMBOLS = (
    "DebugPatchHandoff",
    "DebugResolutionReceipt",
    "DebugControlPlane",
)
_HELPER_SYMBOLS = {
    "debug_evidence": (
        "FailureClass",
        "DebugCaseStatus",
        "DebugEvidenceKind",
        "FailureCase",
        "ReproductionReceipt",
        "DebugEvidenceArtifact",
        "DebugEvidenceLedger",
    ),
    "debug_hypotheses": (
        "HypothesisStatus",
        "DebugHypothesis",
        "DebugHypothesisLedger",
    ),
    "debug_profiles": (
        "DebugDomain",
        "DebugProfile",
        "DebugWorkRequest",
        "DebugCandidateScore",
        "DebugAssignmentReceipt",
        "DebugProfileRegistry",
    ),
}


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_wave5ad_canonical_modules_own_entire_debugging_slice() -> None:
    import nolane.external_core.debugging as canonical

    assert canonical.COMPONENT_ID == "external.debugging"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.debugging"
    for name in _MAIN_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.external_core.debugging"

    for module_name, names in _HELPER_SYMBOLS.items():
        module = __import__(f"nolane.external_core.{module_name}", fromlist=["*"])
        for name in names:
            assert getattr(module, name).__module__ == f"nolane.external_core.{module_name}"


def test_wave5ad_historical_debugging_modules_bridge_exact_canonical_identity() -> None:
    import cogcoder.organization.debugging as legacy_main
    import nolane.external_core.debugging as canonical_main

    for name in _MAIN_SYMBOLS:
        assert getattr(legacy_main, name) is getattr(canonical_main, name)

    for module_name, names in _HELPER_SYMBOLS.items():
        legacy = __import__(f"cogcoder.organization.{module_name}", fromlist=["*"])
        canonical = __import__(f"nolane.external_core.{module_name}", fromlist=["*"])
        for name in names:
            assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ad_canonical_debugging_slice_has_no_reverse_legacy_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    for module_name in ("debugging", *_HELPER_SYMBOLS):
        path = root / "nolane" / "external_core" / f"{module_name}.py"
        imports = _imported_modules(path.read_text(encoding="utf-8"))
        assert not any(module.startswith("cogcoder.organization") for module in imports)

    main_imports = _imported_modules(
        (root / "nolane" / "external_core" / "debugging.py").read_text(encoding="utf-8")
    )
    assert {
        "nolane.core.canonical_digest",
        "nolane.external_core.coding",
        "nolane.external_core.coding_profiles",
        "nolane.external_core.debug_evidence",
        "nolane.external_core.debug_hypotheses",
        "nolane.external_core.debug_profiles",
        "nolane.memory.skills",
        "nolane.organization.events",
        "nolane.organization.identity",
        "nolane.organization.tasks",
    } <= main_imports


def test_wave5ad_authority_version_facade_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["external.debugging"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.debugging"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.debugging")) == "0.0.1"
    assert all(binding.component_id != "external.debugging" for binding in build_active_facade_bindings())

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "external.debugging" not in ids
    assert len(state["components"]) == 19

    assert ledger["external.coding.control"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["external.evidence"].status is ImplementationStatus.CANONICAL_NATIVE


def test_wave5ad_current_status_tracks_native_debugging_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AD" in status
    assert "external.debugging" in status
    assert "19 non-native" in status
