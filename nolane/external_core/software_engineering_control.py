from __future__ import annotations

from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core._software_engineering_control_v06 import (
    CANONICAL_WRITE_AUTHORITY,
    COMPONENT_ID as BASE_COMPONENT_ID,
    COMPONENT_VERSION as BASE_COMPONENT_VERSION,
    EngineeringWorkRecord,
    SoftwareEngineeringControlPlane as _SoftwareEngineeringControlPlaneV06,
)
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering import EngineeringPatchTransaction
from nolane.external_core.software_engineering_effect_fencing import FencedEngineeringEffectLedger
from nolane.external_core.software_engineering_effect_journal import (
    EngineeringApplicationAcknowledgement,
    EngineeringEffectJournal,
    EngineeringRollbackAcknowledgement,
)
from nolane.external_core.software_engineering_effect_recovery import EngineeringEffectFinalizer
from nolane.external_core.software_engineering_effects import (
    EngineeringApplicationCommit,
    EngineeringRollbackCompletion,
    EngineeringRollbackDecision,
)


COMPONENT_ID = BASE_COMPONENT_ID
COMPONENT_VERSION = "0.7.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


class SoftwareEngineeringControlPlane(_SoftwareEngineeringControlPlaneV06):
    """F control plane with durable external-effect acknowledgement lineage.

    v0.7 of the control compatibility schema composes the established v0.6
    governed engineering lifecycle with transaction-scoped effect-intent fencing,
    an observation-only effect journal and a local-only recovery finalizer. The
    public canonical owner remains this module; the frozen v0.6 class is an
    internal compatibility implementation, not a second write authority.
    """

    def __init__(
        self,
        *,
        claims: CodeClaimLedger,
        effect_journal: EngineeringEffectJournal | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(claims=claims, **kwargs)

        if not isinstance(self.effects, FencedEngineeringEffectLedger):
            self.effects = FencedEngineeringEffectLedger.from_state(
                transactions=self.transactions,
                mutation_authority=self.mutation_authority,
                state=self.effects.to_state(),
            )

        if effect_journal is None:
            self.effect_journal = EngineeringEffectJournal(
                transactions=self.transactions,
                effects=self.effects,
            )
        elif (
            effect_journal.transactions is self.transactions
            and effect_journal.effects is self.effects
        ):
            self.effect_journal = effect_journal
        else:
            self.effect_journal = EngineeringEffectJournal.from_state(
                transactions=self.transactions,
                effects=self.effects,
                state=effect_journal.to_state(),
            )

        if (
            self.effect_journal.transactions is not self.transactions
            or self.effect_journal.effects is not self.effects
        ):
            raise ValueError("effect journal must share canonical transaction/effect ledgers")
        self.effect_finalizer = EngineeringEffectFinalizer(
            transactions=self.transactions,
            effects=self.effects,
            journal=self.effect_journal,
        )

    def acknowledge_application(
        self,
        intent_id: str,
        *,
        executor_namespace: str,
        executor_receipt_ref: str,
        observed_state_digest: str,
    ) -> EngineeringApplicationAcknowledgement:
        """Record an executor acknowledgement as an observation-only fact.

        The caller is reporting an external effect that it observed. This method
        therefore records history and does not pretend F can undo the fact if
        live claim state changes between executor execution and acknowledgement.
        New dispatch integrations must use the prepared, mutation-authorized
        application intent as the executor boundary.
        """
        return self.effect_journal.acknowledge_application(
            intent_id,
            executor_namespace=executor_namespace,
            executor_receipt_ref=executor_receipt_ref,
            observed_state_digest=observed_state_digest,
        )

    def finalize_application(self, acknowledgement_id: str) -> EngineeringApplicationCommit:
        return self.effect_finalizer.finalize_application(acknowledgement_id)

    def commit_application(
        self,
        intent_id: str,
        *,
        executor_receipt_ref: str,
    ) -> EngineeringApplicationCommit:
        """Compatibility one-call path backed by the v0.8 durable journal."""
        intent = self.effects.application_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        receipt_ref = _text(executor_receipt_ref, field="executor receipt ref")

        existing_commit = self.effects.application_commit_for_transaction(tx.transaction_id)
        if existing_commit is not None:
            if existing_commit.intent_id != intent.intent_id:
                raise ValueError("application intent conflicts with existing transaction commit")
            if existing_commit.executor_receipt_ref != receipt_ref:
                raise ValueError("application intent executor receipt cannot be rebound")
            return existing_commit

        existing_ack = self.effect_journal.application_acknowledgement_for_transaction(tx.transaction_id)
        if existing_ack is not None and existing_ack.executor_receipt_ref != receipt_ref:
            raise ValueError("application intent executor receipt cannot be rebound")
        if existing_ack is None:
            # In this compatibility path the call is still the mutation action
            # boundary, so preserve the v0.6 live revalidation before recording
            # a new executor acknowledgement. Explicit acknowledge_application()
            # instead records an already-observed external fact.
            reasons = tuple(self.mutation_authority.preapply_reasons(tx.transaction_id))
            if reasons and tx.application_ref is None:
                raise PermissionError("application denied by live mutation authority: " + ", ".join(reasons))

        acknowledgement = self.effect_journal.acknowledge_application(
            intent.intent_id,
            executor_namespace="compatibility.effects.v0.1",
            executor_receipt_ref=receipt_ref,
            observed_state_digest=canonical_digest(
                {"compatibility_application_executor_receipt_ref": receipt_ref}
            ),
        )
        return self.effect_finalizer.finalize_application(acknowledgement.acknowledgement_id)

    def mark_applied(
        self,
        transaction_id: str,
        *,
        application_ref: str,
        mutation_authority_receipt_id: str | None = None,
    ) -> EngineeringPatchTransaction:
        """Legacy adapter that now routes through acknowledgement-backed commit."""
        if mutation_authority_receipt_id is None:
            raise PermissionError("patch application requires mutation authority receipt")
        intent = self.effects.prepare_application(
            transaction_id=transaction_id,
            mutation_authority_receipt_id=mutation_authority_receipt_id,
            application_ref=application_ref,
        )
        self.commit_application(intent.intent_id, executor_receipt_ref=application_ref)
        return self.transactions.get(transaction_id)

    def acknowledge_rollback(
        self,
        intent_id: str,
        *,
        executor_namespace: str,
        executor_receipt_ref: str,
        observed_state_digest: str,
    ) -> EngineeringRollbackAcknowledgement:
        return self.effect_journal.acknowledge_rollback(
            intent_id,
            executor_namespace=executor_namespace,
            executor_receipt_ref=executor_receipt_ref,
            observed_state_digest=observed_state_digest,
        )

    def finalize_rollback(
        self,
        acknowledgement_id: str,
        *,
        verification_receipt_id: str,
    ) -> EngineeringRollbackCompletion:
        return self.effect_finalizer.finalize_rollback(
            acknowledgement_id,
            verification_receipt_id=verification_receipt_id,
        )

    def complete_rollback(
        self,
        intent_id: str,
        *,
        verification_receipt_id: str,
    ) -> EngineeringRollbackCompletion:
        """Compatibility completion path backed by a durable rollback observation."""
        intent = self.effects.rollback_intent(intent_id)
        try:
            verification = self.effects.rollback_verification(verification_receipt_id)
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

        acknowledgement = self.effect_journal.acknowledge_rollback(
            intent.intent_id,
            executor_namespace="compatibility.effects.v0.1",
            executor_receipt_ref=intent.rollback_operation_ref,
            observed_state_digest=intent.target_state_digest,
        )
        return self.effect_finalizer.finalize_rollback(
            acknowledgement.acknowledgement_id,
            verification_receipt_id=verification.receipt_id,
        )

    def _state_payload(self) -> dict[str, Any]:
        payload = super()._state_payload()
        payload["component_version"] = COMPONENT_VERSION
        payload["effect_journal"] = self.effect_journal.to_state()
        return payload

    @classmethod
    def from_state(
        cls,
        *,
        claims: CodeClaimLedger,
        state: Mapping[str, Any],
    ) -> "SoftwareEngineeringControlPlane":
        if _text(state["component_id"], field="component id") != COMPONENT_ID:
            raise ValueError("software engineering control component id mismatch")
        if _text(state["component_version"], field="component version") != COMPONENT_VERSION:
            raise ValueError("software engineering control component version mismatch")
        supplied_digest = _text(state["digest"], field="software engineering state digest")
        payload = {key: value for key, value in state.items() if key != "digest"}
        if canonical_digest(payload) != supplied_digest:
            raise ValueError("software engineering control snapshot digest mismatch")
        if "effect_journal" not in state:
            raise ValueError("software engineering v0.7 snapshot requires durable effect journal")

        # Explicit schema translation into the frozen v0.6 implementation.
        # Missing acknowledgement history is never guessed or synthesized.
        base_payload = {
            key: value
            for key, value in state.items()
            if key not in {"digest", "effect_journal"}
        }
        base_payload["component_version"] = BASE_COMPONENT_VERSION
        base_state = {**base_payload, "digest": canonical_digest(base_payload)}
        base = _SoftwareEngineeringControlPlaneV06.from_state(
            claims=claims,
            state=base_state,
        )

        fenced_effects = FencedEngineeringEffectLedger.from_state(
            transactions=base.transactions,
            mutation_authority=base.mutation_authority,
            state=base.effects.to_state(),
        )
        journal = EngineeringEffectJournal.from_state(
            transactions=base.transactions,
            effects=fenced_effects,
            state=state["effect_journal"],
        )
        plane = cls(
            claims=claims,
            evidence=base.evidence,
            transactions=base.transactions,
            claim_bindings=base.claim_bindings,
            manifests=base.manifests,
            closure=base.closure,
            policy=base.policy,
            gate=base.gate,
            mutation_authority=base.mutation_authority,
            effects=fenced_effects,
            validity=base.validity,
            works={row.work_id: row for row in base.works()},
            effect_journal=journal,
        )
        plane.effect_journal.validate_effect_coverage()
        if plane.digest != supplied_digest:
            raise ValueError("software engineering control restore is not state-identical")
        return plane


__all__ = (
    "EngineeringWorkRecord",
    "SoftwareEngineeringControlPlane",
)
