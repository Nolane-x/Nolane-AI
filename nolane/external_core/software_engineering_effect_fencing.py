from __future__ import annotations

from typing import Any, Mapping

from nolane.external_core.software_engineering import PatchTransactionLedger
from nolane.external_core.software_engineering_effects import (
    EngineeringApplicationIntent,
    EngineeringEffectLedger,
    EngineeringRollbackIntent,
)


PARENT_COMPONENT_ID = "external.software_engineering.control"
PROTOCOL_ID = "external.software_engineering.effect_fencing"
PROTOCOL_VERSION = "0.1.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


class FencedEngineeringEffectLedger(EngineeringEffectLedger):
    """Effect ledger that gives each transaction one immutable dispatch intent.

    The base effects protocol already fences operation/idempotency references and
    terminal commits. This subtype closes the earlier pre-dispatch race where one
    transaction could prepare multiple distinct application or rollback intents
    before any executor acknowledgement existed.

    The transaction indices are derived caches only. They are rebuilt from the
    canonical intent rows during restore and therefore do not change the effects
    serialized state schema or create another authority surface.
    """

    def __init__(self, *, transactions: PatchTransactionLedger, mutation_authority: Any) -> None:
        super().__init__(transactions=transactions, mutation_authority=mutation_authority)
        self._application_intent_by_transaction: dict[str, str] = {}
        self._rollback_intent_by_transaction: dict[str, str] = {}

    def prepare_application(
        self,
        *,
        transaction_id: str,
        mutation_authority_receipt_id: str,
        application_ref: str,
    ) -> EngineeringApplicationIntent:
        tx_id = _text(transaction_id, field="transaction id")
        receipt_id = _text(mutation_authority_receipt_id, field="mutation authority receipt id")
        app_ref = _text(application_ref, field="application ref")
        prior_intent_id = self._application_intent_by_transaction.get(tx_id)
        if prior_intent_id is not None:
            existing = self.application_intent(prior_intent_id)
            if (
                existing.mutation_authority_receipt_id != receipt_id
                or existing.application_ref != app_ref
            ):
                raise ValueError("engineering transaction cannot prepare multiple application intents")
            return existing

        row = super().prepare_application(
            transaction_id=tx_id,
            mutation_authority_receipt_id=receipt_id,
            application_ref=app_ref,
        )
        prior = self._application_intent_by_transaction.get(row.transaction_id)
        if prior is not None and prior != row.intent_id:
            raise ValueError("engineering transaction cannot prepare multiple application intents")
        self._application_intent_by_transaction[row.transaction_id] = row.intent_id
        return row

    def prepare_rollback(
        self,
        *,
        transaction_id: str,
        rollback_operation_ref: str,
        reason: str,
        target_state_digest: str,
    ) -> EngineeringRollbackIntent:
        tx_id = _text(transaction_id, field="transaction id")
        operation_ref = _text(rollback_operation_ref, field="rollback operation ref")
        why = _text(reason, field="rollback reason")
        target = _text(target_state_digest, field="target state digest")
        prior_intent_id = self._rollback_intent_by_transaction.get(tx_id)
        if prior_intent_id is not None:
            existing = self.rollback_intent(prior_intent_id)
            if (
                existing.rollback_operation_ref != operation_ref
                or existing.reason != why
                or existing.target_state_digest != target
            ):
                raise ValueError("engineering transaction cannot prepare multiple rollback intents")
            return existing

        row = super().prepare_rollback(
            transaction_id=tx_id,
            rollback_operation_ref=operation_ref,
            reason=why,
            target_state_digest=target,
        )
        prior = self._rollback_intent_by_transaction.get(row.transaction_id)
        if prior is not None and prior != row.intent_id:
            raise ValueError("engineering transaction cannot prepare multiple rollback intents")
        self._rollback_intent_by_transaction[row.transaction_id] = row.intent_id
        return row

    @classmethod
    def from_state(
        cls,
        *,
        transactions: PatchTransactionLedger,
        mutation_authority: Any,
        state: Mapping[str, Any],
    ) -> "FencedEngineeringEffectLedger":
        ledger = super().from_state(
            transactions=transactions,
            mutation_authority=mutation_authority,
            state=state,
        )
        if not isinstance(ledger, cls):
            raise TypeError("effect fencing restore produced wrong ledger type")

        for row in ledger.application_intents():
            prior = ledger._application_intent_by_transaction.get(row.transaction_id)
            if prior is not None and prior != row.intent_id:
                raise ValueError("transaction has multiple application intents in snapshot")
            ledger._application_intent_by_transaction[row.transaction_id] = row.intent_id

        for row in ledger.rollback_intents():
            prior = ledger._rollback_intent_by_transaction.get(row.transaction_id)
            if prior is not None and prior != row.intent_id:
                raise ValueError("transaction has multiple rollback intents in snapshot")
            ledger._rollback_intent_by_transaction[row.transaction_id] = row.intent_id

        return ledger


__all__ = (
    "PARENT_COMPONENT_ID",
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "FencedEngineeringEffectLedger",
)
