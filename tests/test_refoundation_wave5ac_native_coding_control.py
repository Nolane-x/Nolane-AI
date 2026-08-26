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
from nolane.core.canonical_digest import canonical_digest


_PUBLIC_SYMBOLS = (
    "PatchVerificationEvidence",
    "CodingReadinessReceipt",
    "CodingControlPlane",
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


def test_wave5ac_canonical_module_owns_coding_control_semantics() -> None:
    import nolane.external_core.coding as canonical

    assert canonical.COMPONENT_ID == "external.coding.control"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.coding"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.external_core.coding"


def test_wave5ac_historical_coding_objects_bridge_exact_canonical_identity() -> None:
    import cogcoder.organization.coding as legacy
    import nolane.external_core.coding as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ac_canonical_coding_control_imports_only_canonical_authorities() -> None:
    root = Path(__file__).resolve().parents[1]
    canonical_path = root / "nolane" / "external_core" / "coding.py"
    legacy_path = root / "cogcoder" / "organization" / "coding.py"
    canonical_source = canonical_path.read_text(encoding="utf-8")
    legacy_source = legacy_path.read_text(encoding="utf-8")
    imports = _imported_modules(canonical_source)

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    expected = {
        "nolane.core.canonical_digest",
        "nolane.external_core.architecture",
        "nolane.external_core.coding_claims",
        "nolane.external_core.coding_patches",
        "nolane.external_core.coding_profiles",
        "nolane.external_core.planning",
        "nolane.memory.skills",
        "nolane.organization.events",
        "nolane.organization.identity",
        "nolane.organization.tasks",
    }
    assert expected <= imports
    assert "nolane.external_core.coding" in legacy_source


def test_wave5ac_readiness_receipt_round_trip_and_digest_remain_fail_closed() -> None:
    from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence

    verification = PatchVerificationEvidence(
        evidence_id="evidence-5ac",
        verifier_agent_id="verification.testing.01",
        passed=True,
    )
    payload = {
        "receipt_id": "coding-ready-00000001",
        "patch_id": "patch-5ac",
        "ready": True,
        "reasons": [],
        "verification": verification.to_state(),
    }
    state = {**payload, "digest": canonical_digest(payload)}
    receipt = CodingReadinessReceipt.from_state(state)
    assert receipt.to_state() == state

    corrupt = dict(state)
    corrupt["digest"] = "0" * 64
    with pytest.raises(ValueError, match="coding readiness receipt digest mismatch"):
        CodingReadinessReceipt.from_state(corrupt)


def test_wave5ac_authority_version_facade_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["external.coding.control"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.coding"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.coding.control")) == "0.0.1"
    assert all(
        binding.component_id != "external.coding.control"
        for binding in build_active_facade_bindings()
    )

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "external.coding.control" not in ids
    # Wave 5AC established the 20-record ceiling. Downstream accepted native
    # cutovers may reduce debt further, but must never reintroduce this boundary.
    assert len(state["components"]) <= 20

    assert ledger["external.coding.claims"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["external.coding.patches"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["external.execution.control"].status is ImplementationStatus.CANONICAL_NATIVE


def test_wave5ac_current_status_tracks_native_coding_control_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AC" in status
    assert "external.coding.control" in status
    assert "20 non-native" in status
