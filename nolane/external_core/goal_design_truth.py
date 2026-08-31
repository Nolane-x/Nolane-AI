"""Assumption truth-maintenance authority for D. Goal / Design.

This module treats assumptions as first-class, evidence-backed authority inputs
without making them mutable truth flags. Claims, evidence and retractions are
content-addressed facts; effective assumption status is derived from those facts
and from the dependency graph. Decision code can therefore bind an exact truth
snapshot and later invalidate authority when the supporting world-model changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Iterable, Mapping

from .goal_design import DecisionClass, stable_digest

__version__ = "0.1.0"


class AssumptionStatus(str, Enum):
    UNKNOWN = "unknown"
    SUPPORTED = "supported"
    CONTESTED = "contested"
    REFUTED = "refuted"


class AssumptionPolarity(str, Enum):
    SUPPORTS = "supports"
    REFUTES = "refutes"


def _normalized_refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _bounded(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return value


@dataclass(frozen=True)
class AssumptionClaim:
    assumption_id: str
    statement: str
    criticality: float = 0.5
    depends_on: tuple[str, ...] = ()
    requirement_refs: tuple[str, ...] = ()
    plan_refs: tuple[str, ...] = ()
    component_refs: tuple[str, ...] = ()
    integration_candidate_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.assumption_id).strip() or not str(self.statement).strip():
            raise ValueError("assumption_id and statement are required")
        _bounded("criticality", self.criticality)
        object.__setattr__(self, "depends_on", _normalized_refs(self.depends_on))
        object.__setattr__(self, "requirement_refs", _normalized_refs(self.requirement_refs))
        object.__setattr__(self, "plan_refs", _normalized_refs(self.plan_refs))
        object.__setattr__(self, "component_refs", _normalized_refs(self.component_refs))
        object.__setattr__(
            self,
            "integration_candidate_refs",
            _normalized_refs(self.integration_candidate_refs),
        )

    @property
    def digest(self) -> str:
        return stable_digest({
            "assumption_claim": {
                "assumption_id": self.assumption_id,
                "statement": self.statement,
                "criticality": float(self.criticality),
                "depends_on": self.depends_on,
                "requirement_refs": self.requirement_refs,
                "plan_refs": self.plan_refs,
                "component_refs": self.component_refs,
                "integration_candidate_refs": self.integration_candidate_refs,
            }
        })


@dataclass(frozen=True)
class AssumptionEvidence:
    evidence_id: str
    assumption_id: str
    polarity: AssumptionPolarity
    confidence: float
    evidence_ref: str

    def __post_init__(self) -> None:
        if not str(self.evidence_id).strip() or not str(self.assumption_id).strip():
            raise ValueError("evidence_id and assumption_id are required")
        if not str(self.evidence_ref).strip():
            raise ValueError("assumption evidence requires an evidence_ref")
        _bounded("confidence", self.confidence)

    @property
    def digest(self) -> str:
        return stable_digest({
            "assumption_evidence": {
                "evidence_id": self.evidence_id,
                "assumption_id": self.assumption_id,
                "polarity": self.polarity.value,
                "confidence": float(self.confidence),
                "evidence_ref": self.evidence_ref,
            }
        })


@dataclass(frozen=True)
class EvidenceRetraction:
    evidence_id: str
    reason_ref: str

    def __post_init__(self) -> None:
        if not str(self.evidence_id).strip() or not str(self.reason_ref).strip():
            raise ValueError("evidence retraction requires evidence_id and reason_ref")

    @property
    def digest(self) -> str:
        return stable_digest({
            "assumption_evidence_retraction": {
                "evidence_id": self.evidence_id,
                "reason_ref": self.reason_ref,
            }
        })


@dataclass(frozen=True)
class AssumptionAssessment:
    assumption_id: str
    direct_status: AssumptionStatus
    status: AssumptionStatus
    support_score: float
    refute_score: float
    dependency_blockers: tuple[str, ...]
    evidence_state_digest: str
    digest: str


@dataclass(frozen=True)
class AssumptionSnapshot:
    assumption_ids: tuple[str, ...]
    assessments: tuple[AssumptionAssessment, ...]
    digest: str


@dataclass(frozen=True)
class AssumptionImpactReport:
    changed_assumption_ids: tuple[str, ...]
    affected_assumption_ids: tuple[str, ...]
    requirement_refs: tuple[str, ...]
    plan_refs: tuple[str, ...]
    component_refs: tuple[str, ...]
    integration_candidate_refs: tuple[str, ...]
    digest: str


class AssumptionTruthMaintenance:
    """Content-addressed truth-maintenance system for Goal/Design assumptions."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        *,
        support_threshold: float = 0.67,
        costly_criticality_threshold: float = 0.5,
    ) -> None:
        self.support_threshold = _bounded("support_threshold", support_threshold)
        self.costly_criticality_threshold = _bounded(
            "costly_criticality_threshold", costly_criticality_threshold
        )
        self._claims: dict[str, AssumptionClaim] = {}
        self._evidence: dict[str, AssumptionEvidence] = {}
        self._retractions: dict[str, EvidenceRetraction] = {}

    @property
    def digest(self) -> str:
        return stable_digest({"assumption_truth_maintenance": self.to_state()})

    def register(self, claim: AssumptionClaim) -> AssumptionClaim:
        existing = self._claims.get(claim.assumption_id)
        if existing is not None and existing != claim:
            raise ValueError(
                f"assumption identity {claim.assumption_id} cannot be rebound to a different claim"
            )
        self._claims[claim.assumption_id] = claim
        return claim

    def add_evidence(self, evidence: AssumptionEvidence) -> AssumptionEvidence:
        if evidence.assumption_id not in self._claims:
            raise ValueError(
                f"assumption evidence references unknown assumption {evidence.assumption_id}"
            )
        existing = self._evidence.get(evidence.evidence_id)
        if existing is not None and existing != evidence:
            raise ValueError(
                f"evidence identity {evidence.evidence_id} cannot be rebound to different content"
            )
        self._evidence[evidence.evidence_id] = evidence
        return evidence

    def retract_evidence(self, evidence_id: str, *, reason_ref: str) -> EvidenceRetraction:
        evidence_id = str(evidence_id).strip()
        if evidence_id not in self._evidence:
            raise ValueError(f"cannot retract unknown assumption evidence {evidence_id}")
        retraction = EvidenceRetraction(evidence_id=evidence_id, reason_ref=reason_ref)
        existing = self._retractions.get(evidence_id)
        if existing is not None and existing != retraction:
            raise ValueError(
                f"evidence {evidence_id} already has a different immutable retraction"
            )
        self._retractions[evidence_id] = retraction
        return retraction

    def get(self, assumption_id: str) -> AssumptionClaim:
        try:
            return self._claims[str(assumption_id)]
        except KeyError as exc:
            raise ValueError(f"unknown assumption {assumption_id}") from exc

    @staticmethod
    def _aggregate(confidences: Iterable[float]) -> float:
        remaining = 1.0
        for confidence in confidences:
            remaining *= 1.0 - float(confidence)
        return 1.0 - remaining

    def _direct_assessment(self, assumption_id: str) -> tuple[AssumptionStatus, float, float, str]:
        evidence = tuple(
            item
            for item in self._evidence.values()
            if item.assumption_id == assumption_id and item.evidence_id not in self._retractions
        )
        support = self._aggregate(
            item.confidence for item in evidence if item.polarity is AssumptionPolarity.SUPPORTS
        )
        refute = self._aggregate(
            item.confidence for item in evidence if item.polarity is AssumptionPolarity.REFUTES
        )
        threshold = self.support_threshold
        if support >= threshold and refute >= threshold:
            status = AssumptionStatus.CONTESTED
        elif refute >= threshold:
            status = AssumptionStatus.REFUTED
        elif support >= threshold:
            status = AssumptionStatus.SUPPORTED
        else:
            status = AssumptionStatus.UNKNOWN

        historical_evidence = tuple(
            sorted(
                (
                    item.evidence_id,
                    item.digest,
                    self._retractions[item.evidence_id].digest
                    if item.evidence_id in self._retractions
                    else None,
                )
                for item in self._evidence.values()
                if item.assumption_id == assumption_id
            )
        )
        evidence_state_digest = stable_digest(
            {"assumption_evidence_state": historical_evidence}
        )
        return status, support, refute, evidence_state_digest

    def _assessment(
        self,
        assumption_id: str,
        *,
        stack: tuple[str, ...],
        cache: dict[str, AssumptionAssessment],
    ) -> AssumptionAssessment:
        if assumption_id in cache:
            return cache[assumption_id]
        if assumption_id in stack:
            cycle = " -> ".join(stack + (assumption_id,))
            raise ValueError(f"assumption dependency cycle detected: {cycle}")
        claim = self.get(assumption_id)
        direct_status, support, refute, evidence_state_digest = self._direct_assessment(
            assumption_id
        )
        dependency_assessments = tuple(
            self._assessment(dep, stack=stack + (assumption_id,), cache=cache)
            for dep in claim.depends_on
        )
        dependency_blockers = tuple(
            sorted(
                dep.assumption_id
                for dep in dependency_assessments
                if dep.status is not AssumptionStatus.SUPPORTED
            )
        )

        if direct_status is AssumptionStatus.REFUTED or any(
            dep.status is AssumptionStatus.REFUTED for dep in dependency_assessments
        ):
            effective = AssumptionStatus.REFUTED
        elif direct_status is AssumptionStatus.CONTESTED or any(
            dep.status is AssumptionStatus.CONTESTED for dep in dependency_assessments
        ):
            effective = AssumptionStatus.CONTESTED
        elif direct_status is AssumptionStatus.SUPPORTED and not dependency_blockers:
            effective = AssumptionStatus.SUPPORTED
        else:
            effective = AssumptionStatus.UNKNOWN

        payload = {
            "assumption_id": assumption_id,
            "claim_digest": claim.digest,
            "direct_status": direct_status.value,
            "status": effective.value,
            "support_score": support,
            "refute_score": refute,
            "dependency_blockers": dependency_blockers,
            "dependency_assessment_digests": tuple(
                dep.digest for dep in dependency_assessments
            ),
            "evidence_state_digest": evidence_state_digest,
        }
        result = AssumptionAssessment(
            assumption_id=assumption_id,
            direct_status=direct_status,
            status=effective,
            support_score=support,
            refute_score=refute,
            dependency_blockers=dependency_blockers,
            evidence_state_digest=evidence_state_digest,
            digest=stable_digest({"assumption_assessment": payload}),
        )
        cache[assumption_id] = result
        return result

    def assessment(self, assumption_id: str) -> AssumptionAssessment:
        return self._assessment(str(assumption_id), stack=(), cache={})

    def _closure(self, required_ids: Iterable[str]) -> tuple[str, ...]:
        seeds = _normalized_refs(required_ids)
        if not seeds:
            seeds = tuple(sorted(self._claims))
        closure: set[str] = set()
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(assumption_id: str) -> None:
            if assumption_id in visiting:
                raise ValueError(f"assumption dependency cycle detected at {assumption_id}")
            if assumption_id in visited:
                return
            claim = self.get(assumption_id)
            visiting.add(assumption_id)
            for dependency in claim.depends_on:
                if dependency not in self._claims:
                    raise ValueError(
                        f"assumption {assumption_id} depends on unknown assumption {dependency}"
                    )
                visit(dependency)
            visiting.remove(assumption_id)
            visited.add(assumption_id)
            closure.add(assumption_id)

        for assumption_id in seeds:
            visit(assumption_id)
        return tuple(sorted(closure))

    def snapshot(self, required_ids: Iterable[str] = ()) -> AssumptionSnapshot:
        assumption_ids = self._closure(required_ids)
        cache: dict[str, AssumptionAssessment] = {}
        assessments = tuple(
            self._assessment(assumption_id, stack=(), cache=cache)
            for assumption_id in assumption_ids
        )
        payload = {
            "assumption_ids": assumption_ids,
            "assessment_digests": tuple(assessment.digest for assessment in assessments),
        }
        return AssumptionSnapshot(
            assumption_ids=assumption_ids,
            assessments=assessments,
            digest=stable_digest({"assumption_truth_snapshot": payload}),
        )

    def analyze_change(self, changed_ids: Iterable[str]) -> AssumptionImpactReport:
        changed = set(_normalized_refs(changed_ids))
        for assumption_id in changed:
            self.get(assumption_id)
        # Validate the complete graph before deriving authority impact.
        self._closure(self._claims)

        affected = set(changed)
        progressed = True
        while progressed:
            before = len(affected)
            for claim in self._claims.values():
                if affected.intersection(claim.depends_on):
                    affected.add(claim.assumption_id)
            progressed = len(affected) != before

        claims = tuple(self._claims[assumption_id] for assumption_id in sorted(affected))
        requirement_refs = _normalized_refs(
            ref for claim in claims for ref in claim.requirement_refs
        )
        plan_refs = _normalized_refs(ref for claim in claims for ref in claim.plan_refs)
        component_refs = _normalized_refs(
            ref for claim in claims for ref in claim.component_refs
        )
        candidate_refs = _normalized_refs(
            ref for claim in claims for ref in claim.integration_candidate_refs
        )
        payload = {
            "changed_assumption_ids": tuple(sorted(changed)),
            "affected_assumption_ids": tuple(sorted(affected)),
            "requirement_refs": requirement_refs,
            "plan_refs": plan_refs,
            "component_refs": component_refs,
            "integration_candidate_refs": candidate_refs,
        }
        return AssumptionImpactReport(
            changed_assumption_ids=payload["changed_assumption_ids"],
            affected_assumption_ids=payload["affected_assumption_ids"],
            requirement_refs=requirement_refs,
            plan_refs=plan_refs,
            component_refs=component_refs,
            integration_candidate_refs=candidate_refs,
            digest=stable_digest({"assumption_impact": payload}),
        )

    def decision_blockers(
        self,
        assumption_ids: Iterable[str],
        decision_class: DecisionClass,
    ) -> tuple[str, ...]:
        blockers: list[str] = []
        snapshot = self.snapshot(assumption_ids)
        assessment_by_id = {
            assessment.assumption_id: assessment for assessment in snapshot.assessments
        }
        requested = _normalized_refs(assumption_ids)
        for assumption_id in requested:
            claim = self.get(assumption_id)
            assessment = assessment_by_id[assumption_id]
            if assessment.status is AssumptionStatus.REFUTED:
                blockers.append(f"assumption {assumption_id} is refuted")
                continue
            if decision_class is DecisionClass.IRREVERSIBLE:
                if assessment.status is not AssumptionStatus.SUPPORTED:
                    blockers.append(
                        f"irreversible decision requires supported assumption {assumption_id}; "
                        f"observed {assessment.status.value}"
                    )
            elif decision_class is DecisionClass.COSTLY_REVERSIBLE:
                if (
                    assessment.status is not AssumptionStatus.SUPPORTED
                    and claim.criticality >= self.costly_criticality_threshold
                ):
                    blockers.append(
                        f"costly reversible decision has unsettled high-criticality assumption "
                        f"{assumption_id}: {assessment.status.value}"
                    )
        return tuple(sorted(blockers))

    def to_state(self) -> dict[str, Any]:
        claims = [
            {
                "assumption_id": claim.assumption_id,
                "statement": claim.statement,
                "criticality": float(claim.criticality),
                "depends_on": list(claim.depends_on),
                "requirement_refs": list(claim.requirement_refs),
                "plan_refs": list(claim.plan_refs),
                "component_refs": list(claim.component_refs),
                "integration_candidate_refs": list(claim.integration_candidate_refs),
                "digest": claim.digest,
            }
            for claim in (self._claims[key] for key in sorted(self._claims))
        ]
        evidence = [
            {
                "evidence_id": item.evidence_id,
                "assumption_id": item.assumption_id,
                "polarity": item.polarity.value,
                "confidence": float(item.confidence),
                "evidence_ref": item.evidence_ref,
                "digest": item.digest,
            }
            for item in (self._evidence[key] for key in sorted(self._evidence))
        ]
        retractions = [
            {
                "evidence_id": item.evidence_id,
                "reason_ref": item.reason_ref,
                "digest": item.digest,
            }
            for item in (self._retractions[key] for key in sorted(self._retractions))
        ]
        return {
            "schema_version": self.SCHEMA_VERSION,
            "support_threshold": self.support_threshold,
            "costly_criticality_threshold": self.costly_criticality_threshold,
            "claims": claims,
            "evidence": evidence,
            "retractions": retractions,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AssumptionTruthMaintenance":
        if int(state.get("schema_version", cls.SCHEMA_VERSION)) != cls.SCHEMA_VERSION:
            raise ValueError("unsupported assumption truth-maintenance schema version")
        truth = cls(
            support_threshold=float(state.get("support_threshold", 0.67)),
            costly_criticality_threshold=float(
                state.get("costly_criticality_threshold", 0.5)
            ),
        )
        for row in state.get("claims", ()):
            claim = AssumptionClaim(
                assumption_id=str(row["assumption_id"]),
                statement=str(row["statement"]),
                criticality=float(row.get("criticality", 0.5)),
                depends_on=tuple(str(x) for x in row.get("depends_on", ())),
                requirement_refs=tuple(str(x) for x in row.get("requirement_refs", ())),
                plan_refs=tuple(str(x) for x in row.get("plan_refs", ())),
                component_refs=tuple(str(x) for x in row.get("component_refs", ())),
                integration_candidate_refs=tuple(
                    str(x) for x in row.get("integration_candidate_refs", ())
                ),
            )
            if str(row.get("digest", "")) != claim.digest:
                raise ValueError(
                    f"assumption claim digest mismatch for {claim.assumption_id}"
                )
            truth.register(claim)

        for row in state.get("evidence", ()):
            item = AssumptionEvidence(
                evidence_id=str(row["evidence_id"]),
                assumption_id=str(row["assumption_id"]),
                polarity=AssumptionPolarity(str(row["polarity"])),
                confidence=float(row["confidence"]),
                evidence_ref=str(row["evidence_ref"]),
            )
            if str(row.get("digest", "")) != item.digest:
                raise ValueError(
                    f"assumption evidence digest mismatch for {item.evidence_id}"
                )
            truth.add_evidence(item)

        for row in state.get("retractions", ()):
            retraction = EvidenceRetraction(
                evidence_id=str(row["evidence_id"]),
                reason_ref=str(row["reason_ref"]),
            )
            if str(row.get("digest", "")) != retraction.digest:
                raise ValueError(
                    f"assumption evidence retraction digest mismatch for {retraction.evidence_id}"
                )
            truth.retract_evidence(
                retraction.evidence_id,
                reason_ref=retraction.reason_ref,
            )
        return truth


__all__ = [
    "AssumptionAssessment",
    "AssumptionClaim",
    "AssumptionEvidence",
    "AssumptionImpactReport",
    "AssumptionPolarity",
    "AssumptionSnapshot",
    "AssumptionStatus",
    "AssumptionTruthMaintenance",
    "EvidenceRetraction",
]
