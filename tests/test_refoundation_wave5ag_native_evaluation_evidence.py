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


_PUBLIC_SYMBOLS = (
    "EvaluationObservation",
    "MatchedBudgetComparison",
    "OrganizationSuperiorityAssessment",
    "AblationAssessment",
    "EvaluationEvidenceLedger",
)


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_wave5ag_canonical_module_owns_evaluation_evidence_authority() -> None:
    import nolane.evaluation.evidence as canonical

    assert canonical.COMPONENT_ID == "evaluation.evidence"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.evaluation_evidence"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.evaluation.evidence"


def test_wave5ag_historical_evidence_module_bridges_exact_canonical_identity() -> None:
    import cogcoder.organization.evaluation_evidence as legacy
    import nolane.evaluation.evidence as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ag_canonical_evidence_has_no_reverse_legacy_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "nolane" / "evaluation" / "evidence.py"
    imports = _imported_modules(path.read_text(encoding="utf-8"))

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    assert "nolane.organization.identity" in imports
    assert "nolane.external_core.evidence" in imports
    assert "nolane.core.canonical_digest" in imports
    assert "nolane.evaluation.regimes" in imports


def test_wave5ag_authority_version_facade_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["evaluation.evidence"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.evaluation.evidence"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("evaluation.evidence")) == "0.0.1"
    assert all(binding.component_id != "evaluation.evidence" for binding in build_active_facade_bindings())

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "evaluation.evidence" not in ids
    assert len(state["components"]) == 16


def test_wave5ag_current_status_tracks_native_evidence_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AG" in status
    assert "evaluation.evidence" in status
    assert "16 non-native" in status
