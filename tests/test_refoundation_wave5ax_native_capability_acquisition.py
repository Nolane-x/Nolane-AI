from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane, PromotionAssuranceReceipt
from nolane.external_core.cognitive_catalog import OperatorFamilyDescriptor, SubOperatorDescriptor
from nolane.external_core.cognitive_library import CognitiveLibrary


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


def _native():
    return importlib.import_module("nolane.external_core.capability_acquisition")


def _family(*, summary: str = "A candidate operator family") -> OperatorFamilyDescriptor:
    return OperatorFamilyDescriptor(
        "wave5ax_candidate",
        summary,
        (
            SubOperatorDescriptor(
                "wave5ax_candidate.probe",
                "experimental",
                "Probe a candidate capability without granting authority.",
                frozenset({"wave5ax", "probation"}),
            ),
        ),
    )


def _promotion_receipt(
    *,
    receipt_id: str,
    candidate_id: str,
    evidence_ids: tuple[str, ...],
    predecessor_version: str,
    authorized: bool = True,
) -> PromotionAssuranceReceipt:
    payload = {
        "receipt_id": receipt_id,
        "subject_id": candidate_id,
        "evidence_ids": list(evidence_ids),
        "predecessor_version": predecessor_version,
        "verifier_ids": ["verification.chief"],
        "authorized": authorized,
        "reasons": [] if authorized else ["rejected"],
    }
    return PromotionAssuranceReceipt(
        receipt_id=receipt_id,
        subject_id=candidate_id,
        evidence_ids=evidence_ids,
        predecessor_version=predecessor_version,
        verifier_ids=("verification.chief",),
        authorized=authorized,
        reasons=() if authorized else ("rejected",),
        digest=canonical_digest(payload),
    )


def _assurance_plane(*receipts: PromotionAssuranceReceipt) -> AssuranceControlPlane:
    plane = object.__new__(AssuranceControlPlane)
    plane._promotion_receipts = {row.receipt_id: row for row in receipts}
    return plane


def _ready(native, *, library: CognitiveLibrary | None = None, display_name: str = "candidate"):
    library = library or CognitiveLibrary()
    governor = native.CapabilityAcquisitionGovernor(library)
    candidate = native.CapabilityCandidate.for_operator_family(_family(), display_name=display_name)
    governor.admit(candidate)
    governor.begin_probation(candidate.candidate_id)
    evidence_ids = ("independent:e1", "challenge:e2")
    governor.record_probation(
        candidate.candidate_id,
        evidence_ids=evidence_ids,
        independent_passed=True,
        challenge_passed=True,
        reliability=0.95,
    )
    return library, governor, candidate, evidence_ids


def test_wave5ax_native_capability_acquisition_public_boundary_and_no_reverse_imports() -> None:
    native = _native()
    assert native.COMPONENT_ID == "external.capability_acquisition"
    assert native.COMPONENT_VERSION == "0.0.1"
    assert native.MIGRATED_FROM == "cogcoder R2.55 hardened capability-acquisition lineage"
    for name in (
        "CapabilityKind",
        "CapabilityState",
        "CapabilityCandidate",
        "CapabilityRecord",
        "CapabilityAcquisitionGovernor",
    ):
        assert hasattr(native, name), name

    imports = _imports(_root() / "nolane" / "external_core" / "capability_acquisition.py")
    assert not any(name.startswith("cogcoder.r") for name in imports)
    assert not any(name.startswith("cogcoder.organization") for name in imports)
    assert not any(name.startswith("research") or name.startswith("ai") for name in imports)


def test_wave5ax_candidate_identity_is_content_addressed_rename_stable_and_duplicate_safe() -> None:
    native = _native()
    first = native.CapabilityCandidate.for_operator_family(_family(), display_name="human label A")
    renamed = native.CapabilityCandidate.for_operator_family(_family(), display_name="human label B")
    changed = native.CapabilityCandidate.for_operator_family(
        _family(summary="Semantically changed candidate"),
        display_name="human label A",
    )
    assert first.candidate_id == renamed.candidate_id
    assert first.semantic_state() == renamed.semantic_state()
    assert first.candidate_id != changed.candidate_id

    governor = native.CapabilityAcquisitionGovernor(CognitiveLibrary())
    governor.admit(first)
    with pytest.raises(ValueError, match="duplicate"):
        governor.admit(renamed)


def test_wave5ax_probation_failures_quarantine_without_mutating_library() -> None:
    native = _native()
    library = CognitiveLibrary()
    baseline = library.digest
    governor = native.CapabilityAcquisitionGovernor(library)
    candidate = native.CapabilityCandidate.for_operator_family(_family())
    admitted = governor.admit(candidate)
    assert admitted.state is native.CapabilityState.CANDIDATE
    probation = governor.begin_probation(candidate.candidate_id)
    assert probation.state is native.CapabilityState.PROBATION

    quarantined = governor.record_probation(
        candidate.candidate_id,
        evidence_ids=("independent:failed", "challenge:failed"),
        independent_passed=False,
        challenge_passed=False,
        reliability=0.10,
    )
    assert quarantined.state is native.CapabilityState.QUARANTINED
    assert library.digest == baseline
    assert governor.retrievable_ids() == ()
    with pytest.raises(PermissionError):
        governor.retrieve(candidate.candidate_id)
    with pytest.raises(ValueError, match="quarantined"):
        governor.begin_probation(candidate.candidate_id)


def test_wave5ax_promotion_requires_exact_persisted_assurance_receipt_and_evidence_binding() -> None:
    native = _native()
    library, governor, candidate, evidence_ids = _ready(native)
    baseline = library.digest

    forged = _promotion_receipt(
        receipt_id="assurance-promotion-forged",
        candidate_id=candidate.candidate_id,
        evidence_ids=evidence_ids,
        predecessor_version=baseline,
    )
    with pytest.raises(ValueError, match="persisted assurance"):
        governor.promote(candidate.candidate_id, assurance=_assurance_plane(), receipt=forged)
    assert library.digest == baseline

    wrong_subject = _promotion_receipt(
        receipt_id="assurance-promotion-wrong-subject",
        candidate_id="capability:some-other-candidate",
        evidence_ids=evidence_ids,
        predecessor_version=baseline,
    )
    with pytest.raises(ValueError, match="subject"):
        governor.promote(
            candidate.candidate_id,
            assurance=_assurance_plane(wrong_subject),
            receipt=wrong_subject,
        )
    assert library.digest == baseline

    wrong_evidence = _promotion_receipt(
        receipt_id="assurance-promotion-wrong-evidence",
        candidate_id=candidate.candidate_id,
        evidence_ids=("independent:other", "challenge:other"),
        predecessor_version=baseline,
    )
    with pytest.raises(ValueError, match="evidence"):
        governor.promote(
            candidate.candidate_id,
            assurance=_assurance_plane(wrong_evidence),
            receipt=wrong_evidence,
        )
    assert library.digest == baseline

    accepted = _promotion_receipt(
        receipt_id="assurance-promotion-accepted",
        candidate_id=candidate.candidate_id,
        evidence_ids=evidence_ids,
        predecessor_version=baseline,
    )
    promoted = governor.promote(
        candidate.candidate_id,
        assurance=_assurance_plane(accepted),
        receipt=accepted,
    )
    assert promoted.state is native.CapabilityState.PROMOTED
    assert governor.retrievable_ids() == (candidate.candidate_id,)
    assert governor.retrieve(candidate.candidate_id) == _family()
    assert library.family("wave5ax_candidate") == _family()


def test_wave5ax_library_baseline_drift_and_unauthorized_receipts_fail_closed() -> None:
    native = _native()
    library, governor, candidate, evidence_ids = _ready(native)
    probation_baseline = library.digest

    drift_family = OperatorFamilyDescriptor(
        "wave5ax_drift",
        "Unrelated library drift",
        (
            SubOperatorDescriptor(
                "wave5ax_drift.other",
                "experimental",
                "An unrelated mutation after probation started.",
                frozenset({"wave5ax", "drift"}),
            ),
        ),
    )
    library.register_family(drift_family)
    drifted = _promotion_receipt(
        receipt_id="assurance-promotion-drifted",
        candidate_id=candidate.candidate_id,
        evidence_ids=evidence_ids,
        predecessor_version=probation_baseline,
    )
    with pytest.raises(ValueError, match="baseline"):
        governor.promote(
            candidate.candidate_id,
            assurance=_assurance_plane(drifted),
            receipt=drifted,
        )
    with pytest.raises(KeyError):
        library.family("wave5ax_candidate")

    clean_library, clean_governor, clean_candidate, clean_evidence = _ready(native)
    rejected = _promotion_receipt(
        receipt_id="assurance-promotion-rejected",
        candidate_id=clean_candidate.candidate_id,
        evidence_ids=clean_evidence,
        predecessor_version=clean_library.digest,
        authorized=False,
    )
    with pytest.raises(ValueError, match="authorized"):
        clean_governor.promote(
            clean_candidate.candidate_id,
            assurance=_assurance_plane(rejected),
            receipt=rejected,
        )
    with pytest.raises(KeyError):
        clean_library.family("wave5ax_candidate")


def test_wave5ax_retrieval_firewall_revokes_promoted_capability_after_live_failure() -> None:
    native = _native()
    library, governor, candidate, evidence_ids = _ready(native)
    receipt = _promotion_receipt(
        receipt_id="assurance-promotion-live",
        candidate_id=candidate.candidate_id,
        evidence_ids=evidence_ids,
        predecessor_version=library.digest,
    )
    governor.promote(candidate.candidate_id, assurance=_assurance_plane(receipt), receipt=receipt)
    assert governor.retrieve(candidate.candidate_id) == _family()

    revoked = governor.report_live_failure(candidate.candidate_id, reason="post-promotion regression")
    assert revoked.state is native.CapabilityState.QUARANTINED
    assert governor.retrievable_ids() == ()
    with pytest.raises(PermissionError):
        governor.retrieve(candidate.candidate_id)
    # CognitiveLibrary is append-only; the acquisition firewall is therefore the
    # authority boundary that makes the rolled-back capability non-actionable.
    assert library.family("wave5ax_candidate") == _family()


def test_wave5ax_snapshot_roundtrip_is_deterministic_and_rejects_tampering() -> None:
    native = _native()
    library, governor, candidate, evidence_ids = _ready(native, display_name="rename excluded from identity")
    receipt = _promotion_receipt(
        receipt_id="assurance-promotion-snapshot",
        candidate_id=candidate.candidate_id,
        evidence_ids=evidence_ids,
        predecessor_version=library.digest,
    )
    governor.promote(candidate.candidate_id, assurance=_assurance_plane(receipt), receipt=receipt)

    state = governor.to_state()
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    restored_library = CognitiveLibrary.from_state(json.loads(json.dumps(library.to_state())))
    restored = native.CapabilityAcquisitionGovernor.from_state(json.loads(encoded), library=restored_library)
    assert json.dumps(
        restored.to_state(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ) == encoded
    assert restored.digest == governor.digest
    assert restored.retrievable_ids() == (candidate.candidate_id,)

    corrupt_schema = json.loads(encoded)
    corrupt_schema["schema_version"] = "capability-acquisition-v999"
    with pytest.raises(ValueError, match="schema"):
        native.CapabilityAcquisitionGovernor.from_state(corrupt_schema, library=restored_library)

    corrupt_component = json.loads(encoded)
    corrupt_component["component_id"] = "external.not-capability-acquisition"
    with pytest.raises(ValueError, match="component"):
        native.CapabilityAcquisitionGovernor.from_state(corrupt_component, library=restored_library)

    corrupt_id = json.loads(encoded)
    corrupt_id["records"][0]["candidate"]["candidate_id"] = "capability:tampered"
    with pytest.raises(ValueError, match="candidate.*identity|identity.*candidate"):
        native.CapabilityAcquisitionGovernor.from_state(corrupt_id, library=restored_library)


def test_wave5ax_authority_version_and_debt_cutover() -> None:
    row = build_component_implementation_ledger()["external.capability_acquisition"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.capability_acquisition"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.capability_acquisition")) == "0.0.1"
    assert any("r255" in source for source in row.legacy_sources)

    debt = json.loads((_root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in debt["components"]}
    assert "external.capability_acquisition" not in ids
    assert sum(debt["counts_by_status"].values()) == len(debt["components"])

    status = (_root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AX" in status
    assert "external.capability_acquisition" in status
    assert "moves from 3 to 2 non-native" in status
