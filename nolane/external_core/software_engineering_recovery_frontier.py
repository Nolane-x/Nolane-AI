from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering import EngineeringPhase, PatchTransactionLedger
from nolane.external_core.software_engineering_effect_dispatch import (
    EngineeringDispatchKind,
    EngineeringEffectDispatchLedger,
)
from nolane.external_core.software_engineering_effect_journal import EngineeringEffectJournal
from nolane.external_core.software_engineering_effects import EngineeringEffectLedger, EngineeringRollbackDecision


PARENT_COMPONENT_ID = "external.software_engineering.control"
PROTOCOL_ID = "external.software_engineering.recovery_frontier"
PROTOCOL_VERSION = "0.1.0"


class EngineeringRecoveryAction(str, Enum):
    READY_TO_DISPATCH = "ready_to_dispatch"
    EXTERNAL_STATUS_REQUIRED = "external_status_required"
    VERIFICATION_REQUIRED = "verification_required"
    LOCAL_FINALIZATION_READY = "local_finalization_ready"
    FINALIZED = "finalized"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class EngineeringRecoveryFrontierReceipt:
    frontier_id: str
    kind: EngineeringDispatchKind
    intent_id: str
    intent_digest: str
    transaction_id: str
    action: EngineeringRecoveryAction
    dispatch_id: str | None
    acknowledgement_id: str | None
    terminal_ref: str | None
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "intent_id": self.intent_id,
            "intent_digest": self.intent_digest,
            "transaction_id": self.transaction_id,
            "action": self.action.value,
            "dispatch_id": self.dispatch_id,
            "acknowledgement_id": self.acknowledgement_id,
            "terminal_ref": self.terminal_ref,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }

    def __post_init__(self) -> None:
        if not self.frontier_id or not self.intent_id or not self.intent_digest or not self.transaction_id or not self.digest:
            raise ValueError("recovery frontier identity/lineage must be explicit")
        if self.authority != "advisory_only":
            raise ValueError("recovery frontier cannot grant execution authority")
        if self.action is EngineeringRecoveryAction.EXTERNAL_STATUS_REQUIRED and self.dispatch_id is None:
            raise ValueError("external-status frontier requires dispatch lineage")
        if self.action in {
            EngineeringRecoveryAction.LOCAL_FINALIZATION_READY,
            EngineeringRecoveryAction.VERIFICATION_REQUIRED,
        } and self.acknowledgement_id is None:
            raise ValueError("acknowledgement-backed frontier requires acknowledgement lineage")
        if self.action is EngineeringRecoveryAction.FINALIZED and self.terminal_ref is None:
            raise ValueError("finalized frontier requires terminal effect reference")


class EngineeringEffectRecoveryFrontier:
    """Read-only current recovery decision over dispatch/journal/effect history."""

    _ROLLBACK_READY_PHASES = {
        EngineeringPhase.APPLIED,
        EngineeringPhase.OUTCOME_OBSERVED,
        EngineeringPhase.POSTCONDITIONS_VERIFIED,
        EngineeringPhase.CANDIDATE_READY,
        EngineeringPhase.QUARANTINED,
    }

    def __init__(
        self,
        *,
        transactions: PatchTransactionLedger,
        effects: EngineeringEffectLedger,
        journal: EngineeringEffectJournal,
        dispatch: EngineeringEffectDispatchLedger,
    ) -> None:
        self.transactions = transactions
        self.effects = effects
        self.journal = journal
        self.dispatch = dispatch

    def _receipt(
        self,
        *,
        kind: EngineeringDispatchKind,
        intent_id: str,
        intent_digest: str,
        transaction_id: str,
        action: EngineeringRecoveryAction,
        dispatch_id: str | None = None,
        acknowledgement_id: str | None = None,
        terminal_ref: str | None = None,
        reasons: tuple[str, ...] = (),
    ) -> EngineeringRecoveryFrontierReceipt:
        payload = {
            "kind": kind.value,
            "intent_id": intent_id,
            "intent_digest": intent_digest,
            "transaction_id": transaction_id,
            "action": action.value,
            "dispatch_id": dispatch_id,
            "acknowledgement_id": acknowledgement_id,
            "terminal_ref": terminal_ref,
            "reasons": list(tuple(sorted(set(reasons)))),
            "authority": "advisory_only",
        }
        digest = canonical_digest(payload)
        return EngineeringRecoveryFrontierReceipt(
            frontier_id=f"eng-recovery-frontier-{digest[:20]}",
            kind=kind,
            intent_id=intent_id,
            intent_digest=intent_digest,
            transaction_id=transaction_id,
            action=action,
            dispatch_id=dispatch_id,
            acknowledgement_id=acknowledgement_id,
            terminal_ref=terminal_ref,
            reasons=tuple(payload["reasons"]),
            authority="advisory_only",
            digest=digest,
        )

    def application(self, intent_id: str) -> EngineeringRecoveryFrontierReceipt:
        intent = self.effects.application_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        commit = self.effects.application_commit_for_transaction(tx.transaction_id)
        dispatch = self.dispatch.application_dispatch_for_intent(intent.intent_id)
        acknowledgement = self.journal.application_acknowledgement_for_transaction(tx.transaction_id)

        if commit is not None:
            return self._receipt(
                kind=EngineeringDispatchKind.APPLICATION,
                intent_id=intent.intent_id,
                intent_digest=intent.digest,
                transaction_id=tx.transaction_id,
                action=EngineeringRecoveryAction.FINALIZED,
                dispatch_id=None if dispatch is None else dispatch.dispatch_id,
                acknowledgement_id=None if acknowledgement is None else acknowledgement.acknowledgement_id,
                terminal_ref=commit.commit_id,
            )
        if acknowledgement is not None:
            return self._receipt(
                kind=EngineeringDispatchKind.APPLICATION,
                intent_id=intent.intent_id,
                intent_digest=intent.digest,
                transaction_id=tx.transaction_id,
                action=EngineeringRecoveryAction.LOCAL_FINALIZATION_READY,
                dispatch_id=None if dispatch is None else dispatch.dispatch_id,
                acknowledgement_id=acknowledgement.acknowledgement_id,
            )
        if dispatch is not None:
            return self._receipt(
                kind=EngineeringDispatchKind.APPLICATION,
                intent_id=intent.intent_id,
                intent_digest=intent.digest,
                transaction_id=tx.transaction_id,
                action=EngineeringRecoveryAction.EXTERNAL_STATUS_REQUIRED,
                dispatch_id=dispatch.dispatch_id,
                reasons=("dispatch_started_without_durable_acknowledgement",),
            )
        if tx.phase is EngineeringPhase.PRECONDITIONS_VERIFIED:
            live_reasons = tuple(getattr(self.effects.mutation_authority, "preapply_reasons", lambda _tx: ())(
                tx.transaction_id
            ))
            if live_reasons:
                return self._receipt(
                    kind=EngineeringDispatchKind.APPLICATION,
                    intent_id=intent.intent_id,
                    intent_digest=intent.digest,
                    transaction_id=tx.transaction_id,
                    action=EngineeringRecoveryAction.BLOCKED,
                    reasons=live_reasons,
                )
            return self._receipt(
                kind=EngineeringDispatchKind.APPLICATION,
                intent_id=intent.intent_id,
                intent_digest=intent.digest,
                transaction_id=tx.transaction_id,
                action=EngineeringRecoveryAction.READY_TO_DISPATCH,
            )
        return self._receipt(
            kind=EngineeringDispatchKind.APPLICATION,
            intent_id=intent.intent_id,
            intent_digest=intent.digest,
            transaction_id=tx.transaction_id,
            action=EngineeringRecoveryAction.BLOCKED,
            reasons=(f"application_transaction_phase:{tx.phase.value}",),
        )

    def _verified_rollback_exists(self, intent: Any) -> bool:
        rows = tuple(getattr(self.effects, "_rollback_verifications", {}).values())
        for row in rows:
            if (
                row.rollback_intent_id == intent.intent_id
                and row.rollback_intent_digest == intent.digest
                and row.transaction_id == intent.transaction_id
                and row.restored_state_digest == intent.target_state_digest
                and row.passed
                and row.decision is EngineeringRollbackDecision.VERIFIED
                and row.verifier_region == "verification-testing"
            ):
                return True
        return False

    def rollback(self, intent_id: str) -> EngineeringRecoveryFrontierReceipt:
        intent = self.effects.rollback_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        dispatch = self.dispatch.rollback_dispatch_for_intent(intent.intent_id)
        acknowledgement = self.journal.rollback_acknowledgement_for_transaction(tx.transaction_id)
        completion_id = getattr(self.effects, "_rollback_completion_by_transaction", {}).get(tx.transaction_id)

        if completion_id is not None:
            return self._receipt(
                kind=EngineeringDispatchKind.ROLLBACK,
                intent_id=intent.intent_id,
                intent_digest=intent.digest,
                transaction_id=tx.transaction_id,
                action=EngineeringRecoveryAction.FINALIZED,
                dispatch_id=None if dispatch is None else dispatch.dispatch_id,
                acknowledgement_id=None if acknowledgement is None else acknowledgement.acknowledgement_id,
                terminal_ref=completion_id,
            )
        if acknowledgement is not None:
            action = (
                EngineeringRecoveryAction.LOCAL_FINALIZATION_READY
                if self._verified_rollback_exists(intent)
                else EngineeringRecoveryAction.VERIFICATION_REQUIRED
            )
            return self._receipt(
                kind=EngineeringDispatchKind.ROLLBACK,
                intent_id=intent.intent_id,
                intent_digest=intent.digest,
                transaction_id=tx.transaction_id,
                action=action,
                dispatch_id=None if dispatch is None else dispatch.dispatch_id,
                acknowledgement_id=acknowledgement.acknowledgement_id,
                reasons=(() if action is EngineeringRecoveryAction.LOCAL_FINALIZATION_READY else ("independent_rollback_verification_required",)),
            )
        if dispatch is not None:
            return self._receipt(
                kind=EngineeringDispatchKind.ROLLBACK,
                intent_id=intent.intent_id,
                intent_digest=intent.digest,
                transaction_id=tx.transaction_id,
                action=EngineeringRecoveryAction.EXTERNAL_STATUS_REQUIRED,
                dispatch_id=dispatch.dispatch_id,
                reasons=("rollback_dispatch_started_without_durable_acknowledgement",),
            )
        if tx.phase in self._ROLLBACK_READY_PHASES:
            return self._receipt(
                kind=EngineeringDispatchKind.ROLLBACK,
                intent_id=intent.intent_id,
                intent_digest=intent.digest,
                transaction_id=tx.transaction_id,
                action=EngineeringRecoveryAction.READY_TO_DISPATCH,
            )
        return self._receipt(
            kind=EngineeringDispatchKind.ROLLBACK,
            intent_id=intent.intent_id,
            intent_digest=intent.digest,
            transaction_id=tx.transaction_id,
            action=EngineeringRecoveryAction.BLOCKED,
            reasons=(f"rollback_transaction_phase:{tx.phase.value}",),
        )


__all__ = (
    "PARENT_COMPONENT_ID",
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "EngineeringRecoveryAction",
    "EngineeringRecoveryFrontierReceipt",
    "EngineeringEffectRecoveryFrontier",
)
