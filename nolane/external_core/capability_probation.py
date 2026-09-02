from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest

from .capability_acquisition import (
    CapabilityAcquisitionGovernor,
    CapabilityCandidate,
    CapabilityKind as AcquisitionCapabilityKind,
    CapabilityRecord,
    CapabilityState,
)
from .evidence import EvidenceRecord
from .reasoning_invention import CapabilityGap, CapabilityKind as ReasoningCapabilityKind


COMPONENT_ID = "external.capability_acquisition"
COMPONENT_VERSION = "0.0.2"
SCHEMA_VERSION = "capability-probation-v1"

_KIND_MAP = {
    AcquisitionCapabilityKind.OPERATOR_FAMILY: ReasoningCapabilityKind.OPERATOR,
    AcquisitionCapabilityKind.LEARNED_ABSTRACTION: ReasoningCapabilityKind.ABSTRACTION,
}


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


def _optional_ids(values: Sequence[object], name: str) -> tuple[str, ...]:
    return _ids(values, name, minimum=0)


def _score(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a finite numeric value")
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a finite numeric value") from exc
    if not math.isfinite(score):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")
    return score


def _clean_evidence(values: Sequence[EvidenceRecord]) -> tuple[EvidenceRecord, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("independent evidence must be a sequence")
    rows = tuple(values)
    if not rows or not all(isinstance(row, EvidenceRecord) for row in rows):
        raise TypeError("independent evidence must contain EvidenceRecord values")
    by_id: dict[str, EvidenceRecord] = {}
    for row in rows:
        if not row.passed or row.false_accepts or row.regressions:
            raise ValueError("independent probation requires clean passing evidence")
        if row.evidence_id in by_id:
            raise ValueError("independent evidence ids must be unique")
        by_id[row.evidence_id] = row
    return tuple(by_id[key] for key in sorted(by_id))


def _receipt_id(state: Mapping[str, object]) -> str:
    return f"capability-probation:{canonical_digest(dict(state))}"


@dataclass(frozen=True, slots=True)
class CapabilityProbationReceipt:
    candidate_id: str
    gap_id: str
    cognitive_library_baseline_digest: str
    governor_min_reliability: float
    candidate_synthesis_id: str
    acceptance_test_ids: tuple[str, ...]
    holdout_test_ids: tuple[str, ...]
    environment_ids: tuple[str, ...]
    gap_evidence_ids: tuple[str, ...]
    independent_evidence: tuple[EvidenceRecord, ...]
    causal_challenge_ids: tuple[str, ...]
    experiment_receipt_ids: tuple[str, ...]
    verified_challenge_id: str | None
    independent_passed: bool
    challenge_passed: bool
    reliability: float
    promoted: bool = False
    receipt_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _text(self.candidate_id, "candidate id"))
        object.__setattr__(self, "gap_id", _text(self.gap_id, "gap id"))
        object.__setattr__(
            self,
            "cognitive_library_baseline_digest",
            _text(self.cognitive_library_baseline_digest, "cognitive library baseline digest"),
        )
        object.__setattr__(
            self,
            "governor_min_reliability",
            _score(self.governor_min_reliability, "governor minimum reliability"),
        )
        object.__setattr__(
            self,
            "candidate_synthesis_id",
            _text(self.candidate_synthesis_id, "candidate synthesis id"),
        )
        acceptance = _ids(self.acceptance_test_ids, "acceptance test ids")
        holdouts = _ids(self.holdout_test_ids, "holdout test ids")
        environments = _ids(self.environment_ids, "environment ids")
        gap_evidence = _ids(self.gap_evidence_ids, "gap evidence ids")
        independent = _clean_evidence(self.independent_evidence)
        causal = _optional_ids(self.causal_challenge_ids, "causal challenge ids")
        experiments = _optional_ids(self.experiment_receipt_ids, "experiment receipt ids")
        verified = (
            None
            if self.verified_challenge_id is None
            else _text(self.verified_challenge_id, "verified challenge id")
        )
        if not set(acceptance).issubset(holdouts):
            raise ValueError("holdout test ids must cover every acceptance test")
        if not isinstance(self.independent_passed, bool):
            raise TypeError("independent_passed must be bool")
        if not isinstance(self.challenge_passed, bool):
            raise TypeError("challenge_passed must be bool")
        if self.challenge_passed and not (verified or causal or experiments):
            raise ValueError("passing challenge gate requires challenge support")
        reliability = _score(self.reliability, "probation reliability")
        if self.promoted:
            raise ValueError("capability probation receipt cannot self-promote")

        source_witnesses = set(gap_evidence)
        # gap_evidence_ids are evidence identities, not verifier identities; verifier
        # phase separation is checked by the binder while the original Gap is present.
        del source_witnesses

        object.__setattr__(self, "acceptance_test_ids", acceptance)
        object.__setattr__(self, "holdout_test_ids", holdouts)
        object.__setattr__(self, "environment_ids", environments)
        object.__setattr__(self, "gap_evidence_ids", gap_evidence)
        object.__setattr__(self, "independent_evidence", independent)
        object.__setattr__(self, "causal_challenge_ids", causal)
        object.__setattr__(self, "experiment_receipt_ids", experiments)
        object.__setattr__(self, "verified_challenge_id", verified)
        object.__setattr__(self, "reliability", reliability)
        object.__setattr__(self, "promoted", False)

        evidence_ids = self.probation_evidence_ids
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("probation evidence identities must be globally unique")
        object.__setattr__(self, "receipt_id", _receipt_id(self.semantic_state()))

    @property
    def probation_evidence_ids(self) -> tuple[str, ...]:
        rows = [*self.gap_evidence_ids]
        rows.extend(row.evidence_id for row in self.independent_evidence)
        rows.extend(self.causal_challenge_ids)
        rows.extend(self.experiment_receipt_ids)
        if self.verified_challenge_id is not None:
            rows.append(self.verified_challenge_id)
        return tuple(sorted(rows))

    def semantic_state(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "gap_id": self.gap_id,
            "cognitive_library_baseline_digest": self.cognitive_library_baseline_digest,
            "governor_min_reliability": self.governor_min_reliability,
            "candidate_synthesis_id": self.candidate_synthesis_id,
            "acceptance_test_ids": list(self.acceptance_test_ids),
            "holdout_test_ids": list(self.holdout_test_ids),
            "environment_ids": list(self.environment_ids),
            "gap_evidence_ids": list(self.gap_evidence_ids),
            "independent_evidence": [row.to_state() for row in self.independent_evidence],
            "causal_challenge_ids": list(self.causal_challenge_ids),
            "experiment_receipt_ids": list(self.experiment_receipt_ids),
            "verified_challenge_id": self.verified_challenge_id,
            "independent_passed": self.independent_passed,
            "challenge_passed": self.challenge_passed,
            "reliability": self.reliability,
            "promoted": False,
        }

    def to_state(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "receipt_id": self.receipt_id,
            **self.semantic_state(),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "CapabilityProbationReceipt":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported capability probation schema")
        raw_evidence = state.get("independent_evidence", ())
        if isinstance(raw_evidence, (str, bytes)) or not isinstance(raw_evidence, Sequence):
            raise TypeError("independent evidence state must be a sequence")
        evidence: list[EvidenceRecord] = []
        for item in raw_evidence:
            if not isinstance(item, Mapping):
                raise TypeError("independent evidence state rows must be mappings")
            evidence.append(EvidenceRecord.from_state(item))
        row = cls(
            candidate_id=state["candidate_id"],
            gap_id=state["gap_id"],
            cognitive_library_baseline_digest=state["cognitive_library_baseline_digest"],
            governor_min_reliability=state["governor_min_reliability"],
            candidate_synthesis_id=state["candidate_synthesis_id"],
            acceptance_test_ids=tuple(state.get("acceptance_test_ids", ())),
            holdout_test_ids=tuple(state.get("holdout_test_ids", ())),
            environment_ids=tuple(state.get("environment_ids", ())),
            gap_evidence_ids=tuple(state.get("gap_evidence_ids", ())),
            independent_evidence=tuple(evidence),
            causal_challenge_ids=tuple(state.get("causal_challenge_ids", ())),
            experiment_receipt_ids=tuple(state.get("experiment_receipt_ids", ())),
            verified_challenge_id=(
                None if state.get("verified_challenge_id") is None else state["verified_challenge_id"]
            ),
            independent_passed=state["independent_passed"],
            challenge_passed=state["challenge_passed"],
            reliability=state["reliability"],
            promoted=bool(state.get("promoted", False)),
        )
        if str(state.get("receipt_id")) != row.receipt_id:
            raise ValueError("capability probation receipt identity mismatch")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical capability probation receipt state")
        return row


def _probation_record(
    governor: CapabilityAcquisitionGovernor,
    candidate: CapabilityCandidate,
) -> CapabilityRecord:
    if not isinstance(governor, CapabilityAcquisitionGovernor):
        raise TypeError("governor must be CapabilityAcquisitionGovernor")
    if not isinstance(candidate, CapabilityCandidate):
        raise TypeError("candidate must be CapabilityCandidate")
    try:
        record = governor.record(candidate.candidate_id)
    except KeyError as exc:
        raise ValueError("candidate must be admitted to capability acquisition") from exc
    if record.state is not CapabilityState.PROBATION:
        raise ValueError("candidate must already be in probation")
    if record.candidate != candidate:
        raise ValueError("probation candidate does not match governor record")
    if not record.baseline_digest:
        raise ValueError("probation record is missing cognitive library baseline")
    return record


def bind_capability_probation_receipt(
    governor: CapabilityAcquisitionGovernor,
    *,
    candidate: CapabilityCandidate,
    gap: CapabilityGap,
    holdout_test_ids: Sequence[str],
    environment_ids: Sequence[str],
    independent_evidence: Sequence[EvidenceRecord],
    causal_challenge_ids: Sequence[str] = (),
    experiment_receipt_ids: Sequence[str] = (),
    independent_passed: bool,
    challenge_passed: bool,
    reliability: float,
) -> CapabilityProbationReceipt:
    record = _probation_record(governor, candidate)
    if not isinstance(gap, CapabilityGap):
        raise TypeError("gap must be Reasoning/Invention CapabilityGap")
    baseline = str(record.baseline_digest)
    if governor.library.digest != baseline:
        raise ValueError("cognitive library baseline drifted during probation")
    if gap.cognitive_library_digest != baseline:
        raise ValueError("capability gap baseline does not match probation baseline")
    expected_kind = _KIND_MAP.get(candidate.kind)
    if expected_kind is None or gap.capability_kind is not expected_kind:
        raise ValueError("capability gap kind does not match acquisition candidate kind")

    holdouts = _ids(tuple(holdout_test_ids), "holdout test ids")
    if not set(gap.acceptance_test_ids).issubset(holdouts):
        raise ValueError("holdout test ids must cover every acceptance test")
    environments = _ids(tuple(environment_ids), "environment ids")
    evidence = _clean_evidence(tuple(independent_evidence))
    source_verifiers = {row.witness_id for row in gap.insufficiency_evidence}
    if any(row.verifier_agent_id in source_verifiers for row in evidence):
        raise ValueError("independent verifier must differ from capability-gap witnesses")

    return CapabilityProbationReceipt(
        candidate_id=candidate.candidate_id,
        gap_id=gap.gap_id,
        cognitive_library_baseline_digest=baseline,
        governor_min_reliability=governor.min_reliability,
        candidate_synthesis_id=gap.candidate_synthesis_id,
        acceptance_test_ids=gap.acceptance_test_ids,
        holdout_test_ids=holdouts,
        environment_ids=environments,
        gap_evidence_ids=tuple(row.evidence_id for row in gap.insufficiency_evidence),
        independent_evidence=evidence,
        causal_challenge_ids=tuple(causal_challenge_ids),
        experiment_receipt_ids=tuple(experiment_receipt_ids),
        verified_challenge_id=gap.verified_challenge_id,
        independent_passed=independent_passed,
        challenge_passed=challenge_passed,
        reliability=reliability,
        promoted=False,
    )


def apply_capability_probation_receipt(
    governor: CapabilityAcquisitionGovernor,
    receipt: CapabilityProbationReceipt,
) -> CapabilityRecord:
    if not isinstance(governor, CapabilityAcquisitionGovernor):
        raise TypeError("governor must be CapabilityAcquisitionGovernor")
    if not isinstance(receipt, CapabilityProbationReceipt):
        raise TypeError("receipt must be CapabilityProbationReceipt")
    # Reconstruct before trusting a detached caller-provided object.
    CapabilityProbationReceipt.from_state(receipt.to_state())
    try:
        current = governor.record(receipt.candidate_id)
    except KeyError as exc:
        raise ValueError("receipt candidate is not admitted to capability acquisition") from exc
    if current.state is not CapabilityState.PROBATION:
        raise ValueError("receipt candidate must be in probation")
    if current.baseline_digest != receipt.cognitive_library_baseline_digest:
        raise ValueError("probation baseline does not match receipt baseline")
    if governor.library.digest != receipt.cognitive_library_baseline_digest:
        raise ValueError("cognitive library baseline drifted after probation receipt binding")
    if governor.min_reliability != receipt.governor_min_reliability:
        raise ValueError("probation reliability threshold changed after receipt binding")

    if current.evidence_ids:
        if (
            current.evidence_ids == receipt.probation_evidence_ids
            and current.independent_passed is receipt.independent_passed
            and current.challenge_passed is receipt.challenge_passed
            and current.reliability == receipt.reliability
        ):
            return current
        raise ValueError("conflicting probation receipt for candidate")

    library_before = governor.library.digest
    updated = governor.record_probation(
        receipt.candidate_id,
        evidence_ids=receipt.probation_evidence_ids,
        independent_passed=receipt.independent_passed,
        challenge_passed=receipt.challenge_passed,
        reliability=receipt.reliability,
    )
    if governor.library.digest != library_before:
        raise RuntimeError("probation application mutated Cognitive Library")
    if updated.state is CapabilityState.PROMOTED:
        raise RuntimeError("probation application cannot promote capability")
    return updated


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "CapabilityProbationReceipt",
    "bind_capability_probation_receipt",
    "apply_capability_probation_receipt",
)
