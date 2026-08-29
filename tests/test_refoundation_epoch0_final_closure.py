from __future__ import annotations

from pathlib import Path

from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.repository.audit import build_native_debt, stale_paths


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FROZEN_COMPONENT = "neural.shared"
EXPECTED_FROZEN_PROVENANCE = ("model/neural-r2.3",)
CLOSURE_HEADING = "# Epoch 0 — final closure"


def test_epoch0_has_no_historical_or_non_native_executable_authority() -> None:
    ledger = build_component_implementation_ledger()

    historical = {
        component_id
        for component_id, row in ledger.items()
        if row.status is ImplementationStatus.HISTORICAL_ONLY
    }
    assert historical == set()

    writers = {
        component_id
        for component_id, row in ledger.items()
        if row.canonical_write_authority
    }
    native = {
        component_id
        for component_id, row in ledger.items()
        if row.status is ImplementationStatus.CANONICAL_NATIVE
    }
    assert writers == native

    non_native = {
        component_id: row
        for component_id, row in ledger.items()
        if row.status is not ImplementationStatus.CANONICAL_NATIVE
    }
    assert set(non_native) == {EXPECTED_FROZEN_COMPONENT}

    frozen = non_native[EXPECTED_FROZEN_COMPONENT]
    assert frozen.status is ImplementationStatus.FROZEN_ASSET
    assert frozen.canonical_module is None
    assert frozen.canonical_write_authority is False
    assert frozen.component_version == "0.0.0"
    assert frozen.legacy_sources == EXPECTED_FROZEN_PROVENANCE


def test_epoch0_native_debt_projection_is_exact_terminal_state_and_fresh() -> None:
    debt = build_native_debt()
    assert debt["counts_by_status"] == {"frozen_asset": 1}
    assert len(debt["components"]) == 1

    frozen = debt["components"][0]
    assert frozen["component_id"] == EXPECTED_FROZEN_COMPONENT
    assert frozen["implementation_status"] == "frozen_asset"
    assert frozen["canonical_module"] is None
    assert frozen["canonical_write_authority"] is False
    assert frozen["component_version"] == "0.0.0"
    assert frozen["legacy_sources"] == list(EXPECTED_FROZEN_PROVENANCE)

    assert stale_paths(source_root=ROOT, output_root=ROOT) == ()


def test_epoch0_closure_is_explicit_without_overclaiming_frozen_neural_authority() -> None:
    status = (ROOT / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "## Wave 5AY — Native transfer/meta authority" in status
    assert "`historical_only` debt reaches zero" in status

    closure = (ROOT / "CURRENT" / "EPOCH0_CLOSURE.md").read_text(encoding="utf-8")
    assert CLOSURE_HEADING in closure
    assert "`historical_only` debt is zero" in closure
    assert "`neural.shared` remains `frozen_asset`" in closure
    assert "not executable migration debt" in closure
    assert "does not grant canonical write authority" in closure
    assert "Epoch 0 is closed" in closure
    assert "No later extraction wave is required" in closure


def test_epoch0_closure_contract_runs_in_the_supported_refoundation_matrix() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "refoundation-epoch0-wave1.yml"
    ).read_text(encoding="utf-8")
    assert "python-version: ['3.11', '3.13']" in workflow
    assert "python -m nolane.repository.audit --check" in workflow
    assert "python -m pytest -q tests/test_refoundation_*.py" in workflow
    assert "python model/neural-r2.3/scripts/verify_neural_r23.py" in workflow
    assert "Upload Refoundation Epoch 0 generated audit snapshot" in workflow
    assert "refoundation-epoch0-audit-py${{ matrix.python-version }}" in workflow
    assert "Wave 5O" not in workflow
    assert "refoundation-wave5o-audit" not in workflow


def test_epoch0_closed_main_has_no_wave_specific_carrier_workflows() -> None:
    workflows = ROOT / ".github" / "workflows"
    residue = tuple(sorted(path.name for path in workflows.glob("refoundation-wave*.yml")))
    assert residue == ()
