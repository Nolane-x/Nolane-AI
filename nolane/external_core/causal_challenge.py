from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from .causal import CausalProgramLedger, ComplementaryExperimentProgram
from .evidence import EvidenceRecord

COMPONENT_ID = "external.causal"
COMPONENT_VERSION = "0.0.2"
SCHEMA_VERSION = "causal-challenge-v1"


class CausalChallengeVerdict(str, Enum):
    SUPPORTED = "supported"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"
    ABSTAIN = "abstain"


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _digest(prefix: str, value: object) -> str:
    return prefix + hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _text(value: object, name: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{name} must be non-empty")
    return result


def _ids(values: Sequence[object], name: str, *, minimum: int = 1) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence")
    rows = tuple(sorted(_text(value, name) for value in values))
    if len(rows) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} values")
    if len(rows) != len(set(rows)):
        raise ValueError(f"{name} must be unique")
    return rows


def _clean(evidence: EvidenceRecord, name: str) -> EvidenceRecord:
    if not isinstance(evidence, EvidenceRecord):
        raise TypeError(f"{name} must be EvidenceRecord")
    if not evidence.passed or evidence.false_accepts or evidence.regressions:
        raise ValueError(f"{name} requires clean passing evidence")
    return evidence


@dataclass(frozen=True, slots=True)
class CausalAblationEvidence:
    removed_intervention_ids: tuple[str, ...]
    evidence: EvidenceRecord
    target_reproduced: bool
    ablation_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "removed_intervention_ids", _ids(self.removed_intervention_ids, "removed intervention ids"))
        object.__setattr__(self, "evidence", _clean(self.evidence, "causal ablation"))
        if not isinstance(self.target_reproduced, bool):
            raise TypeError("target_reproduced must be bool")
        object.__setattr__(self, "ablation_id", _digest("causal-ablation:", self.semantic_state()))

    def semantic_state(self) -> dict[str, object]:
        return {
            "removed_intervention_ids": list(self.removed_intervention_ids),
            "evidence": self.evidence.to_state(),
            "target_reproduced": self.target_reproduced,
        }

    def to_state(self) -> dict[str, object]:
        return {"ablation_id": self.ablation_id, **self.semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "CausalAblationEvidence":
        evidence = state.get("evidence")
        if not isinstance(evidence, Mapping):
            raise TypeError("causal ablation state requires evidence mapping")
        row = cls(
            tuple(state.get("removed_intervention_ids", ())),
            EvidenceRecord.from_state(evidence),
            state["target_reproduced"],
        )
        if str(state.get("ablation_id")) != row.ablation_id:
            raise ValueError("causal ablation identity mismatch")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical causal ablation state")
        return row


@dataclass(frozen=True, slots=True)
class CausalHypothesisChallenge:
    reasoning_hypothesis_id: str
    program_id: str
    program_intervention_ids: tuple[str, ...]
    causal_row_digest: str
    cognitive_library_digest: str
    source_evidence_id: str
    source_verifier_agent_id: str
    ablations: tuple[CausalAblationEvidence, ...]
    independent_evidence: tuple[EvidenceRecord, ...]
    verdict: CausalChallengeVerdict
    reason: str
    promoted: bool = False
    challenge_id: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "reasoning_hypothesis_id", "program_id", "causal_row_digest",
            "cognitive_library_digest", "source_evidence_id", "source_verifier_agent_id", "reason",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        program_ids = _ids(self.program_intervention_ids, "program intervention ids", minimum=2)
        object.__setattr__(self, "program_intervention_ids", program_ids)
        program_set = set(program_ids)

        ablations = tuple(self.ablations)
        if not ablations or not all(isinstance(row, CausalAblationEvidence) for row in ablations):
            raise TypeError("causal ablations must contain CausalAblationEvidence")
        seen: set[tuple[str, ...]] = set()
        for row in ablations:
            removed = set(row.removed_intervention_ids)
            if not removed.issubset(program_set):
                raise ValueError("ablation removes intervention outside causal program")
            if removed == program_set:
                raise ValueError("ablation must preserve a non-empty proper subset")
            if row.removed_intervention_ids in seen:
                raise ValueError("duplicate causal ablation subset")
            if row.evidence.verifier_agent_id == self.source_verifier_agent_id:
                raise ValueError("causal ablation requires independent verifier")
            seen.add(row.removed_intervention_ids)
        object.__setattr__(self, "ablations", tuple(sorted(ablations, key=lambda row: row.ablation_id)))

        evidence = tuple(self.independent_evidence)
        if not evidence:
            raise ValueError("causal challenge requires independent evidence")
        by_id: dict[str, EvidenceRecord] = {}
        for row in evidence:
            row = _clean(row, "independent challenge")
            if row.evidence_id in by_id:
                raise ValueError("independent challenge evidence ids must be unique")
            if row.verifier_agent_id == self.source_verifier_agent_id:
                raise ValueError("independent verifier must differ from source verifier")
            by_id[row.evidence_id] = row
        object.__setattr__(self, "independent_evidence", tuple(by_id[key] for key in sorted(by_id)))

        object.__setattr__(self, "verdict", CausalChallengeVerdict(self.verdict))
        if self.promoted:
            raise ValueError("causal challenge cannot self-promote")
        object.__setattr__(self, "promoted", False)

        if self.verdict is CausalChallengeVerdict.SUPPORTED:
            if self.proper_subset_coverage != 1.0:
                raise ValueError("supported challenge requires complete proper-subset coverage")
            if any(row.target_reproduced for row in self.ablations):
                raise ValueError("supported challenge rejected because a proper subset reproduced target")
        if self.verdict is CausalChallengeVerdict.FALSIFIED and not any(
            row.target_reproduced for row in self.ablations
        ):
            raise ValueError("falsified challenge requires a reproducing proper subset")
        object.__setattr__(self, "challenge_id", _digest("causal-challenge:", self.semantic_state()))

    @property
    def proper_subset_coverage(self) -> float:
        expected = {(value,) for value in self.program_intervention_ids}
        observed = {row.removed_intervention_ids for row in self.ablations if len(row.removed_intervention_ids) == 1}
        return len(expected & observed) / len(expected)

    def semantic_state(self) -> dict[str, object]:
        return {
            "reasoning_hypothesis_id": self.reasoning_hypothesis_id,
            "program_id": self.program_id,
            "program_intervention_ids": list(self.program_intervention_ids),
            "causal_row_digest": self.causal_row_digest,
            "cognitive_library_digest": self.cognitive_library_digest,
            "source_evidence_id": self.source_evidence_id,
            "source_verifier_agent_id": self.source_verifier_agent_id,
            "ablations": [row.to_state() for row in self.ablations],
            "independent_evidence": [row.to_state() for row in self.independent_evidence],
            "verdict": self.verdict.value,
            "reason": self.reason,
            "promoted": False,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "challenge_id": self.challenge_id, **self.semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "CausalHypothesisChallenge":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported causal challenge schema")
        ablations = tuple(CausalAblationEvidence.from_state(row) for row in state.get("ablations", ()))
        independent = tuple(EvidenceRecord.from_state(row) for row in state.get("independent_evidence", ()))
        row = cls(
            state["reasoning_hypothesis_id"], state["program_id"], tuple(state["program_intervention_ids"]),
            state["causal_row_digest"], state["cognitive_library_digest"], state["source_evidence_id"],
            state["source_verifier_agent_id"], ablations, independent,
            CausalChallengeVerdict(str(state["verdict"])), state["reason"], bool(state.get("promoted", False)),
        )
        if str(state.get("challenge_id")) != row.challenge_id:
            raise ValueError("causal challenge identity mismatch")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical causal challenge state")
        return row


def _accepted_row(ledger: CausalProgramLedger, program_id: str):
    if not isinstance(ledger, CausalProgramLedger):
        raise TypeError("ledger must be CausalProgramLedger")
    wanted = _text(program_id, "program id")
    for row in ledger.to_state().get("programs", ()):
        program_state = row.get("program")
        evidence_state = row.get("evidence")
        if not isinstance(program_state, Mapping) or not isinstance(evidence_state, Mapping):
            continue
        if str(program_state.get("program_id")) != wanted:
            continue
        program = ComplementaryExperimentProgram.from_state(program_state)
        evidence = _clean(EvidenceRecord.from_state(evidence_state), "accepted causal program")
        return program, evidence, _digest("causal-row:", {"program": program.to_state(), "evidence": evidence.to_state()})
    raise KeyError(f"unknown accepted causal program: {wanted}")


def bind_causal_hypothesis_challenge(
    ledger: CausalProgramLedger,
    *,
    reasoning_hypothesis_id: str,
    program_id: str,
    ablations: Sequence[CausalAblationEvidence],
    independent_evidence: Sequence[EvidenceRecord],
    verdict: CausalChallengeVerdict,
    reason: str,
) -> CausalHypothesisChallenge:
    program, source, row_digest = _accepted_row(ledger, program_id)
    return CausalHypothesisChallenge(
        _text(reasoning_hypothesis_id, "reasoning hypothesis id"),
        program.program_id,
        tuple(row.intervention_id for row in program.interventions),
        row_digest,
        ledger.cognitive_library_digest,
        source.evidence_id,
        source.verifier_agent_id,
        tuple(ablations),
        tuple(independent_evidence),
        CausalChallengeVerdict(verdict),
        _text(reason, "reason"),
        False,
    )


__all__ = (
    "COMPONENT_ID", "COMPONENT_VERSION", "SCHEMA_VERSION",
    "CausalChallengeVerdict", "CausalAblationEvidence", "CausalHypothesisChallenge",
    "bind_causal_hypothesis_challenge",
)
