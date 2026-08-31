from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering import EngineeringPhase, PatchTransactionLedger
from nolane.external_core.software_engineering_effects import EngineeringEffectLedger


PARENT_COMPONENT_ID = "external.software_engineering.control"
PROTOCOL_ID = "external.software_engineering.effect_dispatch"
PROTOCOL_VERSION = "0.1.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


class EngineeringDispatchKind(str, Enum):
    APPLICATION = "application"
    ROLLBACK = "rollback"


class EngineeringDispatchDecision(str, Enum):
    STARTED = "dispatch_started"


class EngineeringDispatchOrigin(str, Enum):
    PRE_DISPATCH = "pre_dispatch"
    OBSERVED_WITH_ACK = "observed_with_ack"


@dataclass(frozen=True, slots=True)
class EngineeringEffectDispatchRecord:
    dispatch_id: str
    kind: EngineeringDispatchKind
    intent_id: str
    intent_digest: str
    transaction_id: str
    patch_ref: str
    patch_digest: str
    operation_ref: str
    executor_namespace: str
    origin: EngineeringDispatchOrigin
    target_state_digest: str | None
    decision: EngineeringDispatchDecision
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.dispatch_id, "dispatch id"),
            (self.intent_id, "dispatch intent id"),
            (self.intent_digest, "dispatch intent digest"),
            (self.transaction_id, "dispatch transaction id"),
            (self.patch_ref, "dispatch patch ref"),
            (self.patch_digest, "dispatch patch digest"),
            (self.operation_ref, "dispatch operation ref"),
            (self.executor_namespace, "dispatch executor namespace"),
            (self.digest, "dispatch digest"),
        ):
            _text(value, field=field)
        if self.kind is EngineeringDispatchKind.APPLICATION:
            if self.target_state_digest is not None:
                raise ValueError("application dispatch cannot declare rollback target state")
        else:
            _text(self.target_state_digest, field="rollback dispatch target state digest")
        if self.decision is not EngineeringDispatchDecision.STARTED:
            raise ValueError("effect dispatch record must represent dispatch-started state")
        if self.authority != "coordination_only":
            raise ValueError("effect dispatch record cannot grant execution authority")

    def payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "intent_id": self.intent_id,
            "intent_digest": self.intent_digest,
            "transaction_id": self.transaction_id,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "operation_ref": self.operation_ref,
            "executor_namespace": self.executor_namespace,
            "origin": self.origin.value,
            "target_state_digest": self.target_state_digest,
            "decision": self.decision.value,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"dispatch_id": self.dispatch_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringEffectDispatchRecord":
        target_raw = state.get("target_state_digest")
        row = cls(
            dispatch_id=_text(state["dispatch_id"], field="dispatch id"),
            kind=EngineeringDispatchKind(str(state["kind"])),
            intent_id=_text(state["intent_id"], field="dispatch intent id"),
            intent_digest=_text(state["intent_digest"], field="dispatch intent digest"),
            transaction_id=_text(state["transaction_id"], field="dispatch transaction id"),
            patch_ref=_text(state["patch_ref"], field="dispatch patch ref"),
            patch_digest=_text(state["patch_digest"], field="dispatch patch digest"),
            operation_ref=_text(state["operation_ref"], field="dispatch operation ref"),
            executor_namespace=_text(state["executor_namespace"], field="dispatch executor namespace"),
            origin=EngineeringDispatchOrigin(str(state["origin"])),
            target_state_digest=(None if target_raw is None else _text(target_raw, field="dispatch target state digest")),
            decision=EngineeringDispatchDecision(str(state["decision"])),
            authority=_text(state["authority"], field="dispatch authority"),
            digest=_text(state["digest"], field="dispatch digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.dispatch_id != f"eng-effect-dispatch-{expected[:20]}":
            raise ValueError("effect dispatch digest/id mismatch")
        return row


class EngineeringEffectDispatchLedger:
    """Durable marker that a prepared effect crossed the local dispatch boundary.

    A marker is coordination history only. It is deliberately not an execution
    capability. Once a PRE_DISPATCH marker exists without an acknowledgement,
    callers must query/reconcile external status instead of automatically
    dispatching the effect again.
    """

    def __init__(self, *, transactions: PatchTransactionLedger, effects: EngineeringEffectLedger) -> None:
        self.transactions = transactions
        self.effects = effects
        self._records: dict[str, EngineeringEffectDispatchRecord] = {}
        self._by_intent: dict[str, str] = {}
        self._by_transaction_kind: dict[tuple[EngineeringDispatchKind, str], str] = {}
        self._by_operation_kind: dict[tuple[EngineeringDispatchKind, str], str] = {}

    def records(self) -> tuple[EngineeringEffectDispatchRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def get(self, dispatch_id: str) -> EngineeringEffectDispatchRecord:
        try:
            return self._records[str(dispatch_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering effect dispatch: {dispatch_id}") from exc

    def dispatch_for_intent(self, intent_id: str) -> EngineeringEffectDispatchRecord | None:
        dispatch_id = self._by_intent.get(str(intent_id))
        return None if dispatch_id is None else self.get(dispatch_id)

    def application_dispatch_for_intent(self, intent_id: str) -> EngineeringEffectDispatchRecord | None:
        row = self.dispatch_for_intent(intent_id)
        if row is not None and row.kind is not EngineeringDispatchKind.APPLICATION:
            raise ValueError("intent is bound to non-application dispatch")
        return row

    def rollback_dispatch_for_intent(self, intent_id: str) -> EngineeringEffectDispatchRecord | None:
        row = self.dispatch_for_intent(intent_id)
        if row is not None and row.kind is not EngineeringDispatchKind.ROLLBACK:
            raise ValueError("intent is bound to non-rollback dispatch")
        return row

    def application_dispatch_for_transaction(self, transaction_id: str) -> EngineeringEffectDispatchRecord | None:
        dispatch_id = self._by_transaction_kind.get((EngineeringDispatchKind.APPLICATION, str(transaction_id)))
        return None if dispatch_id is None else self.get(dispatch_id)

    def rollback_dispatch_for_transaction(self, transaction_id: str) -> EngineeringEffectDispatchRecord | None:
        dispatch_id = self._by_transaction_kind.get((EngineeringDispatchKind.ROLLBACK, str(transaction_id)))
        return None if dispatch_id is None else self.get(dispatch_id)

    def _store(self, row: EngineeringEffectDispatchRecord) -> EngineeringEffectDispatchRecord:
        existing_by_intent = self._by_intent.get(row.intent_id)
        if existing_by_intent is not None:
            existing = self.get(existing_by_intent)
            if (
                existing.kind != row.kind
                or existing.transaction_id != row.transaction_id
                or existing.intent_digest != row.intent_digest
                or existing.operation_ref != row.operation_ref
                or existing.executor_namespace != row.executor_namespace
                or existing.target_state_digest != row.target_state_digest
            ):
                raise ValueError("effect dispatch intent cannot be rebound")
            return existing

        tx_key = (row.kind, row.transaction_id)
        prior_tx = self._by_transaction_kind.get(tx_key)
        if prior_tx is not None and prior_tx != row.dispatch_id:
            raise ValueError("engineering transaction cannot bind multiple dispatches of same effect kind")
        operation_key = (row.kind, row.operation_ref)
        prior_operation = self._by_operation_kind.get(operation_key)
        if prior_operation is not None and prior_operation != row.dispatch_id:
            raise ValueError("effect dispatch operation ref cannot be rebound")
        existing = self._records.get(row.dispatch_id)
        if existing is not None and existing != row:
            raise ValueError("effect dispatch id cannot be rebound")

        self._records[row.dispatch_id] = row
        self._by_intent[row.intent_id] = row.dispatch_id
        self._by_transaction_kind[tx_key] = row.dispatch_id
        self._by_operation_kind[operation_key] = row.dispatch_id
        return existing or row

    def _build(
        self,
        *,
        kind: EngineeringDispatchKind,
        intent_id: str,
        intent_digest: str,
        transaction_id: str,
        patch_ref: str,
        patch_digest: str,
        operation_ref: str,
        executor_namespace: str,
        origin: EngineeringDispatchOrigin,
        target_state_digest: str | None,
    ) -> EngineeringEffectDispatchRecord:
        payload = {
            "kind": kind.value,
            "intent_id": intent_id,
            "intent_digest": intent_digest,
            "transaction_id": transaction_id,
            "patch_ref": patch_ref,
            "patch_digest": patch_digest,
            "operation_ref": operation_ref,
            "executor_namespace": executor_namespace,
            "origin": origin.value,
            "target_state_digest": target_state_digest,
            "decision": EngineeringDispatchDecision.STARTED.value,
            "authority": "coordination_only",
        }
        digest = canonical_digest(payload)
        return EngineeringEffectDispatchRecord(
            dispatch_id=f"eng-effect-dispatch-{digest[:20]}",
            kind=kind,
            intent_id=intent_id,
            intent_digest=intent_digest,
            transaction_id=transaction_id,
            patch_ref=patch_ref,
            patch_digest=patch_digest,
            operation_ref=operation_ref,
            executor_namespace=executor_namespace,
            origin=origin,
            target_state_digest=target_state_digest,
            decision=EngineeringDispatchDecision.STARTED,
            authority="coordination_only",
            digest=digest,
        )

    def record_application(
        self,
        intent_id: str,
        *,
        executor_namespace: str,
        origin: EngineeringDispatchOrigin,
    ) -> EngineeringEffectDispatchRecord:
        intent = self.effects.application_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        namespace = _text(executor_namespace, field="dispatch executor namespace")
        if (
            tx.transaction_id != intent.transaction_id
            or tx.patch_ref != intent.patch_ref
            or tx.patch_digest != intent.patch_digest
        ):
            raise ValueError("application dispatch intent/transaction lineage mismatch")
        if origin is EngineeringDispatchOrigin.PRE_DISPATCH:
            if tx.phase is not EngineeringPhase.PRECONDITIONS_VERIFIED:
                raise ValueError("application pre-dispatch marker requires precondition-verified transaction")
            if self.effects.application_commit_for_transaction(tx.transaction_id) is not None:
                raise ValueError("finalized application cannot start dispatch")
        elif tx.phase not in {EngineeringPhase.PRECONDITIONS_VERIFIED, EngineeringPhase.APPLIED}:
            raise ValueError("application acknowledgement backfill requires precondition-verified or applied transaction")

        row = self._build(
            kind=EngineeringDispatchKind.APPLICATION,
            intent_id=intent.intent_id,
            intent_digest=intent.digest,
            transaction_id=tx.transaction_id,
            patch_ref=tx.patch_ref,
            patch_digest=tx.patch_digest,
            operation_ref=intent.application_ref,
            executor_namespace=namespace,
            origin=origin,
            target_state_digest=None,
        )
        return self._store(row)

    def record_rollback(
        self,
        intent_id: str,
        *,
        executor_namespace: str,
        origin: EngineeringDispatchOrigin,
    ) -> EngineeringEffectDispatchRecord:
        intent = self.effects.rollback_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        namespace = _text(executor_namespace, field="dispatch executor namespace")
        if (
            tx.transaction_id != intent.transaction_id
            or tx.patch_ref != intent.patch_ref
            or tx.patch_digest != intent.patch_digest
            or tx.rollback_artifact_ref != intent.rollback_artifact_ref
        ):
            raise ValueError("rollback dispatch intent/transaction lineage mismatch")
        recoverable = {
            EngineeringPhase.APPLIED,
            EngineeringPhase.OUTCOME_OBSERVED,
            EngineeringPhase.POSTCONDITIONS_VERIFIED,
            EngineeringPhase.CANDIDATE_READY,
            EngineeringPhase.QUARANTINED,
        }
        if origin is EngineeringDispatchOrigin.PRE_DISPATCH:
            if tx.phase not in recoverable:
                raise ValueError("rollback pre-dispatch marker requires recoverable transaction")
            if self.effects.rollback_completions():
                existing_completion = getattr(self.effects, "_rollback_completion_by_transaction", {}).get(tx.transaction_id)
                if existing_completion is not None:
                    raise ValueError("finalized rollback cannot start dispatch")
        elif tx.phase not in recoverable | {EngineeringPhase.ROLLED_BACK}:
            raise ValueError("rollback acknowledgement backfill requires recoverable or rolled-back transaction")

        row = self._build(
            kind=EngineeringDispatchKind.ROLLBACK,
            intent_id=intent.intent_id,
            intent_digest=intent.digest,
            transaction_id=tx.transaction_id,
            patch_ref=tx.patch_ref,
            patch_digest=tx.patch_digest,
            operation_ref=intent.rollback_operation_ref,
            executor_namespace=namespace,
            origin=origin,
            target_state_digest=intent.target_state_digest,
        )
        return self._store(row)

    def validate_lineage(self) -> None:
        for row in self.records():
            tx = self.transactions.get(row.transaction_id)
            if row.kind is EngineeringDispatchKind.APPLICATION:
                intent = self.effects.application_intent(row.intent_id)
                if (
                    row.intent_digest != intent.digest
                    or row.transaction_id != intent.transaction_id
                    or row.patch_ref != intent.patch_ref
                    or row.patch_digest != intent.patch_digest
                    or row.operation_ref != intent.application_ref
                    or row.target_state_digest is not None
                    or tx.patch_ref != row.patch_ref
                    or tx.patch_digest != row.patch_digest
                ):
                    raise ValueError("application dispatch canonical lineage mismatch")
            else:
                intent = self.effects.rollback_intent(row.intent_id)
                if (
                    row.intent_digest != intent.digest
                    or row.transaction_id != intent.transaction_id
                    or row.patch_ref != intent.patch_ref
                    or row.patch_digest != intent.patch_digest
                    or row.operation_ref != intent.rollback_operation_ref
                    or row.target_state_digest != intent.target_state_digest
                    or tx.patch_ref != row.patch_ref
                    or tx.patch_digest != row.patch_digest
                ):
                    raise ValueError("rollback dispatch canonical lineage mismatch")

    def _state_payload(self) -> dict[str, Any]:
        self.validate_lineage()
        return {
            "protocol_id": PROTOCOL_ID,
            "protocol_version": PROTOCOL_VERSION,
            "records": [row.to_state() for row in self.records()],
        }

    def to_state(self) -> dict[str, Any]:
        payload = self._state_payload()
        return {**payload, "digest": canonical_digest(payload)}

    @classmethod
    def from_state(
        cls,
        *,
        transactions: PatchTransactionLedger,
        effects: EngineeringEffectLedger,
        state: Mapping[str, Any],
    ) -> "EngineeringEffectDispatchLedger":
        if _text(state["protocol_id"], field="effect dispatch protocol id") != PROTOCOL_ID:
            raise ValueError("effect dispatch protocol id mismatch")
        if _text(state["protocol_version"], field="effect dispatch protocol version") != PROTOCOL_VERSION:
            raise ValueError("effect dispatch protocol version mismatch")
        supplied_digest = _text(state["digest"], field="effect dispatch state digest")
        payload = {key: value for key, value in state.items() if key != "digest"}
        if canonical_digest(payload) != supplied_digest:
            raise ValueError("effect dispatch snapshot digest mismatch")

        ledger = cls(transactions=transactions, effects=effects)
        for value in state.get("records", ()):
            row = EngineeringEffectDispatchRecord.from_state(value)
            ledger._store(row)
        ledger.validate_lineage()
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID",
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "EngineeringDispatchKind",
    "EngineeringDispatchDecision",
    "EngineeringDispatchOrigin",
    "EngineeringEffectDispatchRecord",
    "EngineeringEffectDispatchLedger",
)
