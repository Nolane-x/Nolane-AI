from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering import EngineeringPhase, PatchTransactionLedger
from nolane.external_core.software_engineering_validity import EngineeringMutationAuthorityReceipt


PARENT_COMPONENT_ID = "external.software_engineering.control"
PROTOCOL_ID = "external.software_engineering.effects"
PROTOCOL_VERSION = "0.1.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _refs(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


class EngineeringEffectDecision(str, Enum):
    PREPARED = "prepared"
    COMMITTED = "committed"


class EngineeringRollbackDecision(str, Enum):
    PREPARED = "prepared"
    VERIFIED = "verified"
    BLOCKED = "blocked"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class EngineeringApplicationIntent:
    intent_id: str
    transaction_id: str
    patch_ref: str
    patch_digest: str
    mutation_authority_receipt_id: str
    mutation_authority_receipt_digest: str
    application_ref: str
    authorized: bool
    decision: EngineeringEffectDecision
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.intent_id, "application intent id"),
            (self.transaction_id, "transaction id"),
            (self.patch_ref, "patch ref"),
            (self.patch_digest, "patch digest"),
            (self.mutation_authority_receipt_id, "mutation authority receipt id"),
            (self.mutation_authority_receipt_digest, "mutation authority receipt digest"),
            (self.application_ref, "application ref"),
            (self.digest, "application intent digest"),
        ):
            _text(value, field=field)
        if not self.authorized or self.decision is not EngineeringEffectDecision.PREPARED:
            raise ValueError("application intent must represent prepared authorized mutation")
        if self.authority != "mutation_scope_only":
            raise ValueError("application intent cannot grant broader authority")

    @property
    def idempotency_key(self) -> str:
        return self.intent_id

    def payload(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "mutation_authority_receipt_id": self.mutation_authority_receipt_id,
            "mutation_authority_receipt_digest": self.mutation_authority_receipt_digest,
            "application_ref": self.application_ref,
            "authorized": self.authorized,
            "decision": self.decision.value,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"intent_id": self.intent_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringApplicationIntent":
        row = cls(
            intent_id=_text(state["intent_id"], field="application intent id"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            mutation_authority_receipt_id=_text(state["mutation_authority_receipt_id"], field="mutation authority receipt id"),
            mutation_authority_receipt_digest=_text(state["mutation_authority_receipt_digest"], field="mutation authority receipt digest"),
            application_ref=_text(state["application_ref"], field="application ref"),
            authorized=bool(state["authorized"]),
            decision=EngineeringEffectDecision(str(state["decision"])),
            authority=_text(state["authority"], field="application intent authority"),
            digest=_text(state["digest"], field="application intent digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.intent_id != f"eng-application-intent-{expected[:20]}":
            raise ValueError("application intent digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringApplicationCommit:
    commit_id: str
    intent_id: str
    intent_digest: str
    transaction_id: str
    application_ref: str
    executor_receipt_ref: str
    decision: EngineeringEffectDecision
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.commit_id, "application commit id"),
            (self.intent_id, "application intent id"),
            (self.intent_digest, "application intent digest"),
            (self.transaction_id, "transaction id"),
            (self.application_ref, "application ref"),
            (self.executor_receipt_ref, "executor receipt ref"),
            (self.digest, "application commit digest"),
        ):
            _text(value, field=field)
        if self.decision is not EngineeringEffectDecision.COMMITTED:
            raise ValueError("application commit must be committed")
        if self.authority != "mutation_scope_only":
            raise ValueError("application commit cannot grant broader authority")

    def payload(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "intent_digest": self.intent_digest,
            "transaction_id": self.transaction_id,
            "application_ref": self.application_ref,
            "executor_receipt_ref": self.executor_receipt_ref,
            "decision": self.decision.value,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"commit_id": self.commit_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringApplicationCommit":
        row = cls(
            commit_id=_text(state["commit_id"], field="application commit id"),
            intent_id=_text(state["intent_id"], field="application intent id"),
            intent_digest=_text(state["intent_digest"], field="application intent digest"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            application_ref=_text(state["application_ref"], field="application ref"),
            executor_receipt_ref=_text(state["executor_receipt_ref"], field="executor receipt ref"),
            decision=EngineeringEffectDecision(str(state["decision"])),
            authority=_text(state["authority"], field="application commit authority"),
            digest=_text(state["digest"], field="application commit digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.commit_id != f"eng-application-commit-{expected[:20]}":
            raise ValueError("application commit digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringRollbackIntent:
    intent_id: str
    transaction_id: str
    patch_ref: str
    patch_digest: str
    application_commit_id: str
    application_commit_digest: str
    rollback_artifact_ref: str
    rollback_operation_ref: str
    reason: str
    target_state_digest: str
    decision: EngineeringRollbackDecision
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.intent_id, "rollback intent id"),
            (self.transaction_id, "transaction id"),
            (self.patch_ref, "patch ref"),
            (self.patch_digest, "patch digest"),
            (self.application_commit_id, "application commit id"),
            (self.application_commit_digest, "application commit digest"),
            (self.rollback_artifact_ref, "rollback artifact ref"),
            (self.rollback_operation_ref, "rollback operation ref"),
            (self.reason, "rollback reason"),
            (self.target_state_digest, "target state digest"),
            (self.digest, "rollback intent digest"),
        ):
            _text(value, field=field)
        if self.decision is not EngineeringRollbackDecision.PREPARED:
            raise ValueError("rollback intent must be prepared")
        if self.authority != "recovery_scope_only":
            raise ValueError("rollback intent cannot grant broader authority")

    @property
    def idempotency_key(self) -> str:
        return self.intent_id

    def payload(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "application_commit_id": self.application_commit_id,
            "application_commit_digest": self.application_commit_digest,
            "rollback_artifact_ref": self.rollback_artifact_ref,
            "rollback_operation_ref": self.rollback_operation_ref,
            "reason": self.reason,
            "target_state_digest": self.target_state_digest,
            "decision": self.decision.value,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"intent_id": self.intent_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringRollbackIntent":
        row = cls(
            intent_id=_text(state["intent_id"], field="rollback intent id"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            application_commit_id=_text(state["application_commit_id"], field="application commit id"),
            application_commit_digest=_text(state["application_commit_digest"], field="application commit digest"),
            rollback_artifact_ref=_text(state["rollback_artifact_ref"], field="rollback artifact ref"),
            rollback_operation_ref=_text(state["rollback_operation_ref"], field="rollback operation ref"),
            reason=_text(state["reason"], field="rollback reason"),
            target_state_digest=_text(state["target_state_digest"], field="target state digest"),
            decision=EngineeringRollbackDecision(str(state["decision"])),
            authority=_text(state["authority"], field="rollback intent authority"),
            digest=_text(state["digest"], field="rollback intent digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.intent_id != f"eng-rollback-intent-{expected[:20]}":
            raise ValueError("rollback intent digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringRollbackVerificationReceipt:
    receipt_id: str
    rollback_intent_id: str
    rollback_intent_digest: str
    transaction_id: str
    verifier_agent_id: str
    verifier_region: str
    restored_state_digest: str
    evidence_refs: tuple[str, ...]
    passed: bool
    decision: EngineeringRollbackDecision
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.receipt_id, "rollback verification receipt id"),
            (self.rollback_intent_id, "rollback intent id"),
            (self.rollback_intent_digest, "rollback intent digest"),
            (self.transaction_id, "transaction id"),
            (self.verifier_agent_id, "rollback verifier agent"),
            (self.verifier_region, "rollback verifier region"),
            (self.restored_state_digest, "restored state digest"),
            (self.digest, "rollback verification digest"),
        ):
            _text(value, field=field)
        if not self.evidence_refs:
            raise ValueError("rollback verification requires evidence refs")
        expected = EngineeringRollbackDecision.VERIFIED if self.passed else EngineeringRollbackDecision.BLOCKED
        if self.decision is not expected:
            raise ValueError("rollback verification decision contradicts pass state")
        if self.authority != "recovery_scope_only":
            raise ValueError("rollback verification cannot grant broader authority")
        if self.passed and self.verifier_region != "verification-testing":
            raise PermissionError("successful rollback verification requires verification-testing authority")

    def payload(self) -> dict[str, Any]:
        return {
            "rollback_intent_id": self.rollback_intent_id,
            "rollback_intent_digest": self.rollback_intent_digest,
            "transaction_id": self.transaction_id,
            "verifier_agent_id": self.verifier_agent_id,
            "verifier_region": self.verifier_region,
            "restored_state_digest": self.restored_state_digest,
            "evidence_refs": list(self.evidence_refs),
            "passed": self.passed,
            "decision": self.decision.value,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringRollbackVerificationReceipt":
        row = cls(
            receipt_id=_text(state["receipt_id"], field="rollback verification receipt id"),
            rollback_intent_id=_text(state["rollback_intent_id"], field="rollback intent id"),
            rollback_intent_digest=_text(state["rollback_intent_digest"], field="rollback intent digest"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            verifier_agent_id=_text(state["verifier_agent_id"], field="rollback verifier agent"),
            verifier_region=_text(state["verifier_region"], field="rollback verifier region"),
            restored_state_digest=_text(state["restored_state_digest"], field="restored state digest"),
            evidence_refs=_refs(tuple(state.get("evidence_refs", ()))),
            passed=bool(state["passed"]),
            decision=EngineeringRollbackDecision(str(state["decision"])),
            authority=_text(state["authority"], field="rollback verification authority"),
            digest=_text(state["digest"], field="rollback verification digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f"eng-rollback-verification-{expected[:20]}":
            raise ValueError("rollback verification digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringRollbackCompletion:
    completion_id: str
    rollback_intent_id: str
    rollback_intent_digest: str
    verification_receipt_id: str
    verification_receipt_digest: str
    transaction_id: str
    rollback_operation_ref: str
    target_state_digest: str
    decision: EngineeringRollbackDecision
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.completion_id, "rollback completion id"),
            (self.rollback_intent_id, "rollback intent id"),
            (self.rollback_intent_digest, "rollback intent digest"),
            (self.verification_receipt_id, "rollback verification receipt id"),
            (self.verification_receipt_digest, "rollback verification receipt digest"),
            (self.transaction_id, "transaction id"),
            (self.rollback_operation_ref, "rollback operation ref"),
            (self.target_state_digest, "target state digest"),
            (self.digest, "rollback completion digest"),
        ):
            _text(value, field=field)
        if self.decision is not EngineeringRollbackDecision.COMPLETED:
            raise ValueError("rollback completion must be completed")
        if self.authority != "recovery_scope_only":
            raise ValueError("rollback completion cannot grant broader authority")

    def payload(self) -> dict[str, Any]:
        return {
            "rollback_intent_id": self.rollback_intent_id,
            "rollback_intent_digest": self.rollback_intent_digest,
            "verification_receipt_id": self.verification_receipt_id,
            "verification_receipt_digest": self.verification_receipt_digest,
            "transaction_id": self.transaction_id,
            "rollback_operation_ref": self.rollback_operation_ref,
            "target_state_digest": self.target_state_digest,
            "decision": self.decision.value,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"completion_id": self.completion_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringRollbackCompletion":
        row = cls(
            completion_id=_text(state["completion_id"], field="rollback completion id"),
            rollback_intent_id=_text(state["rollback_intent_id"], field="rollback intent id"),
            rollback_intent_digest=_text(state["rollback_intent_digest"], field="rollback intent digest"),
            verification_receipt_id=_text(state["verification_receipt_id"], field="rollback verification receipt id"),
            verification_receipt_digest=_text(state["verification_receipt_digest"], field="rollback verification receipt digest"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            rollback_operation_ref=_text(state["rollback_operation_ref"], field="rollback operation ref"),
            target_state_digest=_text(state["target_state_digest"], field="target state digest"),
            decision=EngineeringRollbackDecision(str(state["decision"])),
            authority=_text(state["authority"], field="rollback completion authority"),
            digest=_text(state["digest"], field="rollback completion digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.completion_id != f"eng-rollback-completion-{expected[:20]}":
            raise ValueError("rollback completion digest/id mismatch")
        return row


class EngineeringEffectLedger:
    """Idempotent external-effect protocol for F application and rollback.

    F does not execute external effects. It issues deterministic intent identities
    for executors to use as idempotency keys, records the executor receipt that
    committed the effect, and requires independent proof before a rollback may
    become terminal. This gives crash/retry semantics without expanding F into
    executor or release authority.
    """

    _PRE_ROLLBACK_PHASES = {
        EngineeringPhase.APPLIED,
        EngineeringPhase.OUTCOME_OBSERVED,
        EngineeringPhase.POSTCONDITIONS_VERIFIED,
        EngineeringPhase.CANDIDATE_READY,
        EngineeringPhase.QUARANTINED,
    }

    def __init__(self, *, transactions: PatchTransactionLedger, mutation_authority: Any) -> None:
        self.transactions = transactions
        self.mutation_authority = mutation_authority
        self._application_intents: dict[str, EngineeringApplicationIntent] = {}
        self._application_commits: dict[str, EngineeringApplicationCommit] = {}
        self._application_ref_to_intent: dict[str, str] = {}
        self._application_commit_by_intent: dict[str, str] = {}
        self._application_commit_by_transaction: dict[str, str] = {}
        self._rollback_intents: dict[str, EngineeringRollbackIntent] = {}
        self._rollback_operation_to_intent: dict[str, str] = {}
        self._rollback_verifications: dict[str, EngineeringRollbackVerificationReceipt] = {}
        self._rollback_completions: dict[str, EngineeringRollbackCompletion] = {}
        self._rollback_completion_by_intent: dict[str, str] = {}
        self._rollback_completion_by_transaction: dict[str, str] = {}

    def application_intents(self) -> tuple[EngineeringApplicationIntent, ...]:
        return tuple(self._application_intents[key] for key in sorted(self._application_intents))

    def application_commits(self) -> tuple[EngineeringApplicationCommit, ...]:
        return tuple(self._application_commits[key] for key in sorted(self._application_commits))

    def rollback_intents(self) -> tuple[EngineeringRollbackIntent, ...]:
        return tuple(self._rollback_intents[key] for key in sorted(self._rollback_intents))

    def rollback_verifications(self) -> tuple[EngineeringRollbackVerificationReceipt, ...]:
        return tuple(self._rollback_verifications[key] for key in sorted(self._rollback_verifications))

    def rollback_completions(self) -> tuple[EngineeringRollbackCompletion, ...]:
        return tuple(self._rollback_completions[key] for key in sorted(self._rollback_completions))

    def application_intent(self, intent_id: str) -> EngineeringApplicationIntent:
        try:
            return self._application_intents[str(intent_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering application intent: {intent_id}") from exc

    def application_commit(self, commit_id: str) -> EngineeringApplicationCommit:
        try:
            return self._application_commits[str(commit_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering application commit: {commit_id}") from exc

    def rollback_intent(self, intent_id: str) -> EngineeringRollbackIntent:
        try:
            return self._rollback_intents[str(intent_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering rollback intent: {intent_id}") from exc

    def rollback_verification(self, receipt_id: str) -> EngineeringRollbackVerificationReceipt:
        try:
            return self._rollback_verifications[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering rollback verification: {receipt_id}") from exc

    def rollback_completion(self, completion_id: str) -> EngineeringRollbackCompletion:
        try:
            return self._rollback_completions[str(completion_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering rollback completion: {completion_id}") from exc

    def _preapply_reasons(self, transaction_id: str) -> tuple[str, ...]:
        method = getattr(self.mutation_authority, "preapply_reasons", None)
        if method is None:
            return ()
        return tuple(method(transaction_id))

    def _mutation_receipt(self, receipt_id: str) -> EngineeringMutationAuthorityReceipt:
        try:
            row = self.mutation_authority.get(receipt_id)
        except KeyError as exc:
            raise PermissionError("application requires known mutation authority receipt") from exc
        if not isinstance(row, EngineeringMutationAuthorityReceipt):
            raise TypeError("mutation authority ledger returned non-canonical receipt")
        return row

    def prepare_application(
        self,
        *,
        transaction_id: str,
        mutation_authority_receipt_id: str,
        application_ref: str,
    ) -> EngineeringApplicationIntent:
        tx = self.transactions.get(transaction_id)
        if tx.phase is not EngineeringPhase.PRECONDITIONS_VERIFIED:
            raise ValueError("application preparation requires precondition-verified transaction phase")
        receipt = self._mutation_receipt(mutation_authority_receipt_id)
        if (
            not receipt.authorized
            or receipt.transaction_id != tx.transaction_id
            or receipt.patch_ref != tx.patch_ref
            or receipt.patch_digest != tx.patch_digest
        ):
            raise PermissionError("application denied by mutation authority receipt lineage")
        reasons = self._preapply_reasons(tx.transaction_id)
        if reasons:
            raise PermissionError("application denied by live mutation authority: " + ", ".join(reasons))

        app_ref = _text(application_ref, field="application ref")
        payload = {
            "transaction_id": tx.transaction_id,
            "patch_ref": tx.patch_ref,
            "patch_digest": tx.patch_digest,
            "mutation_authority_receipt_id": receipt.receipt_id,
            "mutation_authority_receipt_digest": receipt.digest,
            "application_ref": app_ref,
            "authorized": True,
            "decision": EngineeringEffectDecision.PREPARED.value,
            "authority": "mutation_scope_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringApplicationIntent(
            intent_id=f"eng-application-intent-{digest[:20]}",
            transaction_id=tx.transaction_id,
            patch_ref=tx.patch_ref,
            patch_digest=tx.patch_digest,
            mutation_authority_receipt_id=receipt.receipt_id,
            mutation_authority_receipt_digest=receipt.digest,
            application_ref=app_ref,
            authorized=True,
            decision=EngineeringEffectDecision.PREPARED,
            authority="mutation_scope_only",
            digest=digest,
        )
        prior_intent_id = self._application_ref_to_intent.get(app_ref)
        if prior_intent_id is not None and prior_intent_id != row.intent_id:
            raise ValueError("application ref cannot be rebound to another application intent")
        existing = self._application_intents.get(row.intent_id)
        if existing is not None and existing != row:
            raise ValueError("application intent id cannot be rebound")
        self._application_intents[row.intent_id] = row
        self._application_ref_to_intent[app_ref] = row.intent_id
        return existing or row

    def _build_application_commit(
        self,
        *,
        intent: EngineeringApplicationIntent,
        transaction_id: str,
        executor_receipt_ref: str,
    ) -> EngineeringApplicationCommit:
        payload = {
            "intent_id": intent.intent_id,
            "intent_digest": intent.digest,
            "transaction_id": transaction_id,
            "application_ref": intent.application_ref,
            "executor_receipt_ref": executor_receipt_ref,
            "decision": EngineeringEffectDecision.COMMITTED.value,
            "authority": "mutation_scope_only",
        }
        digest = canonical_digest(payload)
        return EngineeringApplicationCommit(
            commit_id=f"eng-application-commit-{digest[:20]}",
            intent_id=intent.intent_id,
            intent_digest=intent.digest,
            transaction_id=transaction_id,
            application_ref=intent.application_ref,
            executor_receipt_ref=executor_receipt_ref,
            decision=EngineeringEffectDecision.COMMITTED,
            authority="mutation_scope_only",
            digest=digest,
        )

    def _store_application_commit(self, row: EngineeringApplicationCommit) -> EngineeringApplicationCommit:
        prior_intent = self._application_commit_by_intent.get(row.intent_id)
        if prior_intent is not None and prior_intent != row.commit_id:
            raise ValueError("application intent cannot have multiple commits")
        prior_tx = self._application_commit_by_transaction.get(row.transaction_id)
        if prior_tx is not None and prior_tx != row.commit_id:
            raise ValueError("engineering transaction cannot have multiple application commits")
        existing = self._application_commits.get(row.commit_id)
        if existing is not None and existing != row:
            raise ValueError("application commit id cannot be rebound")
        self._application_commits[row.commit_id] = row
        self._application_commit_by_intent[row.intent_id] = row.commit_id
        self._application_commit_by_transaction[row.transaction_id] = row.commit_id
        return existing or row

    def commit_application(self, intent_id: str, *, executor_receipt_ref: str) -> EngineeringApplicationCommit:
        intent = self.application_intent(intent_id)
        executor_ref = _text(executor_receipt_ref, field="executor receipt ref")
        prior_commit_id = self._application_commit_by_intent.get(intent.intent_id)
        if prior_commit_id is not None:
            existing = self.application_commit(prior_commit_id)
            if existing.executor_receipt_ref != executor_ref:
                raise ValueError("application intent executor receipt cannot be rebound")
            return existing

        tx = self.transactions.get(intent.transaction_id)
        if (
            tx.transaction_id != intent.transaction_id
            or tx.patch_ref != intent.patch_ref
            or tx.patch_digest != intent.patch_digest
        ):
            raise ValueError("application intent transaction lineage mismatch")
        receipt = self._mutation_receipt(intent.mutation_authority_receipt_id)
        if (
            receipt.digest != intent.mutation_authority_receipt_digest
            or not receipt.authorized
            or receipt.transaction_id != tx.transaction_id
            or receipt.patch_ref != tx.patch_ref
            or receipt.patch_digest != tx.patch_digest
        ):
            raise PermissionError("application mutation authority receipt changed or is not authorized for transaction lineage")

        if tx.phase is EngineeringPhase.APPLIED:
            if tx.application_ref != intent.application_ref:
                raise ValueError("applied transaction application ref does not match application intent")
            row = self._build_application_commit(
                intent=intent,
                transaction_id=tx.transaction_id,
                executor_receipt_ref=executor_ref,
            )
            return self._store_application_commit(row)

        if tx.phase is not EngineeringPhase.PRECONDITIONS_VERIFIED:
            raise ValueError("application commit requires precondition-verified or matching applied transaction phase")
        reasons = self._preapply_reasons(tx.transaction_id)
        if reasons:
            raise PermissionError("application denied by live mutation authority: " + ", ".join(reasons))

        row = self._build_application_commit(
            intent=intent,
            transaction_id=tx.transaction_id,
            executor_receipt_ref=executor_ref,
        )
        prior_tx = self._application_commit_by_transaction.get(tx.transaction_id)
        if prior_tx is not None and prior_tx != row.commit_id:
            raise ValueError("engineering transaction cannot have multiple application commits")

        self.transactions.mark_applied(tx.transaction_id, application_ref=intent.application_ref)
        return self._store_application_commit(row)

    def application_commit_for_transaction(self, transaction_id: str) -> EngineeringApplicationCommit | None:
        commit_id = self._application_commit_by_transaction.get(str(transaction_id))
        return None if commit_id is None else self._application_commits[commit_id]

    def prepare_rollback(
        self,
        *,
        transaction_id: str,
        rollback_operation_ref: str,
        reason: str,
        target_state_digest: str,
    ) -> EngineeringRollbackIntent:
        tx = self.transactions.get(transaction_id)
        if tx.phase not in self._PRE_ROLLBACK_PHASES:
            raise ValueError("rollback preparation requires an applied recoverable transaction phase")
        commit = self.application_commit_for_transaction(tx.transaction_id)
        if commit is None:
            raise ValueError("rollback requires application commit lineage")
        operation_ref = _text(rollback_operation_ref, field="rollback operation ref")
        why = _text(reason, field="rollback reason")
        target = _text(target_state_digest, field="target state digest")
        payload = {
            "transaction_id": tx.transaction_id,
            "patch_ref": tx.patch_ref,
            "patch_digest": tx.patch_digest,
            "application_commit_id": commit.commit_id,
            "application_commit_digest": commit.digest,
            "rollback_artifact_ref": tx.rollback_artifact_ref,
            "rollback_operation_ref": operation_ref,
            "reason": why,
            "target_state_digest": target,
            "decision": EngineeringRollbackDecision.PREPARED.value,
            "authority": "recovery_scope_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringRollbackIntent(
            intent_id=f"eng-rollback-intent-{digest[:20]}",
            transaction_id=tx.transaction_id,
            patch_ref=tx.patch_ref,
            patch_digest=tx.patch_digest,
            application_commit_id=commit.commit_id,
            application_commit_digest=commit.digest,
            rollback_artifact_ref=tx.rollback_artifact_ref,
            rollback_operation_ref=operation_ref,
            reason=why,
            target_state_digest=target,
            decision=EngineeringRollbackDecision.PREPARED,
            authority="recovery_scope_only",
            digest=digest,
        )
        prior_intent_id = self._rollback_operation_to_intent.get(operation_ref)
        if prior_intent_id is not None and prior_intent_id != row.intent_id:
            raise ValueError("rollback operation ref cannot be rebound")
        existing = self._rollback_intents.get(row.intent_id)
        if existing is not None and existing != row:
            raise ValueError("rollback intent id cannot be rebound")
        self._rollback_intents[row.intent_id] = row
        self._rollback_operation_to_intent[operation_ref] = row.intent_id
        return existing or row

    def _producer_agents_for_rollback(self, intent: EngineeringRollbackIntent) -> tuple[str, ...]:
        commit = self.application_commit(intent.application_commit_id)
        app_intent = self.application_intent(commit.intent_id)
        mutation = self._mutation_receipt(app_intent.mutation_authority_receipt_id)
        binding_id = mutation.claim_binding_id
        if binding_id is None:
            return ()
        bindings = getattr(self.mutation_authority, "claim_bindings", None)
        if bindings is None:
            return ()
        binding = bindings.get(binding_id)
        return tuple(sorted({str(snapshot.agent_id) for snapshot in binding.claim_snapshots}))

    def _validate_successful_rollback_verifier(
        self,
        *,
        intent: EngineeringRollbackIntent,
        verifier_agent_id: str,
        verifier_region: str,
    ) -> None:
        if verifier_agent_id in self._producer_agents_for_rollback(intent):
            raise PermissionError("successful rollback verification forbids self-verification")
        if verifier_region != "verification-testing":
            raise PermissionError("successful rollback verification requires verification-testing authority")

    def verify_rollback(
        self,
        intent_id: str,
        *,
        verifier_agent_id: str,
        verifier_region: str,
        restored_state_digest: str,
        evidence_refs: tuple[str, ...],
        passed: bool,
    ) -> EngineeringRollbackVerificationReceipt:
        intent = self.rollback_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        if tx.phase not in self._PRE_ROLLBACK_PHASES:
            raise ValueError("rollback verification requires an applied recoverable transaction phase")
        verifier = _text(verifier_agent_id, field="rollback verifier agent")
        region = _text(verifier_region, field="rollback verifier region")
        restored = _text(restored_state_digest, field="restored state digest")
        if restored != intent.target_state_digest:
            raise ValueError("rollback verification target state does not match rollback intent")
        refs = _refs(evidence_refs)
        if not refs:
            raise ValueError("rollback verification requires evidence refs")
        if bool(passed):
            self._validate_successful_rollback_verifier(
                intent=intent,
                verifier_agent_id=verifier,
                verifier_region=region,
            )
        decision = EngineeringRollbackDecision.VERIFIED if bool(passed) else EngineeringRollbackDecision.BLOCKED
        payload = {
            "rollback_intent_id": intent.intent_id,
            "rollback_intent_digest": intent.digest,
            "transaction_id": tx.transaction_id,
            "verifier_agent_id": verifier,
            "verifier_region": region,
            "restored_state_digest": restored,
            "evidence_refs": list(refs),
            "passed": bool(passed),
            "decision": decision.value,
            "authority": "recovery_scope_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringRollbackVerificationReceipt(
            receipt_id=f"eng-rollback-verification-{digest[:20]}",
            rollback_intent_id=intent.intent_id,
            rollback_intent_digest=intent.digest,
            transaction_id=tx.transaction_id,
            verifier_agent_id=verifier,
            verifier_region=region,
            restored_state_digest=restored,
            evidence_refs=refs,
            passed=bool(passed),
            decision=decision,
            authority="recovery_scope_only",
            digest=digest,
        )
        existing = self._rollback_verifications.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("rollback verification receipt cannot be rebound")
        self._rollback_verifications[row.receipt_id] = row
        return existing or row

    def _build_rollback_completion(
        self,
        *,
        intent: EngineeringRollbackIntent,
        verification: EngineeringRollbackVerificationReceipt,
        transaction_id: str,
    ) -> EngineeringRollbackCompletion:
        payload = {
            "rollback_intent_id": intent.intent_id,
            "rollback_intent_digest": intent.digest,
            "verification_receipt_id": verification.receipt_id,
            "verification_receipt_digest": verification.digest,
            "transaction_id": transaction_id,
            "rollback_operation_ref": intent.rollback_operation_ref,
            "target_state_digest": intent.target_state_digest,
            "decision": EngineeringRollbackDecision.COMPLETED.value,
            "authority": "recovery_scope_only",
        }
        digest = canonical_digest(payload)
        return EngineeringRollbackCompletion(
            completion_id=f"eng-rollback-completion-{digest[:20]}",
            rollback_intent_id=intent.intent_id,
            rollback_intent_digest=intent.digest,
            verification_receipt_id=verification.receipt_id,
            verification_receipt_digest=verification.digest,
            transaction_id=transaction_id,
            rollback_operation_ref=intent.rollback_operation_ref,
            target_state_digest=intent.target_state_digest,
            decision=EngineeringRollbackDecision.COMPLETED,
            authority="recovery_scope_only",
            digest=digest,
        )

    def _store_rollback_completion(self, row: EngineeringRollbackCompletion) -> EngineeringRollbackCompletion:
        prior_intent = self._rollback_completion_by_intent.get(row.rollback_intent_id)
        if prior_intent is not None and prior_intent != row.completion_id:
            raise ValueError("rollback intent cannot have multiple completions")
        prior_tx = self._rollback_completion_by_transaction.get(row.transaction_id)
        if prior_tx is not None and prior_tx != row.completion_id:
            raise ValueError("engineering transaction cannot have multiple rollback completions")
        existing = self._rollback_completions.get(row.completion_id)
        if existing is not None and existing != row:
            raise ValueError("rollback completion id cannot be rebound")
        self._rollback_completions[row.completion_id] = row
        self._rollback_completion_by_intent[row.rollback_intent_id] = row.completion_id
        self._rollback_completion_by_transaction[row.transaction_id] = row.completion_id
        return existing or row

    def complete_rollback(self, intent_id: str, *, verification_receipt_id: str) -> EngineeringRollbackCompletion:
        intent = self.rollback_intent(intent_id)
        prior_completion_id = self._rollback_completion_by_intent.get(intent.intent_id)
        if prior_completion_id is not None:
            existing = self.rollback_completion(prior_completion_id)
            if existing.verification_receipt_id != str(verification_receipt_id):
                raise ValueError("rollback completion verification receipt cannot be rebound")
            return existing
        try:
            verification = self.rollback_verification(verification_receipt_id)
        except KeyError as exc:
            raise PermissionError("rollback completion requires known verification receipt") from exc
        if (
            not verification.passed
            or verification.decision is not EngineeringRollbackDecision.VERIFIED
            or verification.rollback_intent_id != intent.intent_id
            or verification.rollback_intent_digest != intent.digest
            or verification.transaction_id != intent.transaction_id
            or verification.restored_state_digest != intent.target_state_digest
        ):
            raise PermissionError("rollback verification is not verified for this rollback intent")
        self._validate_successful_rollback_verifier(
            intent=intent,
            verifier_agent_id=verification.verifier_agent_id,
            verifier_region=verification.verifier_region,
        )
        tx = self.transactions.get(intent.transaction_id)
        if (
            tx.transaction_id != intent.transaction_id
            or tx.patch_ref != intent.patch_ref
            or tx.patch_digest != intent.patch_digest
            or tx.rollback_artifact_ref != intent.rollback_artifact_ref
        ):
            raise ValueError("rollback intent transaction lineage mismatch")

        if tx.phase is EngineeringPhase.ROLLED_BACK:
            if tx.rollback_ref != intent.rollback_operation_ref:
                raise ValueError("rolled-back transaction rollback operation ref does not match rollback intent")
            if tx.failure_reason != intent.reason:
                raise ValueError("rolled-back transaction rollback reason does not match rollback intent")
            row = self._build_rollback_completion(
                intent=intent,
                verification=verification,
                transaction_id=tx.transaction_id,
            )
            return self._store_rollback_completion(row)

        if tx.phase not in self._PRE_ROLLBACK_PHASES:
            raise ValueError("rollback completion requires an applied recoverable or matching rolled-back transaction phase")

        row = self._build_rollback_completion(
            intent=intent,
            verification=verification,
            transaction_id=tx.transaction_id,
        )
        prior_tx = self._rollback_completion_by_transaction.get(tx.transaction_id)
        if prior_tx is not None and prior_tx != row.completion_id:
            raise ValueError("engineering transaction cannot have multiple rollback completions")

        self.transactions.rollback(
            tx.transaction_id,
            rollback_ref=intent.rollback_operation_ref,
            reason=intent.reason,
        )
        return self._store_rollback_completion(row)

    def validate_transaction_coverage(self) -> None:
        for tx in self.transactions.transactions():
            commit = self.application_commit_for_transaction(tx.transaction_id)
            if tx.application_ref is not None:
                if commit is None:
                    raise ValueError(f"applied transaction missing application commit: {tx.transaction_id}")
                intent = self.application_intent(commit.intent_id)
                if (
                    commit.transaction_id != tx.transaction_id
                    or commit.application_ref != tx.application_ref
                    or intent.transaction_id != tx.transaction_id
                    or intent.application_ref != tx.application_ref
                ):
                    raise ValueError("application commit transaction lineage mismatch")
            elif commit is not None:
                raise ValueError("unapplied transaction cannot own application commit")

            completion_id = self._rollback_completion_by_transaction.get(tx.transaction_id)
            if tx.phase is EngineeringPhase.ROLLED_BACK:
                if completion_id is None:
                    raise ValueError(f"rolled-back transaction missing rollback completion: {tx.transaction_id}")
                completion = self.rollback_completion(completion_id)
                if (
                    completion.transaction_id != tx.transaction_id
                    or completion.rollback_operation_ref != tx.rollback_ref
                ):
                    raise ValueError("rollback completion transaction lineage mismatch")
            elif completion_id is not None:
                raise ValueError("non-rolled-back transaction cannot own rollback completion")

    def to_state(self) -> dict[str, Any]:
        self.validate_transaction_coverage()
        return {
            "application_intents": [row.to_state() for row in self.application_intents()],
            "application_commits": [row.to_state() for row in self.application_commits()],
            "rollback_intents": [row.to_state() for row in self.rollback_intents()],
            "rollback_verifications": [row.to_state() for row in self.rollback_verifications()],
            "rollback_completions": [row.to_state() for row in self.rollback_completions()],
        }

    @classmethod
    def from_state(
        cls,
        *,
        transactions: PatchTransactionLedger,
        mutation_authority: Any,
        state: Mapping[str, Any],
    ) -> "EngineeringEffectLedger":
        ledger = cls(transactions=transactions, mutation_authority=mutation_authority)

        for value in state.get("application_intents", ()):
            row = EngineeringApplicationIntent.from_state(value)
            tx = transactions.get(row.transaction_id)
            if row.patch_ref != tx.patch_ref or row.patch_digest != tx.patch_digest:
                raise ValueError("application intent transaction lineage mismatch")
            receipt = ledger._mutation_receipt(row.mutation_authority_receipt_id)
            if (
                receipt.digest != row.mutation_authority_receipt_digest
                or receipt.transaction_id != row.transaction_id
                or receipt.patch_ref != row.patch_ref
                or receipt.patch_digest != row.patch_digest
                or not receipt.authorized
            ):
                raise ValueError("application intent mutation-authority lineage mismatch")
            prior_ref = ledger._application_ref_to_intent.get(row.application_ref)
            if prior_ref is not None and prior_ref != row.intent_id:
                raise ValueError("application ref rebound in snapshot")
            existing = ledger._application_intents.get(row.intent_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound application intent")
            ledger._application_intents[row.intent_id] = row
            ledger._application_ref_to_intent[row.application_ref] = row.intent_id

        for value in state.get("application_commits", ()):
            row = EngineeringApplicationCommit.from_state(value)
            intent = ledger.application_intent(row.intent_id)
            tx = transactions.get(row.transaction_id)
            if (
                row.intent_digest != intent.digest
                or row.transaction_id != intent.transaction_id
                or row.application_ref != intent.application_ref
                or tx.application_ref != row.application_ref
            ):
                raise ValueError("application commit intent/transaction lineage mismatch")
            prior_intent = ledger._application_commit_by_intent.get(intent.intent_id)
            if prior_intent is not None and prior_intent != row.commit_id:
                raise ValueError("application intent has multiple commits in snapshot")
            prior_tx = ledger._application_commit_by_transaction.get(tx.transaction_id)
            if prior_tx is not None and prior_tx != row.commit_id:
                raise ValueError("transaction has multiple application commits in snapshot")
            existing = ledger._application_commits.get(row.commit_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound application commit")
            ledger._application_commits[row.commit_id] = row
            ledger._application_commit_by_intent[intent.intent_id] = row.commit_id
            ledger._application_commit_by_transaction[tx.transaction_id] = row.commit_id

        for value in state.get("rollback_intents", ()):
            row = EngineeringRollbackIntent.from_state(value)
            tx = transactions.get(row.transaction_id)
            commit = ledger.application_commit(row.application_commit_id)
            if (
                row.patch_ref != tx.patch_ref
                or row.patch_digest != tx.patch_digest
                or row.application_commit_digest != commit.digest
                or commit.transaction_id != tx.transaction_id
                or row.rollback_artifact_ref != tx.rollback_artifact_ref
            ):
                raise ValueError("rollback intent application/transaction lineage mismatch")
            prior_ref = ledger._rollback_operation_to_intent.get(row.rollback_operation_ref)
            if prior_ref is not None and prior_ref != row.intent_id:
                raise ValueError("rollback operation ref rebound in snapshot")
            existing = ledger._rollback_intents.get(row.intent_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound rollback intent")
            ledger._rollback_intents[row.intent_id] = row
            ledger._rollback_operation_to_intent[row.rollback_operation_ref] = row.intent_id

        for value in state.get("rollback_verifications", ()):
            row = EngineeringRollbackVerificationReceipt.from_state(value)
            intent = ledger.rollback_intent(row.rollback_intent_id)
            if (
                row.rollback_intent_digest != intent.digest
                or row.transaction_id != intent.transaction_id
                or row.restored_state_digest != intent.target_state_digest
            ):
                raise ValueError("rollback verification intent lineage mismatch")
            if row.passed:
                ledger._validate_successful_rollback_verifier(
                    intent=intent,
                    verifier_agent_id=row.verifier_agent_id,
                    verifier_region=row.verifier_region,
                )
            existing = ledger._rollback_verifications.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound rollback verification")
            ledger._rollback_verifications[row.receipt_id] = row

        for value in state.get("rollback_completions", ()):
            row = EngineeringRollbackCompletion.from_state(value)
            intent = ledger.rollback_intent(row.rollback_intent_id)
            verification = ledger.rollback_verification(row.verification_receipt_id)
            tx = transactions.get(row.transaction_id)
            if (
                row.rollback_intent_digest != intent.digest
                or row.verification_receipt_digest != verification.digest
                or not verification.passed
                or verification.decision is not EngineeringRollbackDecision.VERIFIED
                or verification.rollback_intent_id != intent.intent_id
                or row.transaction_id != intent.transaction_id
                or row.rollback_operation_ref != intent.rollback_operation_ref
                or row.target_state_digest != intent.target_state_digest
                or tx.phase is not EngineeringPhase.ROLLED_BACK
                or tx.rollback_ref != row.rollback_operation_ref
            ):
                raise ValueError("rollback completion intent/verification/transaction lineage mismatch")
            ledger._validate_successful_rollback_verifier(
                intent=intent,
                verifier_agent_id=verification.verifier_agent_id,
                verifier_region=verification.verifier_region,
            )
            prior_intent = ledger._rollback_completion_by_intent.get(intent.intent_id)
            if prior_intent is not None and prior_intent != row.completion_id:
                raise ValueError("rollback intent has multiple completions in snapshot")
            prior_tx = ledger._rollback_completion_by_transaction.get(tx.transaction_id)
            if prior_tx is not None and prior_tx != row.completion_id:
                raise ValueError("transaction has multiple rollback completions in snapshot")
            existing = ledger._rollback_completions.get(row.completion_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound rollback completion")
            ledger._rollback_completions[row.completion_id] = row
            ledger._rollback_completion_by_intent[intent.intent_id] = row.completion_id
            ledger._rollback_completion_by_transaction[tx.transaction_id] = row.completion_id

        ledger.validate_transaction_coverage()
        return ledger


__all__ = (
    "EngineeringEffectDecision",
    "EngineeringRollbackDecision",
    "EngineeringApplicationIntent",
    "EngineeringApplicationCommit",
    "EngineeringRollbackIntent",
    "EngineeringRollbackVerificationReceipt",
    "EngineeringRollbackCompletion",
    "EngineeringEffectLedger",
)
