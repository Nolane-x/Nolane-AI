from __future__ import annotations

import ast
import json
from pathlib import Path

from cogcoder.refoundation.facades import build_active_facade_bindings, validate_active_facades
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger


_EXPECTED_INTENTIONAL_DEBT = {
    "external.capability_acquisition": "historical_only",
    "external.causal": "historical_only",
    "external.cognitive_library": "historical_only",
    "external.experimentation": "historical_only",
    "external.transfer_meta": "historical_only",
    "neural.shared": "frozen_asset",
}

_FINAL_NATIVE_CLOSURE_MODULES = (
    "nolane/external_core/operations.py",
    "nolane/external_core/operations_profiles.py",
    "nolane/external_core/data_operations.py",
    "nolane/external_core/infrastructure_operations.py",
    "nolane/external_core/reliability_operations.py",
    "nolane/external_core/research.py",
    "nolane/external_core/research_profiles.py",
    "nolane/external_core/research_provenance.py",
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_wave5ar_generated_debt_is_exactly_the_intentional_non_executable_set() -> None:
    state = json.loads((_root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    actual = {row["component_id"]: row["implementation_status"] for row in state["components"]}
    assert actual == _EXPECTED_INTENTIONAL_DEBT
    assert state["counts_by_status"] == {"frozen_asset": 1, "historical_only": 5}


def test_wave5ar_has_zero_active_or_legacy_executable_facades() -> None:
    assert build_active_facade_bindings() == ()
    report = validate_active_facades()
    assert report.binding_count == 0
    assert report.clean
    ledger = build_component_implementation_ledger()
    assert all(
        row.status not in {ImplementationStatus.COMPATIBILITY_FACADE, ImplementationStatus.LEGACY_INTERNAL}
        for row in ledger.values()
    )


def test_wave5ar_final_native_closures_never_reverse_import_legacy_organization_authority() -> None:
    root = _root()
    for relative in _FINAL_NATIVE_CLOSURE_MODULES:
        imports = _imports(root / relative)
        assert not any(module.startswith("cogcoder.organization") for module in imports), relative


def test_wave5ar_current_status_records_executable_debt_closure() -> None:
    status = (_root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AR" in status
    assert "zero active compatibility facade" in status.lower()
    assert "five historical semantic reservations" in status.lower()
    assert "neural.shared" in status
