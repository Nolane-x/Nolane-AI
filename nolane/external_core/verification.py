from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.schemas.identity import PHYSICAL_PARAMETER_CEILING
from nolane.organization.events import EventKind, EventLedger
from nolane.organization.identity import AgentRegistry


COMPONENT_ID = "external.verification"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.verification"


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    agent_id: str
    candidate_version: str
    physical_parameters: int
    passed: bool
    false_accepts: int
    regressions: int
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.physical_parameters < 0:
            raise ValueError("physical parameter count must be non-negative")
        if self.false_accepts < 0 or self.regressions < 0:
            raise ValueError("candidate counters must be non-negative")
        if not self.agent_id or not self.candidate_version:
            raise ValueError("candidate identity and version must be explicit")


@dataclass(frozen=True, slots=True)
class PromotionReceipt:
    receipt_id: str
    agent_id: str
    candidate_version: str
    physical_parameters: int
    accepted: bool
    reason: str
    evidence_ids: tuple[str, ...]
    promoted: bool = False
    previous_version: str | None = None

    def to_state(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "agent_id": self.agent_id,
            "candidate_version": self.candidate_version,
            "physical_parameters": self.physical_parameters,
            "accepted": self.accepted,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "promoted": self.promoted,
            "previous_version": self.previous_version,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "PromotionReceipt":
        return cls(
            receipt_id=str(state["receipt_id"]),
            agent_id=str(state["agent_id"]),
            candidate_version=str(state["candidate_version"]),
            physical_parameters=int(state["physical_parameters"]),
            accepted=bool(state["accepted"]),
            reason=str(state["reason"]),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            promoted=bool(state.get("promoted", False)),
            previous_version=None if state.get("previous_version") is None else str(state["previous_version"]),
        )


@dataclass(frozen=True, slots=True)
class RollbackReceipt:
    rollback_id: str
    agent_id: str
    from_version: str
    restored_version: str
    reason: str

    def to_state(self) -> dict[str, str]:
        return {
            "rollback_id": self.rollback_id,
            "agent_id": self.agent_id,
            "from_version": self.from_version,
            "restored_version": self.restored_version,
            "reason": self.reason,
        }


class VerificationAuthority:
    """Canonical bounded candidate-evaluation, promotion and rollback authority."""

    def __init__(self, *, registry: AgentRegistry, ledger: EventLedger | None = None) -> None:
        self.registry = registry
        self.ledger = ledger
        self._receipts: dict[str, PromotionReceipt] = {}
        self._promotion_stack: dict[str, list[str]] = {}
        self._rollback_counter = 0

    def evaluate_candidate(self, evaluation: CandidateEvaluation) -> PromotionReceipt:
        self.registry.get(evaluation.agent_id)
        if evaluation.physical_parameters >= PHYSICAL_PARAMETER_CEILING:
            accepted, reason = False, "parameter_ceiling_exceeded"
        elif not evaluation.passed:
            accepted, reason = False, "verification_failed"
        elif evaluation.false_accepts:
            accepted, reason = False, "false_accepts_detected"
        elif evaluation.regressions:
            accepted, reason = False, "regressions_detected"
        elif not evaluation.evidence_ids:
            accepted, reason = False, "missing_evidence"
        else:
            accepted, reason = True, "accepted_bounded_candidate"
        receipt_id = f"promotion-{len(self._receipts) + 1:08d}"
        row = PromotionReceipt(
            receipt_id=receipt_id,
            agent_id=evaluation.agent_id,
            candidate_version=evaluation.candidate_version,
            physical_parameters=evaluation.physical_parameters,
            accepted=accepted,
            reason=reason,
            evidence_ids=tuple(evaluation.evidence_ids),
        )
        self._receipts[row.receipt_id] = row
        if self.ledger is not None:
            self.ledger.append(
                EventKind.NEURAL_CANDIDATE_EVALUATED,
                source_agent_id="verification.chief",
                target_agent_id=evaluation.agent_id,
                region=self.registry.get(evaluation.agent_id).region,
                payload={
                    "receipt_id": row.receipt_id,
                    "candidate_version": row.candidate_version,
                    "accepted": row.accepted,
                    "reason": row.reason,
                },
            )
        return row

    def get_receipt(self, receipt_id: str) -> PromotionReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown promotion receipt: {receipt_id}") from exc

    def promote_candidate(self, receipt_id: str) -> PromotionReceipt:
        old = self.get_receipt(receipt_id)
        if not old.accepted:
            raise PermissionError(f"candidate promotion rejected: {old.reason}")
        if old.promoted:
            return old
        current = self.registry.get(old.agent_id).neural_version
        self._promotion_stack.setdefault(old.agent_id, []).append(current)
        self.registry.accept_neural_version(old.agent_id, old.candidate_version)
        row = PromotionReceipt(
            receipt_id=old.receipt_id,
            agent_id=old.agent_id,
            candidate_version=old.candidate_version,
            physical_parameters=old.physical_parameters,
            accepted=old.accepted,
            reason=old.reason,
            evidence_ids=old.evidence_ids,
            promoted=True,
            previous_version=current,
        )
        self._receipts[row.receipt_id] = row
        if self.ledger is not None:
            self.ledger.append(
                EventKind.NEURAL_PROMOTED,
                source_agent_id="verification.chief",
                target_agent_id=row.agent_id,
                region=self.registry.get(row.agent_id).region,
                payload={
                    "receipt_id": row.receipt_id,
                    "from_version": current,
                    "to_version": row.candidate_version,
                },
            )
        return row

    def rollback(self, agent_id: str, *, reason: str) -> RollbackReceipt:
        if not str(reason).strip():
            raise ValueError("rollback reason must be explicit")
        stack = self._promotion_stack.get(str(agent_id), [])
        if not stack:
            raise ValueError(f"no promoted predecessor is available for {agent_id}")
        current = self.registry.get(agent_id).neural_version
        restored = stack.pop()
        self.registry.accept_neural_version(agent_id, restored)
        self._rollback_counter += 1
        row = RollbackReceipt(
            rollback_id=f"rollback-{self._rollback_counter:08d}",
            agent_id=str(agent_id),
            from_version=current,
            restored_version=restored,
            reason=str(reason),
        )
        if self.ledger is not None:
            self.ledger.append(
                EventKind.NEURAL_ROLLBACK,
                source_agent_id="verification.chief",
                target_agent_id=row.agent_id,
                region=self.registry.get(row.agent_id).region,
                payload=row.to_state(),
            )
        return row

    def to_state(self) -> dict[str, Any]:
        return {
            "receipts": [self._receipts[key].to_state() for key in sorted(self._receipts)],
            "promotion_stack": {key: list(value) for key, value in sorted(self._promotion_stack.items())},
            "rollback_counter": self._rollback_counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        ledger: EventLedger | None,
        state: Mapping[str, Any],
    ) -> "VerificationAuthority":
        authority = cls(registry=registry, ledger=ledger)
        for value in state.get("receipts", ()):
            row = PromotionReceipt.from_state(value)
            authority._receipts[row.receipt_id] = row
        authority._promotion_stack = {
            str(key): [str(value) for value in values]
            for key, values in state.get("promotion_stack", {}).items()
        }
        authority._rollback_counter = int(state.get("rollback_counter", 0))
        return authority


__all__ = (
    "CandidateEvaluation",
    "PromotionReceipt",
    "RollbackReceipt",
    "VerificationAuthority",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
