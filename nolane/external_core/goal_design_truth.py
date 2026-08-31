"""Assumption truth-maintenance authority for D. Goal / Design.

This module treats assumptions as first-class, evidence-backed authority inputs
without making them mutable truth flags. Claims, evidence, retractions and
independent justification routes are content-addressed facts. Effective truth is
derived from those facts and the justification graph.

Legacy ``depends_on`` remains one conjunctive support route. Explicit
``AssumptionJustification`` objects add independent OR routes: every premise
inside one route is conjunctive, while any surviving route can keep a claim from
being retracted solely because another route failed. This preserves historical
v1 snapshot identity when no explicit justifications exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Iterable, Mapping

from .goal_design import DecisionClass, stable_digest

__version__ = "0.2.0"


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
class AssumptionJustification:
    """One immutable independent support route for an assumption.

    ``premise_refs`` is an AND set. Multiple justification objects targeting the
    same assumption are OR alternatives. ``provenance_ref`` anchors the route to
    the argument/evidence provenance that introduced it.
    """

    justification_id: str
    assumption_id: str
    premise_refs: tuple[str, ...]
    provenance_ref: str

    def __post_init__(self) -> None:
        if not str(self.justification_id).strip() or not str(self.assumption_id).strip():
            raise ValueError("justification_id and assumption_id are required")
        if not str(self.provenance_ref).strip():
            raise ValueError("assumption justification requires provenance_ref")
        premise_refs = _normalized_refs(self.premise_refs)
        if not premise_refs:
            raise ValueError("assumption justification requires at least one premise")
        if self.assumption_id in premise_refs:
            raise ValueError("assumption justification cannot directly depend on itself")
        object.__setattr__(self, "premise_refs", premise_refs)

    @property
    def digest(self) -> str:
        return stable_digest({
            "assumption_justification": {
                "justification_id": self.justification_id,
                "assumption_id": self.assumption_id,
                "premise_refs": self.premise_refs,
                "provenance_ref": self.provenance_ref,
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
    surviving_justification_ids: tuple[str, ...]
    failed_justification_ids: tuple[str, ...]
    unsettled_justification_ids: tuple[str, ...]
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

    SCHEMA_VERSION = 2
    LEGACY_SCHEMA_VERSION = 1

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
        self._justifications: dict[str, AssumptionJustification] = {}
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

    def add_justification(
        self,
        justification: AssumptionJustification,
    ) -> AssumptionJustification:
        if justification.assumption_id not in self._claims:
            raise ValueError(
                "assumption justification references unknown target assumption "
                f"{justification.assumption_id}"
            )
        legacy_id = self._legacy_route_id(justification.assumption_id)
        if justification.justification_id == legacy_id:
            raise ValueError(
                f"justification identity {legacy_id} is reserved for legacy depends_on"
            )
        existing = self._justifications.get(justification.justification_id)
        if existing is not None and existing != justification:
            raise ValueError(
                f"justification identity {justification.justification_id} cannot be rebound to different content"
            )
        self._justifications[justification.justification_id] = justification
        return justification

    def justifications_for(self, assumption_id: str) -> tuple[AssumptionJustification, ...]:
        self.get(assumption_id)
        return tuple(
            sorted(
                (
                    item
                    for item in self._justifications.values()
                    if item.assumption_id == assumption_id
                ),
                key=lambda item: item.justification_id,
            )
        )

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
    def _legacy_route_id(assumption_id: str) -> str:
        return f"legacy-depends-on:{assumption_id}"

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

    def _explicit_justifications(
        self,
        assumption_id: str,
    ) -> tuple[AssumptionJustification, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._justifications.values()
                    if item.assumption_id == assumption_id
                ),
                key=lambda item: item.justification_id,
            )
        )

    def _premise_refs(self, claim: AssumptionClaim) -> tuple[str, ...]:
        return _normalized_refs(
            tuple(claim.depends_on)
            + tuple(
                premise
                for justification in self._explicit_justifications(claim.assumption_id)
                for premise in justification.premise_refs
            )
        )

    @staticmethod
    def _route_status(
        premise_assessments: tuple[AssumptionAssessment, ...],
    ) -> AssumptionStatus:
        if any(
            assessment.status is AssumptionStatus.REFUTED
            for assessment in premise_assessments
        ):
            return AssumptionStatus.REFUTED
        if any(
            assessment.status is AssumptionStatus.CONTESTED
            for assessment in premise_assessments
        ):
            return AssumptionStatus.CONTESTED
        if all(
            assessment.status is AssumptionStatus.SUPPORTED
            for assessment in premise_assessments
        ):
            return AssumptionStatus.SUPPORTED
        return AssumptionStatus.UNKNOWN

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
        explicit = self._explicit_justifications(assumption_id)

        # Compatibility path: preserve the exact historical assessment digest
        # and legacy conjunctive semantics when no explicit independent routes
        # have been introduced for this claim.
        if not explicit:
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

            legacy_id = self._legacy_route_id(assumption_id)
            surviving = (
                (legacy_id,)
                if claim.depends_on
                and dependency_assessments
                and all(
                    dep.status is AssumptionStatus.SUPPORTED
                    for dep in dependency_assessments
                )
                else ()
            )
            failed = (
                (legacy_id,)
                if claim.depends_on
                and any(
                    dep.status is AssumptionStatus.REFUTED
                    for dep in dependency_assessments
                )
                else ()
            )
            unsettled = (
                (legacy_id,)
                if claim.depends_on and not surviving and not failed
                else ()
            )
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
                surviving_justification_ids=surviving,
                failed_justification_ids=failed,
                unsettled_justification_ids=unsettled,
                evidence_state_digest=evidence_state_digest,
                digest=stable_digest({"assumption_assessment": payload}),
            )
            cache[assumption_id] = result
            return result

        route_specs: list[tuple[str, tuple[str, ...], str]] = []
        if claim.depends_on:
            legacy_id = self._legacy_route_id(assumption_id)
            route_specs.append(
                (
                    legacy_id,
                    claim.depends_on,
                    stable_digest(
                        {
                            "legacy_assumption_justification": {
                                "justification_id": legacy_id,
                                "assumption_id": assumption_id,
                                "premise_refs": claim.depends_on,
                                "claim_digest": claim.digest,
                            }
                        }
                    ),
                )
            )
        route_specs.extend(
            (
                justification.justification_id,
                justification.premise_refs,
                justification.digest,
            )
            for justification in explicit
        )
        route_specs.sort(key=lambda row: row[0])

        route_rows: list[dict[str, Any]] = []
        premise_by_id: dict[str, AssumptionAssessment] = {}
        route_status_by_id: dict[str, AssumptionStatus] = {}
        for route_id, premise_refs, route_digest in route_specs:
            premise_assessments = tuple(
                self._assessment(
                    premise,
                    stack=stack + (assumption_id,),
                    cache=cache,
                )
                for premise in premise_refs
            )
            for assessment in premise_assessments:
                premise_by_id[assessment.assumption_id] = assessment
            route_status = self._route_status(premise_assessments)
            route_status_by_id[route_id] = route_status
            route_rows.append(
                {
                    "justification_id": route_id,
                    "justification_digest": route_digest,
                    "premise_refs": premise_refs,
                    "premise_assessment_digests": tuple(
                        assessment.digest for assessment in premise_assessments
                    ),
                    "status": route_status.value,
                }
            )

        surviving = tuple(
            sorted(
                route_id
                for route_id, status in route_status_by_id.items()
                if status is AssumptionStatus.SUPPORTED
            )
        )
        failed = tuple(
            sorted(
                route_id
                for route_id, status in route_status_by_id.items()
                if status is AssumptionStatus.REFUTED
            )
        )
        unsettled = tuple(
            sorted(
                route_id
                for route_id, status in route_status_by_id.items()
                if status in (AssumptionStatus.UNKNOWN, AssumptionStatus.CONTESTED)
            )
        )

        if surviving:
            dependency_blockers: tuple[str, ...] = ()
        else:
            dependency_blockers = tuple(
                sorted(
                    {
                        premise.assumption_id
                        for route_id, premise_refs, _ in route_specs
                        for premise in (
                            self._assessment(
                                premise_ref,
                                stack=stack + (assumption_id,),
                                cache=cache,
                            )
                            for premise_ref in premise_refs
                        )
                        if premise.status is not AssumptionStatus.SUPPORTED
                    }
                )
            )

        route_statuses = tuple(route_status_by_id.values())
        all_routes_refuted = bool(route_statuses) and all(
            status is AssumptionStatus.REFUTED for status in route_statuses
        )
        any_route_contested = any(
            status is AssumptionStatus.CONTESTED for status in route_statuses
        )

        if direct_status is AssumptionStatus.REFUTED or all_routes_refuted:
            effective = AssumptionStatus.REFUTED
        elif direct_status is AssumptionStatus.CONTESTED:
            effective = AssumptionStatus.CONTESTED
        elif not surviving and any_route_contested:
            effective = AssumptionStatus.CONTESTED
        elif direct_status is AssumptionStatus.SUPPORTED and surviving:
            effective = AssumptionStatus.SUPPORTED
        else:
            effective = AssumptionStatus.UNKNOWN

        dependency_assessments = tuple(
            premise_by_id[key] for key in sorted(premise_by_id)
        )
        payload = {
            "schema_version": 2,
            "assumption_id": assumption_id,
            "claim_digest": claim.digest,
            "direct_status": direct_status.value,
            "status": effective.value,
            "support_score": support,
            "refute_score": refute,
            "dependency_blockers": dependency_blockers,
            "surviving_justification_ids": surviving,
            "failed_justification_ids": failed,
            "unsettled_justification_ids": unsettled,
            "justification_routes": tuple(route_rows),
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
            surviving_justification_ids=surviving,
            failed_justification_ids=failed,
            unsettled_justification_ids=unsettled,
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
            for dependency in self._premise_refs(claim):
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
                if affected.intersection(self._premise_refs(claim)):
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
        justifications = [
            {
                "justification_id": item.justification_id,
                "assumption_id": item.assumption_id,
                "premise_refs": list(item.premise_refs),
                "provenance_ref": item.provenance_ref,
                "digest": item.digest,
            }
            for item in (
                self._justifications[key] for key in sorted(self._justifications)
            )
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
            "justifications": justifications,
            "evidence": evidence,
            "retractions": retractions,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AssumptionTruthMaintenance":
        schema_version = int(state.get("schema_version", cls.LEGACY_SCHEMA_VERSION))
        if schema_version not in (cls.LEGACY_SCHEMA_VERSION, cls.SCHEMA_VERSION):
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

        for row in state.get("justifications", ()):
            justification = AssumptionJustification(
                justification_id=str(row["justification_id"]),
                assumption_id=str(row["assumption_id"]),
                premise_refs=tuple(str(x) for x in row.get("premise_refs", ())),
                provenance_ref=str(row["provenance_ref"]),
            )
            if str(row.get("digest", "")) != justification.digest:
                raise ValueError(
                    "assumption justification digest mismatch for "
                    f"{justification.justification_id}"
                )
            truth.add_justification(justification)

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
    "AssumptionJustification",
    "AssumptionPolarity",
    "AssumptionSnapshot",
    "AssumptionStatus",
    "AssumptionTruthMaintenance",
    "EvidenceRetraction",
]
