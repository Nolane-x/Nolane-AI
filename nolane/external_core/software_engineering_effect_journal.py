from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering import EngineeringPhase, PatchTransactionLedger
from nolane.external_core.software_engineering_effects import EngineeringEffectLedger


PARENT_COMPONENT_ID = "external.software_engineering.control"
PROTOCOL_ID = "external.software_engineering.effect_journal"
PROTOCOL_VERSION = "0.1.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


class EngineeringEffectObservationDecision(str, Enum):
    ACKNOWLEDGED = "acknowledged"


@dataclass(frozen=True, slots=True)
class EngineeringApplicationAcknowledgement:
    acknowledgement_id: str
    intent_id: str
    intent_digest: str
    transaction_id: str
    patch_ref: str
    patch_digest: str
    application_ref: str
    executor_namespace: str
    executor_receipt_ref: str
    observed_state_digest: str
    decision: EngineeringEffectObservationDecision
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.acknowledgement_id, "application acknowledgement id"),
            (self.intent_id, "application intent id"),
            (self.intent_digest, "application intent digest"),
            (self.transaction_id, "transaction id"),
            (self.patch_ref, "patch ref"),
            (self.patch_digest, "patch digest"),
            (self.application_ref, "application ref"),
            (self.executor_namespace, "executor namespace"),
            (self.executor_receipt_ref, "executor receipt ref"),
            (self.observed_state_digest, "observed state digest"),
            (self.digest, "application acknowledgement digest"),
        ):
            _text(value, field=field)
        if self.decision is not EngineeringEffectObservationDecision.ACKNOWLEDGED:
            raise ValueError("application acknowledgement must be acknowledged")
        if self.authority != "observation_only":
            raise ValueError("application acknowledgement cannot grant execution authority")

    def payload(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "intent_digest": self.intent_digest,
            "transaction_id": self.transaction_id,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "application_ref": self.application_ref,
            "executor_namespace": self.executor_namespace,
            "executor_receipt_ref": self.executor_receipt_ref,
            "observed_state_digest": self.observed_state_digest,
            "decision": self.decision.value,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"acknowledgement_id": self.acknowledgement_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringApplicationAcknowledgement":
        row = cls(
            acknowledgement_id=_text(state["acknowledgement_id"], field="application acknowledgement id"),
            intent_id=_text(state["intent_id"], field="application intent id"),
            intent_digest=_text(state["intent_digest"], field="application intent digest"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            application_ref=_text(state["application_ref"], field="application ref"),
            executor_namespace=_text(state["executor_namespace"], field="executor namespace"),
            executor_receipt_ref=_text(state["executor_receipt_ref"], field="executor receipt ref"),
            observed_state_digest=_text(state["observed_state_digest"], field="observed state digest"),
            decision=EngineeringEffectObservationDecision(str(state["decision"])),
            authority=_text(state["authority"], field="application acknowledgement authority"),
            digest=_text(state["digest"], field="application acknowledgement digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.acknowledgement_id != f"eng-application-ack-{expected[:20]}":
            raise ValueError("application acknowledgement digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringRollbackAcknowledgement:
    acknowledgement_id: str
    rollback_intent_id: str
    rollback_intent_digest: str
    transaction_id: str
    patch_ref: str
    patch_digest: str
    rollback_operation_ref: str
    target_state_digest: str
    executor_namespace: str
    executor_receipt_ref: str
    observed_state_digest: str
    decision: EngineeringEffectObservationDecision
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.acknowledgement_id, "rollback acknowledgement id"),
            (self.rollback_intent_id, "rollback intent id"),
            (self.rollback_intent_digest, "rollback intent digest"),
            (self.transaction_id, "transaction id"),
            (self.patch_ref, "patch ref"),
            (self.patch_digest, "patch digest"),
            (self.rollback_operation_ref, "rollback operation ref"),
            (self.target_state_digest, "target state digest"),
            (self.executor_namespace, "executor namespace"),
            (self.executor_receipt_ref, "executor receipt ref"),
            (self.observed_state_digest, "observed state digest"),
            (self.digest, "rollback acknowledgement digest"),
        ):
            _text(value, field=field)
        if self.decision is not EngineeringEffectObservationDecision.ACKNOWLEDGED:
            raise ValueError("rollback acknowledgement must be acknowledged")
        if self.authority != "observation_only":
            raise ValueError("rollback acknowledgement cannot grant recovery authority")
        if self.observed_state_digest != self.target_state_digest:
            raise ValueError("rollback acknowledgement observed state must match declared target state")

    def payload(self) -> dict[str, Any]:
        return {
            "rollback_intent_id": self.rollback_intent_id,
            "rollback_intent_digest": self.rollback_intent_digest,
            "transaction_id": self.transaction_id,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "rollback_operation_ref": self.rollback_operation_ref,
            "target_state_digest": self.target_state_digest,
            "executor_namespace": self.executor_namespace,
            "executor_receipt_ref": self.executor_receipt_ref,
            "observed_state_digest": self.observed_state_digest,
            "decision": self.decision.value,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"acknowledgement_id": self.acknowledgement_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringRollbackAcknowledgement":
        row = cls(
            acknowledgement_id=_text(state["acknowledgement_id"], field="rollback acknowledgement id"),
            rollback_intent_id=_text(state["rollback_intent_id"], field="rollback intent id"),
            rollback_intent_digest=_text(state["rollback_intent_digest"], field="rollback intent digest"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            rollback_operation_ref=_text(state["rollback_operation_ref"], field="rollback operation ref"),
            target_state_digest=_text(state["target_state_digest"], field="target state digest"),
            executor_namespace=_text(state["executor_namespace"], field="executor namespace"),
            executor_receipt_ref=_text(state["executor_receipt_ref"], field="executor receipt ref"),
            observed_state_digest=_text(state["observed_state_digest"], field="observed state digest"),
            decision=EngineeringEffectObservationDecision(str(state["decision"])),
            authority=_text(state["authority"], field="rollback acknowledgement authority"),
            digest=_text(state["digest"], field="rollback acknowledgement digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.acknowledgement_id != f"eng-rollback-ack-{expected[:20]}":
            raise ValueError("rollback acknowledgement digest/id mismatch")
        return row


class EngineeringEffectJournal:
    """Durable observation ledger between external acknowledgements and local finalization.

    The journal never executes effects and never grants mutation/recovery authority.
    It records exactly what F observed from an external executor under immutable
    intent/transaction lineage so restart recovery can finalize local state without
    asking the external executor to perform the effect again.
    """

    _APPLICATION_PHASES = {
        EngineeringPhase.PRECONDITIONS_VERIFIED,
        EngineeringPhase.APPLIED,
    }
    _ROLLBACK_PHASES = {
        EngineeringPhase.APPLIED,
        EngineeringPhase.OUTCOME_OBSERVED,
        EngineeringPhase.POSTCONDITIONS_VERIFIED,
        EngineeringPhase.CANDIDATE_READY,
        EngineeringPhase.QUARANTINED,
        EngineeringPhase.ROLLED_BACK,
    }

    def __init__(self, *, transactions: PatchTransactionLedger, effects: EngineeringEffectLedger) -> None:
        self.transactions = transactions
        self.effects = effects
        self._application_acknowledgements: dict[str, EngineeringApplicationAcknowledgement] = {}
        self._application_by_intent: dict[str, str] = {}
        self._application_by_transaction: dict[str, str] = {}
        self._application_by_operation: dict[str, str] = {}
        self._rollback_acknowledgements: dict[str, EngineeringRollbackAcknowledgement] = {}
        self._rollback_by_intent: dict[str, str] = {}
        self._rollback_by_transaction: dict[str, str] = {}
        self._rollback_by_operation: dict[str, str] = {}
        self._executor_receipt_to_acknowledgement: dict[str, str] = {}

    def application_acknowledgements(self) -> tuple[EngineeringApplicationAcknowledgement, ...]:
        return tuple(self._application_acknowledgements[key] for key in sorted(self._application_acknowledgements))

    def rollback_acknowledgements(self) -> tuple[EngineeringRollbackAcknowledgement, ...]:
        return tuple(self._rollback_acknowledgements[key] for key in sorted(self._rollback_acknowledgements))

    def application_acknowledgement(self, acknowledgement_id: str) -> EngineeringApplicationAcknowledgement:
        try:
            return self._application_acknowledgements[str(acknowledgement_id)]
        except KeyError as exc:
            raise KeyError(f"unknown application acknowledgement: {acknowledgement_id}") from exc

    def rollback_acknowledgement(self, acknowledgement_id: str) -> EngineeringRollbackAcknowledgement:
        try:
            return self._rollback_acknowledgements[str(acknowledgement_id)]
        except KeyError as exc:
            raise KeyError(f"unknown rollback acknowledgement: {acknowledgement_id}") from exc

    def application_acknowledgement_for_transaction(self, transaction_id: str) -> EngineeringApplicationAcknowledgement | None:
        acknowledgement_id = self._application_by_transaction.get(str(transaction_id))
        return None if acknowledgement_id is None else self.application_acknowledgement(acknowledgement_id)

    def rollback_acknowledgement_for_transaction(self, transaction_id: str) -> EngineeringRollbackAcknowledgement | None:
        acknowledgement_id = self._rollback_by_transaction.get(str(transaction_id))
        return None if acknowledgement_id is None else self.rollback_acknowledgement(acknowledgement_id)

    def _assert_executor_receipt_available(self, executor_receipt_ref: str, acknowledgement_id: str) -> None:
        prior = self._executor_receipt_to_acknowledgement.get(executor_receipt_ref)
        if prior is not None and prior != acknowledgement_id:
            raise ValueError("executor receipt ref cannot be rebound across effect acknowledgements")

    def acknowledge_application(
        self,
        intent_id: str,
        *,
        executor_namespace: str,
        executor_receipt_ref: str,
        observed_state_digest: str,
    ) -> EngineeringApplicationAcknowledgement:
        intent = self.effects.application_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        if tx.phase not in self._APPLICATION_PHASES:
            raise ValueError("application acknowledgement requires precondition-verified or applied transaction phase")
        if (
            tx.transaction_id != intent.transaction_id
            or tx.patch_ref != intent.patch_ref
            or tx.patch_digest != intent.patch_digest
        ):
            raise ValueError("application acknowledgement intent/transaction lineage mismatch")

        namespace = _text(executor_namespace, field="executor namespace")
        receipt_ref = _text(executor_receipt_ref, field="executor receipt ref")
        observed = _text(observed_state_digest, field="observed state digest")
        payload = {
            "intent_id": intent.intent_id,
            "intent_digest": intent.digest,
            "transaction_id": tx.transaction_id,
            "patch_ref": tx.patch_ref,
            "patch_digest": tx.patch_digest,
            "application_ref": intent.application_ref,
            "executor_namespace": namespace,
            "executor_receipt_ref": receipt_ref,
            "observed_state_digest": observed,
            "decision": EngineeringEffectObservationDecision.ACKNOWLEDGED.value,
            "authority": "observation_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringApplicationAcknowledgement(
            acknowledgement_id=f"eng-application-ack-{digest[:20]}",
            intent_id=intent.intent_id,
            intent_digest=intent.digest,
            transaction_id=tx.transaction_id,
            patch_ref=tx.patch_ref,
            patch_digest=tx.patch_digest,
            application_ref=intent.application_ref,
            executor_namespace=namespace,
            executor_receipt_ref=receipt_ref,
            observed_state_digest=observed,
            decision=EngineeringEffectObservationDecision.ACKNOWLEDGED,
            authority="observation_only",
            digest=digest,
        )

        prior_intent = self._application_by_intent.get(intent.intent_id)
        if prior_intent is not None:
            existing = self.application_acknowledgement(prior_intent)
            if existing != row:
                raise ValueError("application acknowledgement intent cannot be rebound")
            return existing
        prior_tx = self._application_by_transaction.get(tx.transaction_id)
        if prior_tx is not None and prior_tx != row.acknowledgement_id:
            raise ValueError("application acknowledgement transaction cannot be rebound")
        prior_operation = self._application_by_operation.get(intent.application_ref)
        if prior_operation is not None and prior_operation != row.acknowledgement_id:
            raise ValueError("application acknowledgement operation cannot be rebound")
        self._assert_executor_receipt_available(receipt_ref, row.acknowledgement_id)

        self._application_acknowledgements[row.acknowledgement_id] = row
        self._application_by_intent[intent.intent_id] = row.acknowledgement_id
        self._application_by_transaction[tx.transaction_id] = row.acknowledgement_id
        self._application_by_operation[intent.application_ref] = row.acknowledgement_id
        self._executor_receipt_to_acknowledgement[receipt_ref] = row.acknowledgement_id
        return row

    def acknowledge_rollback(
        self,
        intent_id: str,
        *,
        executor_namespace: str,
        executor_receipt_ref: str,
        observed_state_digest: str,
    ) -> EngineeringRollbackAcknowledgement:
        intent = self.effects.rollback_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        if tx.phase not in self._ROLLBACK_PHASES:
            raise ValueError("rollback acknowledgement requires recoverable or rolled-back transaction phase")
        if (
            tx.transaction_id != intent.transaction_id
            or tx.patch_ref != intent.patch_ref
            or tx.patch_digest != intent.patch_digest
            or tx.rollback_artifact_ref != intent.rollback_artifact_ref
        ):
            raise ValueError("rollback acknowledgement intent/transaction lineage mismatch")

        namespace = _text(executor_namespace, field="executor namespace")
        receipt_ref = _text(executor_receipt_ref, field="executor receipt ref")
        observed = _text(observed_state_digest, field="observed state digest")
        if observed != intent.target_state_digest:
            raise ValueError("rollback acknowledgement observed state does not match target state")
        payload = {
            "rollback_intent_id": intent.intent_id,
            "rollback_intent_digest": intent.digest,
            "transaction_id": tx.transaction_id,
            "patch_ref": tx.patch_ref,
            "patch_digest": tx.patch_digest,
            "rollback_operation_ref": intent.rollback_operation_ref,
            "target_state_digest": intent.target_state_digest,
            "executor_namespace": namespace,
            "executor_receipt_ref": receipt_ref,
            "observed_state_digest": observed,
            "decision": EngineeringEffectObservationDecision.ACKNOWLEDGED.value,
            "authority": "observation_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringRollbackAcknowledgement(
            acknowledgement_id=f"eng-rollback-ack-{digest[:20]}",
            rollback_intent_id=intent.intent_id,
            rollback_intent_digest=intent.digest,
            transaction_id=tx.transaction_id,
            patch_ref=tx.patch_ref,
            patch_digest=tx.patch_digest,
            rollback_operation_ref=intent.rollback_operation_ref,
            target_state_digest=intent.target_state_digest,
            executor_namespace=namespace,
            executor_receipt_ref=receipt_ref,
            observed_state_digest=observed,
            decision=EngineeringEffectObservationDecision.ACKNOWLEDGED,
            authority="observation_only",
            digest=digest,
        )

        prior_intent = self._rollback_by_intent.get(intent.intent_id)
        if prior_intent is not None:
            existing = self.rollback_acknowledgement(prior_intent)
            if existing != row:
                raise ValueError("rollback acknowledgement intent cannot be rebound")
            return existing
        prior_tx = self._rollback_by_transaction.get(tx.transaction_id)
        if prior_tx is not None and prior_tx != row.acknowledgement_id:
            raise ValueError("rollback acknowledgement transaction cannot be rebound")
        prior_operation = self._rollback_by_operation.get(intent.rollback_operation_ref)
        if prior_operation is not None and prior_operation != row.acknowledgement_id:
            raise ValueError("rollback acknowledgement operation cannot be rebound")
        self._assert_executor_receipt_available(receipt_ref, row.acknowledgement_id)

        self._rollback_acknowledgements[row.acknowledgement_id] = row
        self._rollback_by_intent[intent.intent_id] = row.acknowledgement_id
        self._rollback_by_transaction[tx.transaction_id] = row.acknowledgement_id
        self._rollback_by_operation[intent.rollback_operation_ref] = row.acknowledgement_id
        self._executor_receipt_to_acknowledgement[receipt_ref] = row.acknowledgement_id
        return row

    def validate_effect_coverage(self) -> None:
        for acknowledgement in self.application_acknowledgements():
            intent = self.effects.application_intent(acknowledgement.intent_id)
            tx = self.transactions.get(acknowledgement.transaction_id)
            if (
                acknowledgement.intent_digest != intent.digest
                or acknowledgement.transaction_id != intent.transaction_id
                or acknowledgement.patch_ref != intent.patch_ref
                or acknowledgement.patch_digest != intent.patch_digest
                or acknowledgement.application_ref != intent.application_ref
                or tx.transaction_id != intent.transaction_id
                or tx.patch_ref != intent.patch_ref
                or tx.patch_digest != intent.patch_digest
            ):
                raise ValueError("application acknowledgement canonical lineage mismatch")
            commit = self.effects.application_commit_for_transaction(tx.transaction_id)
            if commit is None:
                if tx.phase is not EngineeringPhase.PRECONDITIONS_VERIFIED:
                    raise ValueError("unfinalized application acknowledgement requires precondition-verified transaction")
            elif (
                commit.intent_id != intent.intent_id
                or commit.intent_digest != intent.digest
                or commit.application_ref != acknowledgement.application_ref
                or commit.executor_receipt_ref != acknowledgement.executor_receipt_ref
            ):
                raise ValueError("application acknowledgement/commit lineage mismatch")

        for commit in self.effects.application_commits():
            acknowledgement = self.application_acknowledgement_for_transaction(commit.transaction_id)
            if acknowledgement is None:
                raise ValueError(f"application commit missing durable acknowledgement: {commit.transaction_id}")
            if (
                acknowledgement.intent_id != commit.intent_id
                or acknowledgement.intent_digest != commit.intent_digest
                or acknowledgement.application_ref != commit.application_ref
                or acknowledgement.executor_receipt_ref != commit.executor_receipt_ref
            ):
                raise ValueError("application commit durable acknowledgement mismatch")

        for acknowledgement in self.rollback_acknowledgements():
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
                or tx.transaction_id != intent.transaction_id
            ):
                raise ValueError("rollback acknowledgement canonical lineage mismatch")
            completion_id = getattr(self.effects, "_rollback_completion_by_transaction", {}).get(tx.transaction_id)
            if completion_id is not None:
                completion = self.effects.rollback_completion(completion_id)
                if (
                    completion.rollback_intent_id != intent.intent_id
                    or completion.rollback_intent_digest != intent.digest
                    or completion.rollback_operation_ref != acknowledgement.rollback_operation_ref
                    or completion.target_state_digest != acknowledgement.target_state_digest
                ):
                    raise ValueError("rollback acknowledgement/completion lineage mismatch")

        for completion in self.effects.rollback_completions():
            acknowledgement = self.rollback_acknowledgement_for_transaction(completion.transaction_id)
            if acknowledgement is None:
                raise ValueError(f"rollback completion missing durable acknowledgement: {completion.transaction_id}")
            if (
                acknowledgement.rollback_intent_id != completion.rollback_intent_id
                or acknowledgement.rollback_intent_digest != completion.rollback_intent_digest
                or acknowledgement.rollback_operation_ref != completion.rollback_operation_ref
                or acknowledgement.target_state_digest != completion.target_state_digest
            ):
                raise ValueError("rollback completion durable acknowledgement mismatch")

    def _state_payload(self) -> dict[str, Any]:
        self.validate_effect_coverage()
        return {
            "protocol_id": PROTOCOL_ID,
            "protocol_version": PROTOCOL_VERSION,
            "application_acknowledgements": [row.to_state() for row in self.application_acknowledgements()],
            "rollback_acknowledgements": [row.to_state() for row in self.rollback_acknowledgements()],
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
    ) -> "EngineeringEffectJournal":
        if _text(state["protocol_id"], field="effect journal protocol id") != PROTOCOL_ID:
            raise ValueError("effect journal protocol id mismatch")
        if _text(state["protocol_version"], field="effect journal protocol version") != PROTOCOL_VERSION:
            raise ValueError("effect journal protocol version mismatch")
        supplied_digest = _text(state["digest"], field="effect journal state digest")
        payload = {key: value for key, value in state.items() if key != "digest"}
        if canonical_digest(payload) != supplied_digest:
            raise ValueError("effect journal snapshot digest mismatch")

        journal = cls(transactions=transactions, effects=effects)
        for value in state.get("application_acknowledgements", ()):
            row = EngineeringApplicationAcknowledgement.from_state(value)
            intent = effects.application_intent(row.intent_id)
            tx = transactions.get(row.transaction_id)
            if (
                row.intent_digest != intent.digest
                or row.transaction_id != intent.transaction_id
                or row.patch_ref != intent.patch_ref
                or row.patch_digest != intent.patch_digest
                or row.application_ref != intent.application_ref
                or tx.patch_ref != row.patch_ref
                or tx.patch_digest != row.patch_digest
            ):
                raise ValueError("application acknowledgement snapshot lineage mismatch")
            prior_intent = journal._application_by_intent.get(row.intent_id)
            if prior_intent is not None and prior_intent != row.acknowledgement_id:
                raise ValueError("application acknowledgement intent rebound in snapshot")
            prior_tx = journal._application_by_transaction.get(row.transaction_id)
            if prior_tx is not None and prior_tx != row.acknowledgement_id:
                raise ValueError("application acknowledgement transaction rebound in snapshot")
            prior_operation = journal._application_by_operation.get(row.application_ref)
            if prior_operation is not None and prior_operation != row.acknowledgement_id:
                raise ValueError("application acknowledgement operation rebound in snapshot")
            journal._assert_executor_receipt_available(row.executor_receipt_ref, row.acknowledgement_id)
            existing = journal._application_acknowledgements.get(row.acknowledgement_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound application acknowledgement")
            journal._application_acknowledgements[row.acknowledgement_id] = row
            journal._application_by_intent[row.intent_id] = row.acknowledgement_id
            journal._application_by_transaction[row.transaction_id] = row.acknowledgement_id
            journal._application_by_operation[row.application_ref] = row.acknowledgement_id
            journal._executor_receipt_to_acknowledgement[row.executor_receipt_ref] = row.acknowledgement_id

        for value in state.get("rollback_acknowledgements", ()):
            row = EngineeringRollbackAcknowledgement.from_state(value)
            intent = effects.rollback_intent(row.rollback_intent_id)
            tx = transactions.get(row.transaction_id)
            if (
                row.rollback_intent_digest != intent.digest
                or row.transaction_id != intent.transaction_id
                or row.patch_ref != intent.patch_ref
                or row.patch_digest != intent.patch_digest
                or row.rollback_operation_ref != intent.rollback_operation_ref
                or row.target_state_digest != intent.target_state_digest
                or row.observed_state_digest != intent.target_state_digest
                or tx.patch_ref != row.patch_ref
                or tx.patch_digest != row.patch_digest
            ):
                raise ValueError("rollback acknowledgement snapshot lineage mismatch")
            prior_intent = journal._rollback_by_intent.get(row.rollback_intent_id)
            if prior_intent is not None and prior_intent != row.acknowledgement_id:
                raise ValueError("rollback acknowledgement intent rebound in snapshot")
            prior_tx = journal._rollback_by_transaction.get(row.transaction_id)
            if prior_tx is not None and prior_tx != row.acknowledgement_id:
                raise ValueError("rollback acknowledgement transaction rebound in snapshot")
            prior_operation = journal._rollback_by_operation.get(row.rollback_operation_ref)
            if prior_operation is not None and prior_operation != row.acknowledgement_id:
                raise ValueError("rollback acknowledgement operation rebound in snapshot")
            journal._assert_executor_receipt_available(row.executor_receipt_ref, row.acknowledgement_id)
            existing = journal._rollback_acknowledgements.get(row.acknowledgement_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound rollback acknowledgement")
            journal._rollback_acknowledgements[row.acknowledgement_id] = row
            journal._rollback_by_intent[row.rollback_intent_id] = row.acknowledgement_id
            journal._rollback_by_transaction[row.transaction_id] = row.acknowledgement_id
            journal._rollback_by_operation[row.rollback_operation_ref] = row.acknowledgement_id
            journal._executor_receipt_to_acknowledgement[row.executor_receipt_ref] = row.acknowledgement_id

        journal.validate_effect_coverage()
        if journal.to_state() != dict(state):
            raise ValueError("effect journal restore is not state-identical")
        return journal


__all__ = (
    "EngineeringEffectObservationDecision",
    "EngineeringApplicationAcknowledgement",
    "EngineeringRollbackAcknowledgement",
    "EngineeringEffectJournal",
)
