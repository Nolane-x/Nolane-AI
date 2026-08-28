from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger

MODULES = {
    "assurance": ("AssuranceDisposition", "AssuranceDecision", "AssuranceControlPlane"),
    "assurance_evidence": ("AssuranceEvidence", "AssuranceEvidenceLedger"),
    "assurance_profiles": ("AssuranceDomain", "AssuranceProfileRegistry"),
}


def root() -> Path:
    return Path(__file__).resolve().parents[1]


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def test_wave5an_canonical_cluster_owns_public_objects_without_reverse_legacy_imports() -> None:
    main = importlib.import_module("nolane.external_core.assurance")
    assert main.COMPONENT_ID == "external.assurance"
    assert main.COMPONENT_VERSION == "0.0.1"
    for suffix, names in MODULES.items():
        path = root() / "nolane" / "external_core" / f"{suffix}.py"
        assert path.exists()
        module = importlib.import_module(f"nolane.external_core.{suffix}")
        assert not any(name.startswith("cogcoder.organization") for name in imports(path))
        legacy = importlib.import_module(f"cogcoder.organization.{suffix}")
        for name in names:
            assert getattr(module, name).__module__ == f"nolane.external_core.{suffix}"
            assert getattr(legacy, name) is getattr(module, name)


def test_wave5an_behavior_roundtrips_remain_exact() -> None:
    main = importlib.import_module("nolane.external_core.assurance")
    decision_payload = {
        "decision_id": "wave5an-decision",
        "subject_id": "wave5an-subject",
        "evidence_ids": ["evidence-a"],
        "disposition": "verified",
        "reasons": [],
        "blocking_receipt_id": None,
    }
    decision_state = {**decision_payload, "digest": main.canonical_digest(decision_payload)}
    decision = main.AssuranceDecision.from_state(decision_state)
    assert decision.to_state() == decision_state

    evidence = main.AssuranceEvidence(
        evidence_id="wave5an-evidence",
        subject_id="wave5an-subject",
        subject_version="v1",
        verifier_agent_id="verification.unit-property.01",
        domain=main.AssuranceDomain.UNIT_PROPERTY,
        passed=True,
        sandbox_digest="sandbox-wave5an",
        observed_epoch=7,
        evidence_refs=("ref-wave5an",),
    )
    assert main.AssuranceEvidence.from_state(evidence.to_state()) == evidence


def test_wave5an_authority_and_debt_cutover() -> None:
    row = build_component_implementation_ledger()["external.assurance"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.assurance"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.assurance")) == "0.0.1"
    assert all(binding.component_id != "external.assurance" for binding in build_active_facade_bindings())
    state = json.loads((root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    assert "external.assurance" not in {record["component_id"] for record in state["components"]}
    assert len(state["components"]) == 9


def test_wave5an_status_and_cleanup_receipt() -> None:
    status = (root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AN" in status
    assert "external.assurance" in status
    assert "9 non-native" in status
    assert not (root() / ".github" / "workflows" / "refoundation-wave5an-authority-carrier.yml").exists()
