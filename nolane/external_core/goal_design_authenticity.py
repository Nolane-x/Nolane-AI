"""Authenticity proofs for Goal/Design decision receipts and authority events.

Decision receipts are content-addressed authority artifacts.  This module keeps
identity verification separate from lifecycle/index persistence so every
consumer can prove the artifact it is about to trust is the exact artifact
that was originally admitted.
"""
from __future__ import annotations

from typing import Any, Mapping

from .goal_design import DecisionReceipt, stable_digest


_BASE_RECEIPT_FIELDS = (
    "goal_id",
    "selected_option_id",
    "snapshot_digest",
    "version_vector",
    "evaluation_digest",
    "proof_obligation_ids",
    "uncertainty_ids",
    "evidence_refs",
)

_EXTENDED_RECEIPT_FIELDS = (
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


def decision_receipt_payload(receipt: DecisionReceipt) -> dict[str, Any]:
    """Return the canonical identity payload for a v1 or v2 receipt.

    v1 is the original eight-field identity.  v2 extends that identity with
    seven manifests/state digests.  A partially populated extension is not a
    third implicit schema: it is ambiguous authority and therefore rejected.
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
    extended = {field: str(getattr(receipt, field, "")) for field in _EXTENDED_RECEIPT_FIELDS}
    populated = tuple(bool(value) for value in extended.values())
    if any(populated) and not all(populated):
        raise ValueError("decision receipt identity has a partially populated v2 manifest")
    if all(populated):
        payload.update(extended)
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
    extended = tuple(str(getattr(receipt, field, "")) for field in _EXTENDED_RECEIPT_FIELDS)
    return "v2" if all(extended) else "v1"


def decision_event_payload(receipt: DecisionReceipt) -> dict[str, Any]:
    """Canonical ledger payload for an authoritative decision event."""

    verify_decision_receipt(receipt)
    return {
        "receipt_id": receipt.receipt_id,
        "goal_id": receipt.goal_id,
        "selected_option_id": receipt.selected_option_id,
        "snapshot_digest": receipt.snapshot_digest,
        "evaluation_digest": receipt.evaluation_digest,
        "input_manifest_digest": receipt.input_manifest_digest,
    }


def decision_event_subject_refs(receipt: DecisionReceipt) -> tuple[str, ...]:
    verify_decision_receipt(receipt)
    return (receipt.goal_id, receipt.selected_option_id, receipt.snapshot_digest)


def verify_decision_authority_event(receipt: DecisionReceipt, event: Any) -> None:
    """Prove an event is the exact authoritative ledger event for ``receipt``."""

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

    expected_payload_digest = stable_digest(decision_event_payload(receipt))
    if str(getattr(event, "payload_digest", "")) != expected_payload_digest:
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
