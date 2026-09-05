from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


class ResearchTrialOutcome(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class ResearchTrial:
    trial_id: str
    question_id: str
    hypothesis_id: str
    producer_agent_id: str
    protocol_digest: str
    source_state_digest: str
    outcome: ResearchTrialOutcome
    observation: str
    limitations: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    predecessor_trial_id: str | None
    digest: str

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "hypothesis_id": self.hypothesis_id,
            "producer_agent_id": self.producer_agent_id,
            "protocol_digest": self.protocol_digest,
            "source_state_digest": self.source_state_digest,
            "outcome": self.outcome.value,
            "observation": self.observation,
            "limitations": list(self.limitations),
            "evidence_refs": list(self.evidence_refs),
            "predecessor_trial_id": self.predecessor_trial_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {"trial_id": self.trial_id, **self.semantic_payload(), "digest": self.digest}

    @classmethod
    def create(
        cls,
        *,
        question_id: str,
        hypothesis_id: str,
        producer_agent_id: str,
        protocol_digest: str,
        source_state_digest: str,
        outcome: ResearchTrialOutcome | str,
        observation: str,
        limitations: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        predecessor_trial_id: str | None = None,
    ) -> "ResearchTrial":
        limitation_rows = _unique_explicit(limitations, "research trial limitation")
        evidence_rows = _unique_explicit(evidence_refs, "research trial evidence ref")
        if not evidence_rows:
            raise ValueError("research trial requires evidence refs")
        predecessor = None
        if predecessor_trial_id is not None:
            predecessor = _explicit(predecessor_trial_id, "predecessor trial id")
        payload = {
            "question_id": _explicit(question_id, "research question id"),
            "hypothesis_id": _explicit(hypothesis_id, "research hypothesis id"),
            "producer_agent_id": _explicit(producer_agent_id, "research trial producer"),
            "protocol_digest": _explicit(protocol_digest, "research trial protocol digest"),
            "source_state_digest": _explicit(source_state_digest, "research trial source state digest"),
            "outcome": ResearchTrialOutcome(outcome).value,
            "observation": _explicit(observation, "research trial observation"),
            "limitations": list(limitation_rows),
            "evidence_refs": list(evidence_rows),
            "predecessor_trial_id": predecessor,
        }
        digest = canonical_digest(payload)
        return cls(
            trial_id="research-trial-" + digest[:24],
            question_id=payload["question_id"],
            hypothesis_id=payload["hypothesis_id"],
            producer_agent_id=payload["producer_agent_id"],
            protocol_digest=payload["protocol_digest"],
            source_state_digest=payload["source_state_digest"],
            outcome=ResearchTrialOutcome(payload["outcome"]),
            observation=payload["observation"],
            limitations=limitation_rows,
            evidence_refs=evidence_rows,
            predecessor_trial_id=predecessor,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ResearchTrial":
        expected = cls.create(
            question_id=str(state["question_id"]),
            hypothesis_id=str(state["hypothesis_id"]),
            producer_agent_id=str(state["producer_agent_id"]),
            protocol_digest=str(state["protocol_digest"]),
            source_state_digest=str(state["source_state_digest"]),
            outcome=str(state["outcome"]),
            observation=str(state["observation"]),
            limitations=tuple(str(x) for x in state.get("limitations", ())),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            predecessor_trial_id=None
            if state.get("predecessor_trial_id") is None
            else str(state["predecessor_trial_id"]),
        )
        if str(state.get("trial_id", "")) != expected.trial_id:
            raise ValueError("research trial identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("research trial digest mismatch")
        return expected


class ResearchTrialLedger:
    """Append-only trial evidence, including negative and failed attempts."""

    def __init__(self) -> None:
        self._rows: dict[str, ResearchTrial] = {}

    @property
    def digest(self) -> str:
        return canonical_digest(self._payload())

    def record(
        self,
        *,
        question_id: str,
        hypothesis_id: str,
        producer_agent_id: str,
        protocol_digest: str,
        source_state_digest: str,
        outcome: ResearchTrialOutcome | str,
        observation: str,
        limitations: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        predecessor_trial_id: str | None = None,
    ) -> ResearchTrial:
        if predecessor_trial_id is not None:
            predecessor = self.get(predecessor_trial_id)
            if predecessor.question_id != str(question_id):
                raise ValueError("research trial predecessor must belong to the same question")
        row = ResearchTrial.create(
            question_id=question_id,
            hypothesis_id=hypothesis_id,
            producer_agent_id=producer_agent_id,
            protocol_digest=protocol_digest,
            source_state_digest=source_state_digest,
            outcome=outcome,
            observation=observation,
            limitations=limitations,
            evidence_refs=evidence_refs,
            predecessor_trial_id=predecessor_trial_id,
        )
        existing = self._rows.get(row.trial_id)
        if existing is not None:
            if existing != row:
                raise ValueError("research trial id cannot be rebound")
            return existing
        self._rows[row.trial_id] = row
        return row

    def get(self, trial_id: str) -> ResearchTrial:
        try:
            return self._rows[str(trial_id)]
        except KeyError as exc:
            raise KeyError(f"unknown research trial: {trial_id}") from exc

    def records(self) -> tuple[ResearchTrial, ...]:
        return tuple(self._rows[key] for key in sorted(self._rows))

    def records_for_question(self, question_id: str) -> tuple[ResearchTrial, ...]:
        qid = str(question_id)
        return tuple(row for row in self.records() if row.question_id == qid)

    def _payload(self) -> dict[str, Any]:
        return {"trials": [row.to_state() for row in self.records()]}

    def to_state(self) -> dict[str, Any]:
        payload = self._payload()
        return {**payload, "digest": canonical_digest(payload)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ResearchTrialLedger":
        ledger = cls()
        rows = tuple(ResearchTrial.from_state(raw) for raw in state.get("trials", ()))
        pending = {row.trial_id: row for row in rows}
        if len(pending) != len(rows):
            raise ValueError("duplicate research trial id in serialized state")
        while pending:
            progressed = False
            for trial_id, row in tuple(pending.items()):
                predecessor = row.predecessor_trial_id
                if predecessor is not None and predecessor in pending:
                    continue
                if predecessor is not None and predecessor not in ledger._rows:
                    raise ValueError("research trial predecessor missing during restore")
                replayed = ledger.record(
                    question_id=row.question_id,
                    hypothesis_id=row.hypothesis_id,
                    producer_agent_id=row.producer_agent_id,
                    protocol_digest=row.protocol_digest,
                    source_state_digest=row.source_state_digest,
                    outcome=row.outcome,
                    observation=row.observation,
                    limitations=row.limitations,
                    evidence_refs=row.evidence_refs,
                    predecessor_trial_id=row.predecessor_trial_id,
                )
                if replayed != row:
                    raise ValueError("research trial replay mismatch")
                del pending[trial_id]
                progressed = True
            if not progressed:
                raise ValueError("research trial predecessor cycle detected")
        if str(state.get("digest", "")) != ledger.digest:
            raise ValueError("research trial ledger digest mismatch")
        return ledger


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


def _unique_explicit(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    rows = tuple(str(value) for value in values)
    if any(not value.strip() for value in rows):
        raise ValueError(f"{label} must be explicit")
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(rows))


__all__ = (
    "ResearchTrial",
    "ResearchTrialLedger",
    "ResearchTrialOutcome",
)
