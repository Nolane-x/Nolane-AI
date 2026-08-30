from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.external_core.software_engineering import (
    EngineeringEvidenceLedger,
    EngineeringPatchTransaction,
    PatchTransactionLedger,
)


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


@dataclass(frozen=True, slots=True)
class AttemptBoundEngineeringPatchTransaction(EngineeringPatchTransaction):
    """Patch transaction whose immutable origin is fenced by one operation ref."""

    operation_ref: str = ""

    def __post_init__(self) -> None:
        # dataclass(slots=True) may synthesize a replacement class object on
        # Python 3.11, so zero-argument super() can retain a stale __class__
        # cell. Call the immutable base implementation explicitly.
        EngineeringPatchTransaction.__post_init__(self)
        _text(self.operation_ref, field="engineering operation ref")

    def to_state(self) -> dict[str, Any]:
        return {
            **EngineeringPatchTransaction.to_state(self),
            "operation_ref": self.operation_ref,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AttemptBoundEngineeringPatchTransaction":
        base = EngineeringPatchTransaction.from_state(state)
        return cls(
            transaction_id=base.transaction_id,
            patch_ref=base.patch_ref,
            patch_digest=base.patch_digest,
            source_revision=base.source_revision,
            rollback_artifact_ref=base.rollback_artifact_ref,
            phase=base.phase,
            claim_refs=base.claim_refs,
            precondition_attestation_ids=base.precondition_attestation_ids,
            application_ref=base.application_ref,
            outcome_evidence_refs=base.outcome_evidence_refs,
            postcondition_attestation_ids=base.postcondition_attestation_ids,
            closure_receipt_id=base.closure_receipt_id,
            rollback_ref=base.rollback_ref,
            failure_reason=base.failure_reason,
            operation_ref=_text(state["operation_ref"], field="engineering operation ref"),
        )


class IdempotentPatchTransactionLedger(PatchTransactionLedger):
    """Patch lifecycle with immutable operation-ref → transaction fencing.

    Exact retries return the existing transaction at its current phase. Reusing
    an operation ref with different immutable initiation inputs fails closed.
    Distinct operation refs deliberately remain independent attempts.
    """

    def __init__(self, evidence: EngineeringEvidenceLedger) -> None:
        super().__init__(evidence)
        self._operation_to_transaction: dict[str, str] = {}

    def next_automatic_operation_ref(self) -> str:
        candidate_number = self._counter + 1
        while True:
            candidate = f"eng-op:auto-{candidate_number:08d}"
            if candidate not in self._operation_to_transaction:
                return candidate
            candidate_number += 1

    def transaction_for_operation(self, operation_ref: str) -> AttemptBoundEngineeringPatchTransaction | None:
        transaction_id = self._operation_to_transaction.get(str(operation_ref).strip())
        if transaction_id is None:
            return None
        row = self.get(transaction_id)
        if not isinstance(row, AttemptBoundEngineeringPatchTransaction):
            raise ValueError("engineering operation index points to unbound transaction")
        return row

    def begin(
        self,
        *,
        patch_ref: str,
        patch_digest: str,
        source_revision: str,
        rollback_artifact_ref: str,
        operation_ref: str | None = None,
    ) -> AttemptBoundEngineeringPatchTransaction:
        operation = (
            self.next_automatic_operation_ref()
            if operation_ref is None
            else _text(operation_ref, field="engineering operation ref")
        )
        patch_identity = _text(patch_ref, field="patch ref")
        patch_state = _text(patch_digest, field="patch digest")
        source = _text(source_revision, field="source revision")
        rollback = _text(rollback_artifact_ref, field="rollback artifact")

        existing = self.transaction_for_operation(operation)
        if existing is not None:
            if (
                existing.patch_ref != patch_identity
                or existing.patch_digest != patch_state
                or existing.source_revision != source
                or existing.rollback_artifact_ref != rollback
            ):
                raise ValueError("engineering operation ref cannot be rebound to different initiation inputs")
            return existing

        base = super().begin(
            patch_ref=patch_identity,
            patch_digest=patch_state,
            source_revision=source,
            rollback_artifact_ref=rollback,
        )
        row = AttemptBoundEngineeringPatchTransaction(
            transaction_id=base.transaction_id,
            patch_ref=base.patch_ref,
            patch_digest=base.patch_digest,
            source_revision=base.source_revision,
            rollback_artifact_ref=base.rollback_artifact_ref,
            phase=base.phase,
            claim_refs=base.claim_refs,
            precondition_attestation_ids=base.precondition_attestation_ids,
            application_ref=base.application_ref,
            outcome_evidence_refs=base.outcome_evidence_refs,
            postcondition_attestation_ids=base.postcondition_attestation_ids,
            closure_receipt_id=base.closure_receipt_id,
            rollback_ref=base.rollback_ref,
            failure_reason=base.failure_reason,
            operation_ref=operation,
        )
        self._transactions[row.transaction_id] = row
        self._operation_to_transaction[operation] = row.transaction_id
        return row

    @classmethod
    def from_state(
        cls,
        *,
        evidence: EngineeringEvidenceLedger,
        state: Mapping[str, Any],
    ) -> "IdempotentPatchTransactionLedger":
        ledger = cls(evidence)
        for value in state.get("transactions", ()):
            row = AttemptBoundEngineeringPatchTransaction.from_state(value)
            if row.transaction_id in ledger._transactions:
                raise ValueError("duplicate engineering transaction id")
            previous = ledger._operation_to_transaction.get(row.operation_ref)
            if previous is not None and previous != row.transaction_id:
                raise ValueError("engineering operation ref cannot bind multiple transactions")
            ledger._transactions[row.transaction_id] = row
            ledger._operation_to_transaction[row.operation_ref] = row.transaction_id

        ledger._counter = int(state.get("counter", len(ledger._transactions)))
        maximum = 0
        for identity in ledger._transactions:
            try:
                maximum = max(maximum, int(identity.rsplit("-", 1)[1]))
            except Exception as exc:
                raise ValueError("non-canonical engineering transaction id") from exc
        if ledger._counter < maximum:
            raise ValueError("engineering transaction counter behind history")
        return ledger


__all__ = (
    "AttemptBoundEngineeringPatchTransaction",
    "IdempotentPatchTransactionLedger",
)
