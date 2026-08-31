from __future__ import annotations

from nolane.external_core.software_engineering import EngineeringPhase, PatchTransactionLedger
from nolane.external_core.software_engineering_effect_journal import EngineeringEffectJournal
from nolane.external_core.software_engineering_effects import (
    EngineeringApplicationCommit,
    EngineeringEffectLedger,
    EngineeringRollbackCompletion,
    EngineeringRollbackDecision,
)


PARENT_COMPONENT_ID = "external.software_engineering.control"
PROTOCOL_ID = "external.software_engineering.effect_recovery"
PROTOCOL_VERSION = "0.1.0"


class EngineeringEffectFinalizer:
    """Finalize local state from durable external-effect observations."""

    def __init__(
        self,
        *,
        transactions: PatchTransactionLedger,
        effects: EngineeringEffectLedger,
        journal: EngineeringEffectJournal,
    ) -> None:
        self.transactions = transactions
        self.effects = effects
        self.journal = journal

    def finalize_application(self, acknowledgement_id: str) -> EngineeringApplicationCommit:
        acknowledgement = self.journal.application_acknowledgement(acknowledgement_id)
        intent = self.effects.application_intent(acknowledgement.intent_id)
        tx = self.transactions.get(acknowledgement.transaction_id)
        if (
            acknowledgement.intent_digest != intent.digest
            or acknowledgement.transaction_id != intent.transaction_id
            or acknowledgement.patch_ref != intent.patch_ref
            or acknowledgement.patch_digest != intent.patch_digest
            or acknowledgement.application_ref != intent.application_ref
            or tx.patch_ref != intent.patch_ref
            or tx.patch_digest != intent.patch_digest
        ):
            raise ValueError("application acknowledgement finalization lineage mismatch")

        mutation_receipt = self.effects._mutation_receipt(intent.mutation_authority_receipt_id)
        if (
            mutation_receipt.digest != intent.mutation_authority_receipt_digest
            or not mutation_receipt.authorized
            or mutation_receipt.transaction_id != tx.transaction_id
            or mutation_receipt.patch_ref != tx.patch_ref
            or mutation_receipt.patch_digest != tx.patch_digest
        ):
            raise PermissionError("application acknowledgement lost immutable mutation authority lineage")

        existing = self.effects.application_commit_for_transaction(tx.transaction_id)
        if existing is not None:
            if (
                existing.intent_id != intent.intent_id
                or existing.intent_digest != intent.digest
                or existing.application_ref != acknowledgement.application_ref
                or existing.executor_receipt_ref != acknowledgement.executor_receipt_ref
            ):
                raise ValueError("application acknowledgement conflicts with existing commit")
            return existing

        if tx.phase is EngineeringPhase.APPLIED:
            if tx.application_ref != acknowledgement.application_ref:
                raise ValueError("applied transaction does not match application acknowledgement")
        elif tx.phase is EngineeringPhase.PRECONDITIONS_VERIFIED:
            self.transactions.mark_applied(
                tx.transaction_id,
                application_ref=acknowledgement.application_ref,
            )
            tx = self.transactions.get(tx.transaction_id)
        else:
            raise ValueError("application acknowledgement cannot finalize from current transaction phase")

        row = self.effects._build_application_commit(
            intent=intent,
            transaction_id=tx.transaction_id,
            executor_receipt_ref=acknowledgement.executor_receipt_ref,
        )
        return self.effects._store_application_commit(row)

    def finalize_rollback(
        self,
        acknowledgement_id: str,
        *,
        verification_receipt_id: str,
    ) -> EngineeringRollbackCompletion:
        acknowledgement = self.journal.rollback_acknowledgement(acknowledgement_id)
        intent = self.effects.rollback_intent(acknowledgement.rollback_intent_id)
        tx = self.transactions.get(acknowledgement.transaction_id)
        if (
            acknowledgement.rollback_intent_digest != intent.digest
            or acknowledgement.transaction_id != intent.transaction_id
            or acknowledgement.patch_ref != intent.patch_ref
            or acknowledgement.patch_digest != intent.patch_digest
            or acknowledgement.rollback_operation_ref != intent.rollback_operation_ref
            or acknowledgement.target_state_digest != intent.target_state_digest
            or acknowledgement.observed_state_digest != intent.target_state_digest
            or tx.patch_ref != intent.patch_ref
            or tx.patch_digest != intent.patch_digest
        ):
            raise ValueError("rollback acknowledgement finalization lineage mismatch")

        try:
            verification = self.effects.rollback_verification(verification_receipt_id)
        except KeyError as exc:
            raise PermissionError("rollback finalization requires known independent verification") from exc
        if (
            not verification.passed
            or verification.decision is not EngineeringRollbackDecision.VERIFIED
            or verification.rollback_intent_id != intent.intent_id
            or verification.rollback_intent_digest != intent.digest
            or verification.transaction_id != intent.transaction_id
            or verification.restored_state_digest != acknowledgement.target_state_digest
        ):
            raise PermissionError("rollback acknowledgement does not match independent verification")

        completion = self.effects.complete_rollback(
            intent.intent_id,
            verification_receipt_id=verification.receipt_id,
        )
        if (
            completion.rollback_intent_id != intent.intent_id
            or completion.rollback_intent_digest != intent.digest
            or completion.transaction_id != acknowledgement.transaction_id
            or completion.rollback_operation_ref != acknowledgement.rollback_operation_ref
            or completion.target_state_digest != acknowledgement.target_state_digest
        ):
            raise ValueError("rollback acknowledgement conflicts with completion lineage")
        return completion


__all__ = ("EngineeringEffectFinalizer",)
