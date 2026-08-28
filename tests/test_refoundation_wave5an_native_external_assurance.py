from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


_MODULE_OBJECTS = {
    "assurance": (
        "AssuranceDisposition",
        "AssurancePolicy",
        "BlockingReceipt",
        "AssuranceDecision",
        "AssuranceOverrideReceipt",
        "PromotionAssuranceReceipt",
        "AssuranceControlPlane",
    ),
    "assurance_evidence": (
        "ChallengeStatus",
        "AssuranceSubject",
        "ChallengeCase",
        "AssuranceEvidence",
        "AssuranceEvidenceLedger",
    ),
    "assurance_profiles": (
        "AssuranceDomain",
        "AssuranceProfile",
        "AssuranceWorkRequest",
        "AssuranceCandidateScore",
        "AssuranceAssignmentReceipt",
        "AssuranceProfileRegistry",
    ),
}


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


def test_wave5an_canonical_assurance_cluster_owns_public_authority() -> None:
    root = _root()
    canonical = importlib.import_module("nolane.external_core.assurance")
    assert canonical.COMPONENT_ID == "external.assurance"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.assurance"

    for suffix, names in _MODULE_OBJECTS.items():
        path = root / "nolane" / "external_core" / f"{suffix}.py"
        assert path.exists(), f"missing canonical assurance module: {suffix}"
        module = importlib.import_module(f"nolane.external_core.{suffix}")
        for name in names:
            assert getattr(module, name).__module__ == f"nolane.external_core.{suffix}"


def test_wave5an_historical_assurance_cluster_is_exact_identity_bridge() -> None:
    for suffix, names in _MODULE_OBJECTS.items():
        canonical = importlib.import_module(f"nolane.external_core.{suffix}")
        legacy = importlib.import_module(f"cogcoder.organization.{suffix}")
        for name in names:
            assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5an_canonical_assurance_cluster_has_no_reverse_legacy_imports() -> None:
    root = _root()
    for suffix in _MODULE_OBJECTS:
        path = root / "nolane" / "external_core" / f"{suffix}.py"
        assert path.exists(), f"missing canonical assurance module: {suffix}"
        imports = _imports(path)
        assert not any(module.startswith("cogcoder.organization") for module in imports)

    assurance_imports = _imports(root / "nolane" / "external_core" / "assurance.py")
    assert "nolane.external_core.assurance_evidence" in assurance_imports
    assert "nolane.external_core.assurance_profiles" in assurance_imports
    assert "nolane.external_core.artifacts" in assurance_imports
    assert "nolane.organization.authority" in assurance_imports
    assert "nolane.organization.events" in assurance_imports
    assert "nolane.memory.skills" in assurance_imports
    assert "nolane.organization.identity" in assurance_imports
    assert "nolane.core.canonical_digest" in assurance_imports
    assert "nolane.external_core.verification" in assurance_imports


def test_wave5an_assurance_evidence_digest_and_state_roundtrip_remain_stable() -> None:
    legacy = importlib.import_module("cogcoder.organization.assurance_evidence")
    profiles = importlib.import_module("cogcoder.organization.assurance_profiles")
    row = legacy.AssuranceEvidence(
        evidence_id="wave5an-evidence",
        subject_id="wave5an-subject",
        subject_version="v1",
        verifier_agent_id="verification.unit-property.01",
        domain=profiles.AssuranceDomain.UNIT_PROPERTY,
        passed=True,
        sandbox_digest="sandbox-wave5an",
        observed_epoch=3,
        false_accepts=0,
        regressions=0,
        heldout_digest="heldout-wave5an",
        cross_version_refs=("v0",),
        challenge_case_refs=("case-1",),
        evidence_refs=("receipt-1",),
    )
    state = row.to_state()
    restored = legacy.AssuranceEvidence.from_state(state)
    assert restored == row
    assert restored.to_state() == state
    assert restored.digest == row.digest


def test_wave5an_assurance_authority_version_facade_and_debt_cutover() -> None:
    row = build_component_implementation_ledger()["external.assurance"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.assurance"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.assurance")) == "0.0.1"
    assert all(binding.component_id != "external.assurance" for binding in build_active_facade_bindings())

    state = json.loads((_root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "external.assurance" not in ids
    assert len(state["components"]) == 9


def test_wave5an_current_status_tracks_native_assurance_cutover() -> None:
    status = (_root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AN" in status
    assert "external.assurance" in status
    assert "9 non-native" in status


def test_wave5an_temporary_authority_carrier_is_absent_from_accepted_tree() -> None:
    root = _root()
    assert not (root / ".github" / "workflows" / "refoundation-wave5an-authority-carrier.yml").exists()
    assert not (root / "docs" / "superpowers" / "plans" / ".wave5an-carrier-trigger").exists()
