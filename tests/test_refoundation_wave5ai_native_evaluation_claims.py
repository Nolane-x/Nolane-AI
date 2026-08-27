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
from nolane.core.canonical_digest import canonical_digest


_PUBLIC_SYMBOLS = (
    "ClaimClass",
    "ClaimDisposition",
    "ClaimAssessment",
    "OrganizationReadinessReport",
    "ClaimBoundaryEngine",
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


def test_wave5ai_canonical_module_owns_evaluation_claims_authority() -> None:
    import nolane.evaluation.claims as canonical

    assert canonical.COMPONENT_ID == "evaluation.claims"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.evaluation_claims"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.evaluation.claims"


def test_wave5ai_historical_claims_module_bridges_exact_canonical_identity() -> None:
    import cogcoder.organization.evaluation_claims as legacy
    import nolane.evaluation.claims as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ai_canonical_claims_has_no_reverse_legacy_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "nolane" / "evaluation" / "claims.py"
    imports = _imported_modules(path.read_text(encoding="utf-8"))

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    assert "nolane.evaluation.evidence" in imports
    assert "nolane.evaluation.regimes" in imports
    assert "nolane.evaluation.stress" in imports
    assert "nolane.organization.identity" in imports
    assert "nolane.core.canonical_digest" in imports


def test_wave5ai_claim_assessment_and_readiness_state_roundtrip_behavior() -> None:
    from nolane.evaluation.claims import (
        ClaimAssessment,
        ClaimClass,
        ClaimDisposition,
        OrganizationReadinessReport,
    )

    claim_payload = {
        "claim_id": "wave5ai-claim",
        "claim_class": ClaimClass.INTERNAL_ENGINEERING_PROGRESS.value,
        "disposition": ClaimDisposition.LIMITED.value,
        "observation_ids": ["obs-a"],
        "comparison_ids": ["cmp-a"],
        "stress_assessment_id": None,
        "reproduction_receipt_id": None,
        "reasons": [],
        "limitations": ["internal_engineering_evidence_only"],
        "override_effective": False,
    }
    assessment = ClaimAssessment.from_state(
        {**claim_payload, "digest": canonical_digest(claim_payload)}
    )
    assert assessment.to_state() == {**claim_payload, "digest": canonical_digest(claim_payload)}

    readiness_payload = {
        "report_id": "wave5ai-readiness",
        "claim_assessment_ids": [assessment.claim_id],
        "gates": {"benchmark_coverage": True, "safety_cleanliness": False},
    }
    report = OrganizationReadinessReport.from_state(
        {**readiness_payload, "digest": canonical_digest(readiness_payload)}
    )
    assert report.to_state() == {**readiness_payload, "digest": canonical_digest(readiness_payload)}


def test_wave5ai_authority_version_facade_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["evaluation.claims"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.evaluation.claims"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("evaluation.claims")) == "0.0.1"
    assert all(binding.component_id != "evaluation.claims" for binding in build_active_facade_bindings())

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "evaluation.claims" not in ids
    assert len(state["components"]) == 14
