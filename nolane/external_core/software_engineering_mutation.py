from __future__ import annotations

from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering import (
    EngineeringEvidenceLedger,
    EngineeringPhase,
    PatchTransactionLedger,
)
from nolane.external_core.software_engineering_validity import (
    EngineeringClaimBindingLedger,
    EngineeringMutationAuthorityDecision,
    EngineeringMutationAuthorityEngine,
    EngineeringMutationAuthorityReceipt,
)


PARENT_COMPONENT_ID = "external.software_engineering.control"
PROTOCOL_ID = "external.software_engineering.mutation_evidence_guard"
PROTOCOL_VERSION = "0.1.0"


class EvidenceBoundMutationAuthorityEngine(EngineeringMutationAuthorityEngine):
    """Tightens mutation authority with live precondition-evidence validity.

    The canonical mutation-authority engine owns claim/transaction semantics.
    This adapter adds one additional fail-closed invariant at the control-plane
    boundary: precondition attestations must still be live at the instant the
    patch is applied. Historical verification phase alone is not authority.
    """

    def __init__(
        self,
        *,
        transactions: PatchTransactionLedger,
        claim_bindings: EngineeringClaimBindingLedger,
        evidence: EngineeringEvidenceLedger,
    ) -> None:
        super().__init__(transactions=transactions, claim_bindings=claim_bindings)
        self.evidence = evidence

    def _precondition_evidence_reasons(self, transaction_id: str) -> tuple[str, ...]:
        tx = self.transactions.get(transaction_id)
        reasons: list[str] = []
        for attestation_id in tx.precondition_attestation_ids:
            if not self.evidence.is_valid(
                attestation_id,
                subject_ref=tx.patch_ref,
                subject_digest=tx.patch_digest,
                source_revision=tx.source_revision,
            ):
                reasons.append(f"precondition_evidence_invalid:{attestation_id}")
        return tuple(sorted(set(reasons)))

    def preapply_reasons(self, transaction_id: str) -> tuple[str, ...]:
        tx = self.transactions.get(transaction_id)
        reasons: list[str] = []
        if tx.phase is not EngineeringPhase.PRECONDITIONS_VERIFIED:
            reasons.append("transaction_not_precondition_verified")
        binding = self.claim_bindings.for_transaction(tx.transaction_id)
        if binding is None:
            reasons.append("missing_claim_state_binding")
        else:
            reasons.extend(self.claim_bindings.current_reasons(binding.binding_id))
        reasons.extend(self._precondition_evidence_reasons(tx.transaction_id))
        return tuple(sorted(set(reasons)))

    def assess(self, transaction_id: str, *, patch: Any) -> EngineeringMutationAuthorityReceipt:
        base = super().assess(transaction_id, patch=patch)
        evidence_reasons = self._precondition_evidence_reasons(transaction_id)
        if not evidence_reasons:
            return base

        reasons = tuple(sorted(set(base.reasons) | set(evidence_reasons)))
        payload = {
            "transaction_id": base.transaction_id,
            "patch_ref": base.patch_ref,
            "patch_digest": base.patch_digest,
            "claim_binding_id": base.claim_binding_id,
            "claim_binding_digest": base.claim_binding_digest,
            "authorized": False,
            "decision": EngineeringMutationAuthorityDecision.BLOCKED.value,
            "reasons": list(reasons),
            "authority": "mutation_scope_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringMutationAuthorityReceipt(
            receipt_id=f"eng-mutation-authority-{digest[:20]}",
            transaction_id=base.transaction_id,
            patch_ref=base.patch_ref,
            patch_digest=base.patch_digest,
            claim_binding_id=base.claim_binding_id,
            claim_binding_digest=base.claim_binding_digest,
            authorized=False,
            decision=EngineeringMutationAuthorityDecision.BLOCKED,
            reasons=reasons,
            authority="mutation_scope_only",
            digest=digest,
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("engineering mutation authority receipt cannot be rebound")
        self._receipts[row.receipt_id] = row
        return existing or row

    @classmethod
    def from_state(
        cls,
        *,
        transactions: PatchTransactionLedger,
        claim_bindings: EngineeringClaimBindingLedger,
        evidence: EngineeringEvidenceLedger,
        state: Mapping[str, Any],
    ) -> "EvidenceBoundMutationAuthorityEngine":
        engine = cls(
            transactions=transactions,
            claim_bindings=claim_bindings,
            evidence=evidence,
        )
        for value in state.get("receipts", ()):
            row = EngineeringMutationAuthorityReceipt.from_state(value)
            tx = transactions.get(row.transaction_id)
            if row.patch_ref != tx.patch_ref or row.patch_digest != tx.patch_digest:
                raise ValueError("mutation authority snapshot transaction lineage mismatch")
            if row.claim_binding_id is not None:
                binding = claim_bindings.get(row.claim_binding_id)
                if binding.digest != row.claim_binding_digest or binding.transaction_id != row.transaction_id:
                    raise ValueError("mutation authority snapshot claim lineage mismatch")
            existing = engine._receipts.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound mutation authority receipt")
            engine._receipts[row.receipt_id] = row
        return engine


__all__ = ("EvidenceBoundMutationAuthorityEngine",)
