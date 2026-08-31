from __future__ import annotations

from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core._software_engineering_control_v07 import (
    CANONICAL_WRITE_AUTHORITY,
    COMPONENT_ID as BASE_COMPONENT_ID,
    COMPONENT_VERSION as BASE_COMPONENT_VERSION,
    EngineeringWorkRecord,
    SoftwareEngineeringControlPlane as _SoftwareEngineeringControlPlaneV07,
)
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering import EngineeringPhase
from nolane.external_core.software_engineering_effect_dispatch import (
    EngineeringDispatchOrigin,
    EngineeringEffectDispatchLedger,
    EngineeringEffectDispatchRecord,
)
from nolane.external_core.software_engineering_effect_journal import (
    EngineeringApplicationAcknowledgement,
    EngineeringRollbackAcknowledgement,
)
from nolane.external_core.software_engineering_effects import (
    EngineeringApplicationCommit,
    EngineeringRollbackCompletion,
)
from nolane.external_core.software_engineering_recovery_frontier import (
    EngineeringEffectRecoveryFrontier,
    EngineeringRecoveryFrontierReceipt,
)


COMPONENT_ID = BASE_COMPONENT_ID
COMPONENT_VERSION = "0.8.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


class SoftwareEngineeringControlPlane(_SoftwareEngineeringControlPlaneV07):
    """F control plane with durable pre-dispatch uncertainty fencing.

    A v0.9 engineering wave adds a coordination-only dispatch marker before an
    integration crosses the external executor boundary. If a restart observes a
    dispatch marker without a durable acknowledgement, F refuses automatic
    redispatch and exposes EXTERNAL_STATUS_REQUIRED through a read-only recovery
    frontier. This does not claim distributed exactly-once execution.
    """

    def __init__(
        self,
        *,
        claims: CodeClaimLedger,
        effect_dispatch: EngineeringEffectDispatchLedger | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(claims=claims, **kwargs)
        if effect_dispatch is None:
            self.effect_dispatch = EngineeringEffectDispatchLedger(
                transactions=self.transactions,
                effects=self.effects,
            )
        elif (
            effect_dispatch.transactions is self.transactions
            and effect_dispatch.effects is self.effects
        ):
            self.effect_dispatch = effect_dispatch
        else:
            self.effect_dispatch = EngineeringEffectDispatchLedger.from_state(
                transactions=self.transactions,
                effects=self.effects,
                state=effect_dispatch.to_state(),
            )
        if (
            self.effect_dispatch.transactions is not self.transactions
            or self.effect_dispatch.effects is not self.effects
        ):
            raise ValueError("effect dispatch ledger must share canonical transaction/effect ledgers")
        self.recovery_frontier = EngineeringEffectRecoveryFrontier(
            transactions=self.transactions,
            effects=self.effects,
            journal=self.effect_journal,
            dispatch=self.effect_dispatch,
        )
        self._validate_dispatch_acknowledgement_lineage()

    def _application_dispatch_for_intent(self, intent_id: str) -> EngineeringEffectDispatchRecord | None:
        return self.effect_dispatch.application_dispatch_for_intent(intent_id)

    def _rollback_dispatch_for_intent(self, intent_id: str) -> EngineeringEffectDispatchRecord | None:
        return self.effect_dispatch.rollback_dispatch_for_intent(intent_id)

    def begin_application_dispatch(
        self,
        intent_id: str,
        *,
        executor_namespace: str,
    ) -> EngineeringEffectDispatchRecord:
        intent = self.effects.application_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        existing = self._application_dispatch_for_intent(intent.intent_id)
        if existing is not None:
            raise PermissionError(
                "application dispatch already started; external status reconciliation required before any redispatch"
            )
        if self.effect_journal.application_acknowledgement_for_transaction(tx.transaction_id) is not None:
            raise PermissionError("application already acknowledged; local finalization is required instead of dispatch")
        if self.effects.application_commit_for_transaction(tx.transaction_id) is not None:
            raise PermissionError("application already finalized; dispatch cannot be reactivated")
        if tx.phase is not EngineeringPhase.PRECONDITIONS_VERIFIED:
            raise ValueError("application dispatch requires precondition-verified transaction phase")

        try:
            mutation = self.mutation_authority.get(intent.mutation_authority_receipt_id)
        except KeyError as exc:
            raise PermissionError("application dispatch requires known mutation authority receipt") from exc
        if (
            mutation.digest != intent.mutation_authority_receipt_digest
            or not mutation.authorized
            or mutation.transaction_id != tx.transaction_id
            or mutation.patch_ref != tx.patch_ref
            or mutation.patch_digest != tx.patch_digest
        ):
            raise PermissionError("application dispatch lost immutable mutation authority lineage")
        reasons = tuple(self.mutation_authority.preapply_reasons(tx.transaction_id))
        if reasons:
            raise PermissionError("application dispatch denied by live mutation authority: " + ", ".join(reasons))

        return self.effect_dispatch.record_application(
            intent.intent_id,
            executor_namespace=_text(executor_namespace, field="executor namespace"),
            origin=EngineeringDispatchOrigin.PRE_DISPATCH,
        )

    def begin_rollback_dispatch(
        self,
        intent_id: str,
        *,
        executor_namespace: str,
    ) -> EngineeringEffectDispatchRecord:
        intent = self.effects.rollback_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        existing = self._rollback_dispatch_for_intent(intent.intent_id)
        if existing is not None:
            raise PermissionError(
                "rollback dispatch already started; external status reconciliation required before any redispatch"
            )
        if self.effect_journal.rollback_acknowledgement_for_transaction(tx.transaction_id) is not None:
            raise PermissionError("rollback already acknowledged; verification/finalization is required instead of dispatch")
        completion_id = getattr(self.effects, "_rollback_completion_by_transaction", {}).get(tx.transaction_id)
        if completion_id is not None:
            raise PermissionError("rollback already finalized; dispatch cannot be reactivated")
        return self.effect_dispatch.record_rollback(
            intent.intent_id,
            executor_namespace=_text(executor_namespace, field="executor namespace"),
            origin=EngineeringDispatchOrigin.PRE_DISPATCH,
        )

    def acknowledge_application(
        self,
        intent_id: str,
        *,
        executor_namespace: str,
        executor_receipt_ref: str,
        observed_state_digest: str,
    ) -> EngineeringApplicationAcknowledgement:
        namespace = _text(executor_namespace, field="executor namespace")
        dispatch = self._application_dispatch_for_intent(intent_id)
        if dispatch is None:
            dispatch = self.effect_dispatch.record_application(
                intent_id,
                executor_namespace=namespace,
                origin=EngineeringDispatchOrigin.OBSERVED_WITH_ACK,
            )
        elif dispatch.executor_namespace != namespace:
            raise ValueError("application acknowledgement executor namespace does not match dispatch lineage")
        acknowledgement = super().acknowledge_application(
            intent_id,
            executor_namespace=namespace,
            executor_receipt_ref=executor_receipt_ref,
            observed_state_digest=observed_state_digest,
        )
        self._validate_dispatch_acknowledgement_lineage()
        return acknowledgement

    def acknowledge_rollback(
        self,
        intent_id: str,
        *,
        executor_namespace: str,
        executor_receipt_ref: str,
        observed_state_digest: str,
    ) -> EngineeringRollbackAcknowledgement:
        namespace = _text(executor_namespace, field="executor namespace")
        dispatch = self._rollback_dispatch_for_intent(intent_id)
        if dispatch is None:
            dispatch = self.effect_dispatch.record_rollback(
                intent_id,
                executor_namespace=namespace,
                origin=EngineeringDispatchOrigin.OBSERVED_WITH_ACK,
            )
        elif dispatch.executor_namespace != namespace:
            raise ValueError("rollback acknowledgement executor namespace does not match dispatch lineage")
        acknowledgement = super().acknowledge_rollback(
            intent_id,
            executor_namespace=namespace,
            executor_receipt_ref=executor_receipt_ref,
            observed_state_digest=observed_state_digest,
        )
        self._validate_dispatch_acknowledgement_lineage()
        return acknowledgement

    def commit_application(
        self,
        intent_id: str,
        *,
        executor_receipt_ref: str,
    ) -> EngineeringApplicationCommit:
        intent = self.effects.application_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        dispatch = self._application_dispatch_for_intent(intent.intent_id)
        acknowledgement = self.effect_journal.application_acknowledgement_for_transaction(tx.transaction_id)
        if dispatch is not None and dispatch.origin is EngineeringDispatchOrigin.PRE_DISPATCH and acknowledgement is None:
            raise PermissionError(
                "pre-dispatch application is externally uncertain; record/query acknowledgement before local finalization"
            )
        if dispatch is None:
            self.effect_dispatch.record_application(
                intent.intent_id,
                executor_namespace="compatibility.effects.v0.1",
                origin=EngineeringDispatchOrigin.OBSERVED_WITH_ACK,
            )
        commit = super().commit_application(intent.intent_id, executor_receipt_ref=executor_receipt_ref)
        self._validate_dispatch_acknowledgement_lineage()
        return commit

    def complete_rollback(
        self,
        intent_id: str,
        *,
        verification_receipt_id: str,
    ) -> EngineeringRollbackCompletion:
        intent = self.effects.rollback_intent(intent_id)
        tx = self.transactions.get(intent.transaction_id)
        dispatch = self._rollback_dispatch_for_intent(intent.intent_id)
        acknowledgement = self.effect_journal.rollback_acknowledgement_for_transaction(tx.transaction_id)
        if dispatch is not None and dispatch.origin is EngineeringDispatchOrigin.PRE_DISPATCH and acknowledgement is None:
            raise PermissionError(
                "pre-dispatch rollback is externally uncertain; record/query acknowledgement before local finalization"
            )
        if dispatch is None:
            self.effect_dispatch.record_rollback(
                intent.intent_id,
                executor_namespace="compatibility.effects.v0.1",
                origin=EngineeringDispatchOrigin.OBSERVED_WITH_ACK,
            )
        completion = super().complete_rollback(
            intent.intent_id,
            verification_receipt_id=verification_receipt_id,
        )
        self._validate_dispatch_acknowledgement_lineage()
        return completion

    def application_recovery_frontier(self, intent_id: str) -> EngineeringRecoveryFrontierReceipt:
        return self.recovery_frontier.application(intent_id)

    def rollback_recovery_frontier(self, intent_id: str) -> EngineeringRecoveryFrontierReceipt:
        return self.recovery_frontier.rollback(intent_id)

    def _validate_dispatch_acknowledgement_lineage(self) -> None:
        self.effect_dispatch.validate_lineage()
        for acknowledgement in self.effect_journal.application_acknowledgements():
            dispatch = self.effect_dispatch.application_dispatch_for_intent(acknowledgement.intent_id)
            if dispatch is None:
                raise ValueError("application acknowledgement missing durable dispatch lineage")
            if (
                dispatch.transaction_id != acknowledgement.transaction_id
                or dispatch.intent_digest != acknowledgement.intent_digest
                or dispatch.patch_ref != acknowledgement.patch_ref
                or dispatch.patch_digest != acknowledgement.patch_digest
                or dispatch.operation_ref != acknowledgement.application_ref
                or dispatch.executor_namespace != acknowledgement.executor_namespace
            ):
                raise ValueError("application acknowledgement/dispatch lineage mismatch")

        for acknowledgement in self.effect_journal.rollback_acknowledgements():
            dispatch = self.effect_dispatch.rollback_dispatch_for_intent(acknowledgement.rollback_intent_id)
            if dispatch is None:
                raise ValueError("rollback acknowledgement missing durable dispatch lineage")
            if (
                dispatch.transaction_id != acknowledgement.transaction_id
                or dispatch.intent_digest != acknowledgement.rollback_intent_digest
                or dispatch.patch_ref != acknowledgement.patch_ref
                or dispatch.patch_digest != acknowledgement.patch_digest
                or dispatch.operation_ref != acknowledgement.rollback_operation_ref
                or dispatch.target_state_digest != acknowledgement.target_state_digest
                or dispatch.executor_namespace != acknowledgement.executor_namespace
            ):
                raise ValueError("rollback acknowledgement/dispatch lineage mismatch")

        for dispatch in self.effect_dispatch.records():
            if dispatch.origin is not EngineeringDispatchOrigin.OBSERVED_WITH_ACK:
                continue
            if dispatch.kind.value == "application":
                acknowledgement = self.effect_journal.application_acknowledgement_for_transaction(dispatch.transaction_id)
            else:
                acknowledgement = self.effect_journal.rollback_acknowledgement_for_transaction(dispatch.transaction_id)
            if acknowledgement is None:
                raise ValueError("acknowledgement-backfilled dispatch requires durable acknowledgement")

    def _state_payload(self) -> dict[str, Any]:
        self._validate_dispatch_acknowledgement_lineage()
        payload = super()._state_payload()
        payload["component_version"] = COMPONENT_VERSION
        payload["effect_dispatch"] = self.effect_dispatch.to_state()
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
        if "effect_dispatch" not in state:
            raise ValueError("software engineering v0.8 snapshot requires durable effect dispatch lineage")

        base_payload = {
            key: value
            for key, value in state.items()
            if key not in {"digest", "effect_dispatch"}
        }
        base_payload["component_version"] = BASE_COMPONENT_VERSION
        base_state = {**base_payload, "digest": canonical_digest(base_payload)}
        base = _SoftwareEngineeringControlPlaneV07.from_state(
            claims=claims,
            state=base_state,
        )
        dispatch = EngineeringEffectDispatchLedger.from_state(
            transactions=base.transactions,
            effects=base.effects,
            state=state["effect_dispatch"],
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
            effects=base.effects,
            validity=base.validity,
            works={row.work_id: row for row in base.works()},
            effect_journal=base.effect_journal,
            effect_dispatch=dispatch,
        )
        plane.effect_journal.validate_effect_coverage()
        plane._validate_dispatch_acknowledgement_lineage()
        if plane.digest != supplied_digest:
            raise ValueError("software engineering control restore is not state-identical")
        return plane


__all__ = (
    "CANONICAL_WRITE_AUTHORITY",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "EngineeringWorkRecord",
    "SoftwareEngineeringControlPlane",
)
