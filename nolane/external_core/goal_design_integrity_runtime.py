"""Runtime enforcement for terminal-intent integrity in D. Goal / Design.

``goal_design_integrity`` defines immutable integrity contracts and companion
receipts.  This module turns those artifacts into live authority: decisions are
admitted only against the current contract, contract supersession invalidates
older authority, and the integrity layer is content-addressed and persistable.

The historical ``GoalDesignRuntime`` and ``DecisionReceipt`` surfaces are not
modified.  Consumers opt into this stricter runtime explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from .goal_design import (
    CoherenceError,
    DecisionReceipt,
    DesignOption,
    DesignScenario,
    GoalDesignSnapshot,
    GoalSpec,
    ProofObligation,
    UncertaintyItem,
    stable_digest,
)
from .goal_design_integrity import (
    GoalIntegrityAttestation,
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
    GoalIntegrityMetricBinding,
    GoalIntegrityReceipt,
    assess_goal_integrity,
    mint_goal_integrity_receipt,
    verify_goal_integrity_receipt,
)
from .goal_design_runtime import (
    DecisionAuthorityIndex,
    DecisionLifecycle,
    GoalDesignRuntime,
)

__version__ = "0.1.0"


@dataclass(frozen=True)
class GoalIntegrityRuntimeAdmission:
    """Atomic result of ordinary decision authority plus terminal integrity."""

    decision_receipt: DecisionReceipt
    integrity_receipt: GoalIntegrityReceipt


@dataclass(frozen=True)
class GoalIntegrityAuthorityRecord:
    """Persistent companion authority for one immutable decision receipt."""

    decision_receipt: DecisionReceipt
    integrity_receipt: GoalIntegrityReceipt
    lifecycle: DecisionLifecycle = DecisionLifecycle.ACTIVE
    invalidation_reasons: tuple[str, ...] = ()

    @property
    def decision_receipt_id(self) -> str:
        return self.decision_receipt.receipt_id

    @property
    def goal_id(self) -> str:
        return self.decision_receipt.goal_id

    @property
    def contract_digest(self) -> str:
        return self.integrity_receipt.contract_digest


class GoalIntegrityAuthorityIndex:
    """Content-addressed lifecycle index for companion integrity authority."""

    SCHEMA_VERSION = 1

    def __init__(self) -> None:
        self._records: dict[str, GoalIntegrityAuthorityRecord] = {}

    @staticmethod
    def _copy_record(record: GoalIntegrityAuthorityRecord) -> GoalIntegrityAuthorityRecord:
        decision = replace(
            record.decision_receipt,
            version_vector=dict(record.decision_receipt.version_vector),
        )
        return replace(record, decision_receipt=decision)

    def register(
        self,
        decision_receipt: DecisionReceipt,
        integrity_receipt: GoalIntegrityReceipt,
    ) -> GoalIntegrityAuthorityRecord:
        verify_goal_integrity_receipt(integrity_receipt, decision_receipt)
        receipt_id = decision_receipt.receipt_id
        candidate = GoalIntegrityAuthorityRecord(
            decision_receipt=replace(
                decision_receipt,
                version_vector=dict(decision_receipt.version_vector),
            ),
            integrity_receipt=integrity_receipt,
        )
        existing = self._records.get(receipt_id)
        if existing is not None:
            if existing.decision_receipt != candidate.decision_receipt:
                raise ValueError(
                    "integrity authority cannot rebind a decision receipt identity"
                )
            if existing.integrity_receipt != candidate.integrity_receipt:
                raise ValueError(
                    "integrity authority cannot rebind a decision to another integrity receipt"
                )
            return self._copy_record(existing)
        self._records[receipt_id] = candidate
        return self._copy_record(candidate)

    def get(self, decision_receipt_id: str) -> GoalIntegrityAuthorityRecord:
        try:
            return self._copy_record(self._records[str(decision_receipt_id)])
        except KeyError as exc:
            raise KeyError(
                f"unknown Goal/Design integrity authority: {decision_receipt_id}"
            ) from exc

    def records(self) -> tuple[GoalIntegrityAuthorityRecord, ...]:
        return tuple(
            self._copy_record(self._records[key]) for key in sorted(self._records)
        )

    def active(self) -> tuple[GoalIntegrityAuthorityRecord, ...]:
        return tuple(
            record
            for record in self.records()
            if record.lifecycle is DecisionLifecycle.ACTIVE
        )

    def mark_stale(
        self,
        decision_receipt_id: str,
        reasons: Sequence[str],
    ) -> GoalIntegrityAuthorityRecord:
        normalized = tuple(
            sorted({str(reason).strip() for reason in reasons if str(reason).strip()})
        )
        if not normalized:
            raise ValueError("integrity authority staleness requires a reason")
        record = self.get(decision_receipt_id)
        if record.lifecycle in {
            DecisionLifecycle.SUPERSEDED,
            DecisionLifecycle.REVOKED,
        }:
            raise ValueError(
                f"integrity authority lifecycle is terminal ({record.lifecycle.value})"
            )
        merged = tuple(sorted(set(record.invalidation_reasons) | set(normalized)))
        if (
            record.lifecycle is DecisionLifecycle.STALE
            and merged == record.invalidation_reasons
        ):
            return record
        updated = replace(
            record,
            lifecycle=DecisionLifecycle.STALE,
            invalidation_reasons=merged,
        )
        self._records[decision_receipt_id] = updated
        return self._copy_record(updated)

    @staticmethod
    def _receipt_to_state(receipt: GoalIntegrityReceipt) -> dict[str, Any]:
        return {
            "receipt_id": receipt.receipt_id,
            "decision_receipt_id": receipt.decision_receipt_id,
            "goal_id": receipt.goal_id,
            "selected_option_id": receipt.selected_option_id,
            "contract_digest": receipt.contract_digest,
            "assessment_digest": receipt.assessment_digest,
            "attestation_ids": list(receipt.attestation_ids),
        }

    @staticmethod
    def _receipt_from_state(state: Mapping[str, Any]) -> GoalIntegrityReceipt:
        return GoalIntegrityReceipt(
            receipt_id=str(state["receipt_id"]),
            decision_receipt_id=str(state["decision_receipt_id"]),
            goal_id=str(state["goal_id"]),
            selected_option_id=str(state["selected_option_id"]),
            contract_digest=str(state["contract_digest"]),
            assessment_digest=str(state["assessment_digest"]),
            attestation_ids=tuple(str(x) for x in state.get("attestation_ids", ())),
        )

    def to_state(self) -> dict[str, Any]:
        rows = []
        for record in self.records():
            rows.append(
                {
                    "decision_receipt": DecisionAuthorityIndex._receipt_to_state(
                        record.decision_receipt
                    ),
                    "integrity_receipt": self._receipt_to_state(
                        record.integrity_receipt
                    ),
                    "lifecycle": record.lifecycle.value,
                    "invalidation_reasons": list(record.invalidation_reasons),
                }
            )
        return {"schema_version": self.SCHEMA_VERSION, "records": rows}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "GoalIntegrityAuthorityIndex":
        if int(state.get("schema_version", cls.SCHEMA_VERSION)) != cls.SCHEMA_VERSION:
            raise ValueError("unsupported Goal/Design integrity authority schema")
        index = cls()
        for row in state.get("records", ()):
            decision = DecisionAuthorityIndex._receipt_from_state(
                row["decision_receipt"]
            )
            integrity = cls._receipt_from_state(row["integrity_receipt"])
            verify_goal_integrity_receipt(integrity, decision)
            receipt_id = decision.receipt_id
            if receipt_id in index._records:
                raise ValueError(
                    f"duplicate Goal/Design integrity authority: {receipt_id}"
                )
            lifecycle = DecisionLifecycle(
                str(row.get("lifecycle", DecisionLifecycle.ACTIVE.value))
            )
            reasons = tuple(
                sorted(
                    {
                        str(reason).strip()
                        for reason in row.get("invalidation_reasons", ())
                        if str(reason).strip()
                    }
                )
            )
            if lifecycle is DecisionLifecycle.ACTIVE and reasons:
                raise ValueError(
                    "active Goal/Design integrity authority cannot carry invalidation reasons"
                )
            if lifecycle is DecisionLifecycle.STALE and not reasons:
                raise ValueError(
                    "stale Goal/Design integrity authority requires an invalidation reason"
                )
            index._records[receipt_id] = GoalIntegrityAuthorityRecord(
                decision_receipt=decision,
                integrity_receipt=integrity,
                lifecycle=lifecycle,
                invalidation_reasons=reasons,
            )
        return index

    @property
    def digest(self) -> str:
        return stable_digest({"goal_integrity_authority_index": self.to_state()})


def _contract_to_state(contract: GoalIntegrityContract) -> dict[str, Any]:
    return {
        "goal_id": contract.goal_id,
        "clauses": [
            {
                "clause_id": clause.clause_id,
                "goal_id": clause.goal_id,
                "kind": clause.kind.value,
                "statement": clause.statement,
                "provenance_ref": clause.provenance_ref,
                "required_planes": list(clause.required_planes),
            }
            for clause in contract.clauses
        ],
        "metric_bindings": [
            {
                "metric_id": binding.metric_id,
                "goal_id": binding.goal_id,
                "criterion_ref": binding.criterion_ref,
                "metric_ref": binding.metric_ref,
                "provenance_ref": binding.provenance_ref,
            }
            for binding in contract.metric_bindings
        ],
    }


def _contract_from_state(state: Mapping[str, Any]) -> GoalIntegrityContract:
    return GoalIntegrityContract(
        goal_id=str(state["goal_id"]),
        clauses=tuple(
            GoalIntegrityClause(
                clause_id=str(row["clause_id"]),
                goal_id=str(row["goal_id"]),
                kind=GoalIntegrityClauseKind(str(row["kind"])),
                statement=str(row["statement"]),
                provenance_ref=str(row["provenance_ref"]),
                required_planes=tuple(
                    str(x) for x in row.get("required_planes", ())
                ),
            )
            for row in state.get("clauses", ())
        ),
        metric_bindings=tuple(
            GoalIntegrityMetricBinding(
                metric_id=str(row["metric_id"]),
                goal_id=str(row["goal_id"]),
                criterion_ref=str(row["criterion_ref"]),
                metric_ref=str(row["metric_ref"]),
                provenance_ref=str(row["provenance_ref"]),
            )
            for row in state.get("metric_bindings", ())
        ),
    )


class GoalIntegrityRuntime(GoalDesignRuntime):
    """Fail-closed Goal/Design runtime with terminal-intent continuity."""

    INTEGRITY_STATE_SCHEMA_VERSION = 1

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.integrity_authority = GoalIntegrityAuthorityIndex()
        self._integrity_contracts: dict[str, GoalIntegrityContract] = {}
        self._current_contracts: dict[str, str] = {}
        self._contract_predecessors: dict[str, str | None] = {}

    def current_integrity_contract(self, goal_id: str) -> GoalIntegrityContract:
        goal_id = str(goal_id).strip()
        digest = self._current_contracts.get(goal_id)
        if digest is None:
            raise KeyError(f"no current Goal/Design integrity contract for {goal_id}")
        return self._integrity_contracts[digest]

    def install_integrity_contract(
        self,
        contract: GoalIntegrityContract,
        *,
        supersedes_digest: str | None = None,
    ) -> str:
        """Install or explicitly supersede terminal-intent authority.

        A changed contract must name the exact current predecessor.  Historical
        digests cannot be reactivated, preventing rollback-based authority
        laundering.
        """

        current_digest = self._current_contracts.get(contract.goal_id)
        if current_digest is None:
            if supersedes_digest not in (None, ""):
                raise CoherenceError(
                    "Goal/Design integrity contract has no predecessor to supersede"
                )
            self._integrity_contracts[contract.digest] = contract
            self._current_contracts[contract.goal_id] = contract.digest
            self._contract_predecessors.setdefault(contract.digest, None)
            return contract.digest

        if current_digest == contract.digest:
            if supersedes_digest not in (None, "", current_digest):
                raise CoherenceError(
                    "Goal/Design integrity contract predecessor does not match current authority"
                )
            return contract.digest

        supplied = "" if supersedes_digest is None else str(supersedes_digest).strip()
        if supplied != current_digest:
            raise CoherenceError(
                "Goal/Design integrity contract supersession requires the exact current predecessor digest"
            )
        if contract.digest in self._integrity_contracts:
            raise CoherenceError(
                "historical Goal/Design integrity contract cannot be reactivated"
            )

        reason = (
            "goal integrity contract superseded: "
            f"{current_digest} -> {contract.digest}"
        )

        # Archive the new immutable contract before changing the current pointer;
        # every operation below is deterministic for records already proven active.
        self._integrity_contracts[contract.digest] = contract
        self._contract_predecessors[contract.digest] = current_digest
        self._current_contracts[contract.goal_id] = contract.digest

        for integrity_record in tuple(self.integrity_authority.active()):
            if (
                integrity_record.goal_id != contract.goal_id
                or integrity_record.contract_digest != current_digest
            ):
                continue
            receipt_id = integrity_record.decision_receipt_id
            try:
                decision_record = self.decisions.get(receipt_id)
            except KeyError:
                decision_record = None
            if (
                decision_record is not None
                and decision_record.lifecycle is DecisionLifecycle.ACTIVE
            ):
                self.decisions.mark_stale(receipt_id, (reason,))
                self._record_invalidation(decision_record, (reason,))
            self.integrity_authority.mark_stale(receipt_id, (reason,))
        return contract.digest

    @staticmethod
    def _integrity_blockers(assessment: Any) -> tuple[str, ...]:
        blockers: list[str] = []
        if assessment.missing_preservations:
            rendered = ", ".join(
                f"{plane}:{clause_id}"
                for plane, clause_id in assessment.missing_preservations
            )
            blockers.append("missing terminal integrity preservation: " + rendered)
        if assessment.violated_clause_ids:
            blockers.append(
                "violated terminal integrity clauses: "
                + ", ".join(assessment.violated_clause_ids)
            )
        if assessment.stale_attestation_ids:
            blockers.append(
                "stale integrity attestations: "
                + ", ".join(assessment.stale_attestation_ids)
            )
        if not blockers:
            blockers.append("terminal integrity assessment is not authorized")
        return tuple(blockers)

    def admit(
        self,
        *,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
        selected_option_id: str,
        snapshot: GoalDesignSnapshot,
        proof_obligations: Sequence[ProofObligation] = (),
        uncertainties: Sequence[UncertaintyItem] = (),
        integrity_attestations: Sequence[GoalIntegrityAttestation] = (),
    ) -> GoalIntegrityRuntimeAdmission:
        """Admit only after terminal integrity is proven, before side effects."""

        try:
            contract = self.current_integrity_contract(goal.goal_id)
        except KeyError as exc:
            raise CoherenceError(
                f"Goal/Design admission blocked: integrity contract is required for {goal.goal_id}"
            ) from exc

        try:
            assessment = assess_goal_integrity(contract, integrity_attestations)
        except ValueError as exc:
            raise CoherenceError(
                f"Goal/Design admission blocked by terminal integrity authority: {exc}"
            ) from exc
        if not assessment.authorized:
            raise CoherenceError(
                "Goal/Design admission blocked by terminal integrity authority: "
                + "; ".join(self._integrity_blockers(assessment))
            )

        # All user-controlled integrity failure modes are resolved above.  The
        # historical runtime now performs its unchanged coherence/truth admission.
        decision_receipt = super().admit(
            goal=goal,
            scenarios=scenarios,
            options=options,
            selected_option_id=selected_option_id,
            snapshot=snapshot,
            proof_obligations=proof_obligations,
            uncertainties=uncertainties,
        )
        integrity_receipt = mint_goal_integrity_receipt(
            decision_receipt=decision_receipt,
            contract=contract,
            assessment=assessment,
        )
        self.integrity_authority.register(decision_receipt, integrity_receipt)
        return GoalIntegrityRuntimeAdmission(
            decision_receipt=decision_receipt,
            integrity_receipt=integrity_receipt,
        )

    def _stale_integrity_authority(
        self,
        receipt_id: str,
        reasons: Sequence[str],
    ) -> None:
        try:
            integrity_record = self.integrity_authority.get(receipt_id)
        except KeyError:
            return
        if integrity_record.lifecycle is DecisionLifecycle.ACTIVE:
            self.integrity_authority.mark_stale(receipt_id, reasons)

    def revalidate_decisions(self) -> tuple[str, ...]:
        """Revalidate plane/truth authority and terminal-intent continuity."""

        stale = set(super().revalidate_decisions())
        for receipt_id in tuple(stale):
            self._stale_integrity_authority(
                receipt_id,
                ("underlying Goal/Design decision authority became stale",),
            )

        for decision_record in tuple(self.decisions.active()):
            receipt_id = decision_record.receipt.receipt_id
            reasons: tuple[str, ...] = ()
            try:
                integrity_record = self.integrity_authority.get(receipt_id)
            except KeyError:
                integrity_record = None
                reasons = ("decision has no companion terminal integrity authority",)
            else:
                current_digest = self._current_contracts.get(
                    decision_record.receipt.goal_id
                )
                if current_digest is None:
                    reasons = ("current goal integrity contract is unavailable",)
                elif integrity_record.contract_digest != current_digest:
                    reasons = (
                        "goal integrity contract changed after decision admission: "
                        f"{integrity_record.contract_digest} -> {current_digest}",
                    )
                elif integrity_record.lifecycle is not DecisionLifecycle.ACTIVE:
                    reasons = (
                        "companion terminal integrity authority is not active",
                    )
            if not reasons:
                continue
            self.decisions.mark_stale(receipt_id, reasons)
            self._record_invalidation(decision_record, reasons)
            if integrity_record is not None and integrity_record.lifecycle is DecisionLifecycle.ACTIVE:
                self.integrity_authority.mark_stale(receipt_id, reasons)
            stale.add(receipt_id)
        return tuple(sorted(stale))

    def integrity_state(self) -> dict[str, Any]:
        contracts = [
            {
                "digest": digest,
                "contract": _contract_to_state(self._integrity_contracts[digest]),
                "predecessor_digest": self._contract_predecessors.get(digest),
            }
            for digest in sorted(self._integrity_contracts)
        ]
        return {
            "schema_version": self.INTEGRITY_STATE_SCHEMA_VERSION,
            "contracts": contracts,
            "current_contracts": {
                goal_id: self._current_contracts[goal_id]
                for goal_id in sorted(self._current_contracts)
            },
            "authority": self.integrity_authority.to_state(),
        }

    def restore_integrity_state(self, state: Mapping[str, Any]) -> None:
        """Restore a self-verifying integrity layer into an otherwise fresh runtime."""

        if (
            self._integrity_contracts
            or self._current_contracts
            or self.integrity_authority.records()
        ):
            raise ValueError("Goal/Design integrity runtime state is already populated")
        if int(
            state.get("schema_version", self.INTEGRITY_STATE_SCHEMA_VERSION)
        ) != self.INTEGRITY_STATE_SCHEMA_VERSION:
            raise ValueError("unsupported Goal/Design integrity runtime schema")

        contracts: dict[str, GoalIntegrityContract] = {}
        predecessors: dict[str, str | None] = {}
        for row in state.get("contracts", ()):
            contract = _contract_from_state(row["contract"])
            digest = str(row["digest"])
            if digest != contract.digest:
                raise ValueError("persisted Goal/Design integrity contract digest mismatch")
            if digest in contracts:
                raise ValueError("duplicate persisted Goal/Design integrity contract")
            contracts[digest] = contract
            predecessor = row.get("predecessor_digest")
            predecessors[digest] = None if predecessor is None else str(predecessor)

        for digest, predecessor in predecessors.items():
            if predecessor is not None and predecessor not in contracts:
                raise ValueError(
                    f"integrity contract {digest} references unknown predecessor"
                )

        current = {
            str(goal_id): str(digest)
            for goal_id, digest in dict(state.get("current_contracts", {})).items()
        }
        for goal_id, digest in current.items():
            contract = contracts.get(digest)
            if contract is None or contract.goal_id != goal_id:
                raise ValueError(
                    "current Goal/Design integrity contract registry is inconsistent"
                )

        authority = GoalIntegrityAuthorityIndex.from_state(state.get("authority", {}))
        for record in authority.active():
            current_digest = current.get(record.goal_id)
            if current_digest != record.contract_digest:
                raise ValueError(
                    "active integrity authority is not bound to the current contract"
                )
            if record.contract_digest not in contracts:
                raise ValueError(
                    "active integrity authority references an unknown contract"
                )

        self._integrity_contracts = contracts
        self._current_contracts = current
        self._contract_predecessors = predecessors
        self.integrity_authority = authority

    @property
    def integrity_digest(self) -> str:
        return stable_digest({"goal_integrity_runtime": self.integrity_state()})


__all__ = [
    "GoalIntegrityAuthorityIndex",
    "GoalIntegrityAuthorityRecord",
    "GoalIntegrityRuntime",
    "GoalIntegrityRuntimeAdmission",
]
