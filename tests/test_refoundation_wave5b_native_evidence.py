from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


ROOT = Path(__file__).resolve().parents[1]


def test_wave5b_external_evidence_is_canonical_native_and_versioned() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["external.evidence"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.evidence"
    assert row.canonical_write_authority is True
    assert row.component_version == "0.0.1"
    assert str(component_version("external.evidence")) == "0.0.1"


def test_wave5b_legacy_evidence_imports_bridge_to_canonical_class_identity() -> None:
    from cogcoder.organization import EvidenceRecord as PackageEvidenceRecord
    from cogcoder.organization.types import EvidenceRecord as LegacyEvidenceRecord
    from nolane.external_core.evidence import EvidenceRecord

    assert PackageEvidenceRecord is EvidenceRecord
    assert LegacyEvidenceRecord is EvidenceRecord
    assert EvidenceRecord.__module__ == "nolane.external_core.evidence"


def test_wave5b_canonical_evidence_has_no_reverse_import_to_historical_owner() -> None:
    import nolane.external_core.evidence as evidence

    source = inspect.getsource(evidence)
    assert "from cogcoder.organization.types import" not in source
    assert "import cogcoder.organization.types" not in source


def test_wave5b_evidence_record_preserves_validation_and_state_round_trip() -> None:
    from nolane.external_core.evidence import EvidenceRecord

    row = EvidenceRecord(
        evidence_id="evidence-0001",
        verifier_agent_id="verification.chief",
        passed=True,
        false_accepts=0,
        regressions=0,
        notes="bounded verification passed",
    )
    assert row.to_state() == {
        "evidence_id": "evidence-0001",
        "verifier_agent_id": "verification.chief",
        "passed": True,
        "false_accepts": 0,
        "regressions": 0,
        "notes": "bounded verification passed",
    }
    assert EvidenceRecord.from_state(row.to_state()) == row

    with pytest.raises(ValueError, match="evidence counters must be non-negative"):
        EvidenceRecord("evidence-neg", "verification.chief", False, false_accepts=-1)
    with pytest.raises(ValueError, match="evidence identity must be explicit"):
        EvidenceRecord("", "verification.chief", False)


def test_wave5b_evidence_remains_out_of_native_debt_after_later_waves() -> None:
    ledger = build_component_implementation_ledger()
    non_native_ids = {
        component_id
        for component_id, row in ledger.items()
        if row.status is not ImplementationStatus.CANONICAL_NATIVE
    }

    assert "external.evidence" not in non_native_ids
    assert ledger["external.evidence"].canonical_write_authority

    # These boundaries were intentionally left for later extraction in Wave 5B
    # and unrelated migrations must not silently promote them.
    assert ledger["core.canonical_digest"].status is ImplementationStatus.LEGACY_INTERNAL
    assert ledger["schemas.identity"].status is ImplementationStatus.LEGACY_INTERNAL
    assert ledger["external.coding.claims"].status is ImplementationStatus.LEGACY_INTERNAL
    assert ledger["external.coding.patches"].status is ImplementationStatus.LEGACY_INTERNAL


def test_wave5b_acceptance_has_no_write_enabled_bootstrap_workflow() -> None:
    bootstrap = ROOT / ".github" / "workflows" / "refoundation-wave5b-bootstrap.yml"
    assert not bootstrap.exists(), "temporary write-enabled Wave-5B bootstrap must be removed before acceptance"
