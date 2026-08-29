from __future__ import annotations

import ast
import importlib
import json
import math
from pathlib import Path

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane, PromotionAssuranceReceipt
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.experience import (
    AttributionRecord,
    ExperienceLedger,
    ExperienceOutcome,
    ExperienceRecord,
    LearningLayer,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _native():
    return importlib.import_module("nolane.external_core.transfer_meta")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def _experience_ledger(
    *,
    outcome: ExperienceOutcome = ExperienceOutcome.SUCCESS,
    positive: bool = True,
    passed: bool = True,
    false_accepts: int = 0,
    regressions: int = 0,
    lesson: str = "Prefer a bounded positional causal prior before fresh search.",
) -> tuple[ExperienceLedger, ExperienceRecord, AttributionRecord]:
    evidence = EvidenceRecord(
        "evidence-wave5ay-source",
        "verification.chief",
        passed,
        false_accepts=false_accepts,
        regressions=regressions,
    )
    source = ExperienceRecord(
        experience_id="experience-wave5ay-source",
        agent_id="source.agent",
        region="source-region",
        domain="repository-repair",
        outcome=outcome,
        summary="Source task summary that must not enter the portable payload.",
        task_id="task-secret-source",
        object_refs=("object-secret-source",),
        evidence_refs=(evidence.evidence_id,),
    )
    attribution = AttributionRecord(
        attribution_id="attribution-wave5ay-source",
        experience_id=source.experience_id,
        agent_id=source.agent_id,
        learning_layer=LearningLayer.STRATEGY,
        lesson=lesson,
        positive=positive,
        verifier_agent_id=evidence.verifier_agent_id,
        evidence=evidence,
    )
    ledger = object.__new__(ExperienceLedger)
    ledger._experiences = {source.experience_id: source}
    ledger._attributions = {attribution.attribution_id: attribution}
    return ledger, source, attribution


def _promotion_receipt(
    *,
    receipt_id: str,
    transfer_id: str,
    evidence_ids: tuple[str, ...],
    predecessor_version: str,
    authorized: bool = True,
) -> PromotionAssuranceReceipt:
    payload = {
        "receipt_id": receipt_id,
        "subject_id": transfer_id,
        "evidence_ids": list(evidence_ids),
        "predecessor_version": predecessor_version,
        "verifier_ids": ["verification.chief", "assurance.chief"],
        "authorized": authorized,
        "reasons": [] if authorized else ["rejected"],
    }
    return PromotionAssuranceReceipt(
        receipt_id=receipt_id,
        subject_id=transfer_id,
        evidence_ids=evidence_ids,
        predecessor_version=predecessor_version,
        verifier_ids=("verification.chief", "assurance.chief"),
        authorized=authorized,
        reasons=() if authorized else ("rejected",),
        digest=canonical_digest(payload),
    )


def _assurance_plane(*receipts: PromotionAssuranceReceipt) -> AssuranceControlPlane:
    plane = object.__new__(AssuranceControlPlane)
    plane._promotion_receipts = {row.receipt_id: row for row in receipts}
    return plane


def _proposed(native):
    ledger, source, attribution = _experience_ledger()
    governor = native.TransferMetaGovernor(experience=ledger)
    portable, source_receipt = governor.compile_portable(source.experience_id, attribution.attribution_id)
    record = governor.propose(
        portable.portable_id,
        target_domain="incident-response",
        metadata={"numeric_domain": "finite", "role_count": 2, "limits": {"queries": 4}},
    )
    return ledger, governor, portable, source_receipt, record


def test_wave5ay_native_transfer_meta_authority_exists_and_has_no_reverse_imports() -> None:
    module = _native()
    assert module.COMPONENT_ID == "external.transfer_meta"
    assert module.COMPONENT_VERSION == "0.0.1"
    assert module.MIGRATED_FROM == "cogcoder R2.69 autonomous transfer/meta-learning lineage"

    expected = {
        "PortableExperience",
        "PortableExperienceSourceReceipt",
        "TransferAdaptation",
        "TransferState",
        "TransferRecord",
        "TransferMetaGovernor",
    }
    assert expected.issubset(set(module.__all__))

    imports = _imports(_root() / "nolane" / "external_core" / "transfer_meta.py")
    assert not any(name.startswith("cogcoder") for name in imports)
    assert not any(name.startswith("research") or name.startswith("ai") for name in imports)


def test_wave5ay_portable_payload_is_identity_free_and_source_authority_is_derived() -> None:
    native = _native()
    ledger, source, attribution = _experience_ledger()
    governor = native.TransferMetaGovernor(experience=ledger)
    portable, receipt = governor.compile_portable(source.experience_id, attribution.attribution_id)

    raw_portable = json.dumps(portable.to_state(), sort_keys=True)
    for forbidden in (source.agent_id, source.region, source.task_id, source.experience_id, attribution.attribution_id):
        assert forbidden not in raw_portable
    assert portable.source_domain == source.domain
    assert portable.learning_layer == attribution.learning_layer.value
    assert portable.lesson == attribution.lesson

    assert receipt.source_experience_id == source.experience_id
    assert receipt.attribution_id == attribution.attribution_id
    assert receipt.source_evidence_digest == canonical_digest(attribution.evidence.to_state())
    assert receipt.source_authority_digest.startswith("transfer-source:")
    assert receipt.receipt_id.startswith("transfer-source-receipt:")

    restored_portable = native.PortableExperience.from_state(portable.to_state())
    restored_receipt = native.PortableExperienceSourceReceipt.from_state(receipt.to_state())
    assert restored_portable == portable
    assert restored_receipt == receipt

    forged = receipt.to_state()
    forged["source_authority_digest"] = "caller-minted-authority"
    with pytest.raises(ValueError, match="authority"):
        native.PortableExperienceSourceReceipt.from_state(forged)


def test_wave5ay_only_clean_externally_verified_success_experience_becomes_portable() -> None:
    native = _native()
    for kwargs in (
        {"outcome": ExperienceOutcome.FAILURE},
        {"outcome": ExperienceOutcome.MIXED},
        {"positive": False},
        {"passed": False},
        {"false_accepts": 1},
        {"regressions": 1},
    ):
        ledger, source, attribution = _experience_ledger(**kwargs)
        governor = native.TransferMetaGovernor(experience=ledger)
        with pytest.raises(ValueError):
            governor.compile_portable(source.experience_id, attribution.attribution_id)

    ledger, source, attribution = _experience_ledger()
    forged_self = AttributionRecord(
        attribution_id=attribution.attribution_id,
        experience_id=source.experience_id,
        agent_id=source.agent_id,
        learning_layer=attribution.learning_layer,
        lesson=attribution.lesson,
        positive=True,
        verifier_agent_id=source.agent_id,
        evidence=EvidenceRecord("evidence-self", source.agent_id, True),
    )
    ledger._attributions[forged_self.attribution_id] = forged_self
    with pytest.raises(ValueError, match="external"):
        native.TransferMetaGovernor(experience=ledger).compile_portable(
            source.experience_id, forged_self.attribution_id
        )


def test_wave5ay_adaptation_is_content_addressed_domain_bound_and_finite_json_only() -> None:
    native = _native()
    ledger, source, attribution = _experience_ledger()
    governor = native.TransferMetaGovernor(experience=ledger)
    portable, _ = governor.compile_portable(source.experience_id, attribution.attribution_id)

    first = native.TransferAdaptation.create(
        portable,
        target_domain="incident-response",
        metadata={"b": 2, "a": {"z": True, "x": [1, 2]}},
    )
    reordered = native.TransferAdaptation.create(
        portable,
        target_domain="incident-response",
        metadata={"a": {"x": [1, 2], "z": True}, "b": 2},
    )
    assert first.transfer_id == reordered.transfer_id
    assert first.metadata() == reordered.metadata()

    changed_domain = native.TransferAdaptation.create(
        portable,
        target_domain="security-review",
        metadata={"b": 2, "a": {"z": True, "x": [1, 2]}},
    )
    assert first.transfer_id != changed_domain.transfer_id

    with pytest.raises(ValueError, match="differ"):
        native.TransferAdaptation.create(portable, target_domain=portable.source_domain, metadata={})
    with pytest.raises(ValueError, match="finite"):
        native.TransferAdaptation.create(portable, target_domain="other", metadata={"x": math.nan})


def test_wave5ay_preacceptance_reuse_is_blocked_and_exact_persisted_assurance_is_required() -> None:
    native = _native()
    _, governor, portable, source_receipt, record = _proposed(native)
    with pytest.raises(PermissionError):
        governor.resolve(record.adaptation.transfer_id)
    assert governor.reusable_ids() == ()

    evidence_ids = ("acceptance:heldout", "acceptance:challenge")
    accepted = _promotion_receipt(
        receipt_id="assurance-transfer-accepted",
        transfer_id=record.adaptation.transfer_id,
        evidence_ids=evidence_ids,
        predecessor_version=source_receipt.source_authority_digest,
    )

    with pytest.raises((KeyError, ValueError), match="persisted|unknown"):
        governor.accept(
            record.adaptation.transfer_id,
            assurance=_assurance_plane(),
            receipt=accepted,
            evidence_ids=evidence_ids,
        )

    wrong_source = _promotion_receipt(
        receipt_id="assurance-transfer-wrong-source",
        transfer_id=record.adaptation.transfer_id,
        evidence_ids=evidence_ids,
        predecessor_version="transfer-source:wrong",
    )
    with pytest.raises(ValueError, match="source authority"):
        governor.accept(
            record.adaptation.transfer_id,
            assurance=_assurance_plane(wrong_source),
            receipt=wrong_source,
            evidence_ids=evidence_ids,
        )

    accepted_row = governor.accept(
        record.adaptation.transfer_id,
        assurance=_assurance_plane(accepted),
        receipt=accepted,
        evidence_ids=evidence_ids,
    )
    assert accepted_row.state is native.TransferState.ACCEPTED
    assert governor.reusable_ids(target_domain="incident-response") == (record.adaptation.transfer_id,)
    resolved_portable, resolved_adaptation = governor.resolve(record.adaptation.transfer_id)
    assert resolved_portable == portable
    assert resolved_adaptation == record.adaptation


def test_wave5ay_assurance_subject_evidence_authorization_and_digest_replay_fail_closed() -> None:
    native = _native()
    _, governor, _, source_receipt, record = _proposed(native)
    evidence_ids = ("acceptance:heldout", "acceptance:challenge")

    wrong_subject = _promotion_receipt(
        receipt_id="assurance-transfer-wrong-subject",
        transfer_id="transfer:other",
        evidence_ids=evidence_ids,
        predecessor_version=source_receipt.source_authority_digest,
    )
    with pytest.raises(ValueError, match="subject"):
        governor.accept(
            record.adaptation.transfer_id,
            assurance=_assurance_plane(wrong_subject),
            receipt=wrong_subject,
            evidence_ids=evidence_ids,
        )

    wrong_evidence = _promotion_receipt(
        receipt_id="assurance-transfer-wrong-evidence",
        transfer_id=record.adaptation.transfer_id,
        evidence_ids=("acceptance:other",),
        predecessor_version=source_receipt.source_authority_digest,
    )
    with pytest.raises(ValueError, match="evidence"):
        governor.accept(
            record.adaptation.transfer_id,
            assurance=_assurance_plane(wrong_evidence),
            receipt=wrong_evidence,
            evidence_ids=evidence_ids,
        )

    rejected = _promotion_receipt(
        receipt_id="assurance-transfer-rejected",
        transfer_id=record.adaptation.transfer_id,
        evidence_ids=evidence_ids,
        predecessor_version=source_receipt.source_authority_digest,
        authorized=False,
    )
    with pytest.raises(ValueError, match="authorized"):
        governor.accept(
            record.adaptation.transfer_id,
            assurance=_assurance_plane(rejected),
            receipt=rejected,
            evidence_ids=evidence_ids,
        )

    valid = _promotion_receipt(
        receipt_id="assurance-transfer-tamper",
        transfer_id=record.adaptation.transfer_id,
        evidence_ids=evidence_ids,
        predecessor_version=source_receipt.source_authority_digest,
    )
    tampered = PromotionAssuranceReceipt(
        receipt_id=valid.receipt_id,
        subject_id=valid.subject_id,
        evidence_ids=valid.evidence_ids,
        predecessor_version=valid.predecessor_version,
        verifier_ids=valid.verifier_ids,
        authorized=valid.authorized,
        reasons=valid.reasons,
        digest="tampered-digest",
    )
    with pytest.raises(ValueError, match="digest"):
        governor.accept(
            record.adaptation.transfer_id,
            assurance=_assurance_plane(tampered),
            receipt=tampered,
            evidence_ids=evidence_ids,
        )


def test_wave5ay_negative_transfer_quarantines_and_cannot_be_reused_or_reaccepted() -> None:
    native = _native()
    _, governor, _, source_receipt, record = _proposed(native)
    evidence_ids = ("acceptance:heldout", "acceptance:challenge")
    receipt = _promotion_receipt(
        receipt_id="assurance-transfer-negative",
        transfer_id=record.adaptation.transfer_id,
        evidence_ids=evidence_ids,
        predecessor_version=source_receipt.source_authority_digest,
    )
    governor.accept(
        record.adaptation.transfer_id,
        assurance=_assurance_plane(receipt),
        receipt=receipt,
        evidence_ids=evidence_ids,
    )
    revoked = governor.report_negative_transfer(
        record.adaptation.transfer_id,
        reason="held-out target regression",
    )
    assert revoked.state is native.TransferState.QUARANTINED
    assert revoked.assurance_receipt_id == receipt.receipt_id
    assert governor.reusable_ids() == ()
    with pytest.raises(PermissionError):
        governor.resolve(record.adaptation.transfer_id)
    with pytest.raises(ValueError, match="quarantined"):
        governor.accept(
            record.adaptation.transfer_id,
            assurance=_assurance_plane(receipt),
            receipt=receipt,
            evidence_ids=evidence_ids,
        )


def test_wave5ay_snapshot_restore_rebinds_native_sources_and_assurance_and_rejects_tampering() -> None:
    native = _native()
    ledger, governor, _, source_receipt, record = _proposed(native)
    evidence_ids = ("acceptance:heldout", "acceptance:challenge")
    receipt = _promotion_receipt(
        receipt_id="assurance-transfer-snapshot",
        transfer_id=record.adaptation.transfer_id,
        evidence_ids=evidence_ids,
        predecessor_version=source_receipt.source_authority_digest,
    )
    assurance = _assurance_plane(receipt)
    governor.accept(
        record.adaptation.transfer_id,
        assurance=assurance,
        receipt=receipt,
        evidence_ids=evidence_ids,
    )
    state = governor.to_state()
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    restored = native.TransferMetaGovernor.from_state(
        json.loads(encoded),
        experience=ledger,
        assurance=assurance,
    )
    assert json.dumps(restored.to_state(), sort_keys=True, separators=(",", ":"), ensure_ascii=False) == encoded
    assert restored.digest == governor.digest

    with pytest.raises(ValueError, match="Assurance"):
        native.TransferMetaGovernor.from_state(json.loads(encoded), experience=ledger)

    corrupt_portable = json.loads(encoded)
    corrupt_portable["portables"][0]["portable_id"] = "portable:tampered"
    with pytest.raises(ValueError, match="portable experience identity"):
        native.TransferMetaGovernor.from_state(corrupt_portable, experience=ledger, assurance=assurance)

    corrupt_transfer = json.loads(encoded)
    corrupt_transfer["records"][0]["adaptation"]["transfer_id"] = "transfer:tampered"
    with pytest.raises(ValueError, match="transfer adaptation identity"):
        native.TransferMetaGovernor.from_state(corrupt_transfer, experience=ledger, assurance=assurance)

    corrupt_source = json.loads(encoded)
    corrupt_source["sources"][0]["source_evidence_digest"] = "evidence:tampered"
    with pytest.raises(ValueError, match="authority|source"):
        native.TransferMetaGovernor.from_state(corrupt_source, experience=ledger, assurance=assurance)

    corrupt_schema = json.loads(encoded)
    corrupt_schema["schema_version"] = "transfer-meta-v999"
    with pytest.raises(ValueError, match="schema"):
        native.TransferMetaGovernor.from_state(corrupt_schema, experience=ledger, assurance=assurance)
