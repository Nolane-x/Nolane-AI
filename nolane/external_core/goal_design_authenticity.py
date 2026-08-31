"""Authenticity proofs for Goal/Design decision receipts and authority events.

Decision receipts are content-addressed authority artifacts. Verification is
schema-aware and monotonic: v1 and v2 retain their historical identities while
v3 adds an exact assumption truth snapshot and assumption dependency closure.
"""
from __future__ import annotations

from typing import Any

from .goal_design import DecisionReceipt, stable_digest


_V2_RECEIPT_FIELDS = (
    "goal_digest",
    "scenario_set_digest",
    "option_set_digest",
    "proof_state_digest",
    "uncertainty_state_digest",
    "traceability_digest",
    "input_manifest_digest",
)


def _sequence(value: Any) -> list[Any]:
    return list(value)


def _v2_state(receipt: DecisionReceipt) -> dict[str, str]:
    return {field: str(getattr(receipt, field, "")) for field in _V2_RECEIPT_FIELDS}


def _v3_state(receipt: DecisionReceipt) -> tuple[tuple[str, ...], str]:
    refs = tuple(str(value) for value in getattr(receipt, "assumption_refs", ()))
    digest = str(getattr(receipt, "assumption_state_digest", ""))
    return refs, digest


def decision_receipt_payload(receipt: DecisionReceipt) -> dict[str, Any]:
    """Return the canonical identity payload for receipt schema v1/v2/v3.

    v1 is the original eight-field identity. v2 extends it with seven manifest
    digests. v3 extends v2 with the exact truth-maintained assumption closure
    and the content-addressed assumption snapshot digest. Partial extensions are
    ambiguous authority and are rejected fail-closed.
    """

    payload: dict[str, Any] = {
        "goal_id": receipt.goal_id,
        "selected_option_id": receipt.selected_option_id,
        "snapshot_digest": receipt.snapshot_digest,
        "version_vector": dict(receipt.version_vector),
        "evaluation_digest": receipt.evaluation_digest,
        "proof_obligation_ids": _sequence(receipt.proof_obligation_ids),
        "uncertainty_ids": _sequence(receipt.uncertainty_ids),
        "evidence_refs": _sequence(receipt.evidence_refs),
    }

    v2 = _v2_state(receipt)
    v2_populated = tuple(bool(value) for value in v2.values())
    if any(v2_populated) and not all(v2_populated):
        raise ValueError("decision receipt identity has a partially populated v2 manifest")
    has_v2 = all(v2_populated)
    if has_v2:
        payload.update(v2)

    assumption_refs, assumption_state_digest = _v3_state(receipt)
    v3_populated = (bool(assumption_refs), bool(assumption_state_digest))
    if any(v3_populated) and not all(v3_populated):
        raise ValueError("decision receipt identity has a partially populated v3 assumption binding")
    has_v3 = all(v3_populated)
    if has_v3 and not has_v2:
        raise ValueError("decision receipt v3 assumption binding requires a complete v2 manifest")
    if has_v3:
        payload["assumption_refs"] = list(assumption_refs)
        payload["assumption_state_digest"] = assumption_state_digest
    return payload


def expected_decision_receipt_id(receipt: DecisionReceipt) -> str:
    return stable_digest({"goal_design_decision": decision_receipt_payload(receipt)})


def verify_decision_receipt(receipt: DecisionReceipt) -> str:
    """Prove content identity and return the detected identity schema version."""

    actual = str(receipt.receipt_id).strip()
    if not actual:
        raise ValueError("decision receipt identity is required")
    expected = expected_decision_receipt_id(receipt)
    if actual != expected:
        raise ValueError("decision receipt identity digest mismatch")

    assumption_refs, assumption_state_digest = _v3_state(receipt)
    if assumption_refs and assumption_state_digest:
        return "v3"
    v2 = tuple(_v2_state(receipt).values())
    return "v2" if all(v2) else "v1"


def _decision_event_base_payload(receipt: DecisionReceipt) -> dict[str, Any]:
    return {
        "receipt_id": receipt.receipt_id,
        "goal_id": receipt.goal_id,
        "selected_option_id": receipt.selected_option_id,
        "snapshot_digest": receipt.snapshot_digest,
        "evaluation_digest": receipt.evaluation_digest,
    }


def decision_event_payload(receipt: DecisionReceipt) -> dict[str, Any]:
    """Return the canonical DECISION-event payload minted for this receipt."""

    receipt_version = verify_decision_receipt(receipt)
    payload = _decision_event_base_payload(receipt)
    if receipt_version in {"v2", "v3"}:
        payload["input_manifest_digest"] = receipt.input_manifest_digest
    if receipt_version == "v3":
        payload["assumption_refs"] = list(receipt.assumption_refs)
        payload["assumption_state_digest"] = receipt.assumption_state_digest
    return payload


def _accepted_decision_event_payload_digests(receipt: DecisionReceipt) -> frozenset[str]:
    receipt_version = verify_decision_receipt(receipt)
    canonical = decision_event_payload(receipt)
    digests = {stable_digest(canonical)}
    if receipt_version == "v1":
        # Historical transitional runtime briefly emitted the v2 field with an
        # empty value for restored v1 receipts. Preserve that exact artifact.
        transitional = _decision_event_base_payload(receipt)
        transitional["input_manifest_digest"] = ""
        digests.add(stable_digest(transitional))
    return frozenset(digests)


def decision_event_subject_refs(receipt: DecisionReceipt) -> tuple[str, ...]:
    version = verify_decision_receipt(receipt)
    subjects = [receipt.goal_id, receipt.selected_option_id, receipt.snapshot_digest]
    if version == "v3":
        subjects.extend(receipt.assumption_refs)
    return tuple(subjects)


def verify_decision_authority_event(receipt: DecisionReceipt, event: Any) -> None:
    """Prove an event is an exact recognized authority event for ``receipt``."""

    verify_decision_receipt(receipt)
    kind = str(getattr(getattr(event, "kind", None), "value", getattr(event, "kind", "")))
    authority = str(
        getattr(
            getattr(event, "authority_level", None),
            "value",
            getattr(event, "authority_level", ""),
        )
    )
    if kind != "decision" or authority != "authority":
        raise ValueError("authority event is not a decision authority event")

    observed_payload_digest = str(getattr(event, "payload_digest", ""))
    if observed_payload_digest not in _accepted_decision_event_payload_digests(receipt):
        raise ValueError("decision authority event payload does not bind the receipt")

    expected_subjects = decision_event_subject_refs(receipt)
    observed_subjects = tuple(str(value) for value in getattr(event, "subject_refs", ()))
    if observed_subjects != expected_subjects:
        raise ValueError("decision authority event subjects do not bind the receipt")


__all__ = [
    "decision_event_payload",
    "decision_event_subject_refs",
    "decision_receipt_payload",
    "expected_decision_receipt_id",
    "verify_decision_authority_event",
    "verify_decision_receipt",
]
