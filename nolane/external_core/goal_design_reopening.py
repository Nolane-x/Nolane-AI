"""Sensitivity-driven reopening authority for D. Goal / Design.

Truth maintenance answers what is currently supported. This module answers a
different authority question: whether a truth change is material enough to
reopen an already-admitted design decision. The separation is intentional:
reopening never becomes a second truth authority and never mutates historical
receipt identity.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .goal_design import DecisionClass, UncertaintyItem, stable_digest
from .goal_design_truth import (
    AssumptionAssessment,
    AssumptionStatus,
    AssumptionTruthMaintenance,
)

__version__ = "0.1.0"


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _evidence_refs(values: Iterable[str]) -> tuple[str, ...]:
    refs = _refs(values)
    if not refs:
        raise ValueError("reopening obligation satisfaction requires evidence")
    return refs


class ReopeningDisposition(str, Enum):
    NO_REOPEN = "no_reopen"
    REOPEN_REQUIRED = "reopen_required"


class ReopeningCaseStatus(str, Enum):
    OPEN = "open"
    READY_FOR_READMISSION = "ready_for_readmission"


class ReopeningObligationStatus(str, Enum):
    OPEN = "open"
    SATISFIED = "satisfied"


@dataclass(frozen=True)
class AssumptionReopeningBaseline:
    assumption_id: str
    status: AssumptionStatus
    support_score: float
    refute_score: float
    criticality: float
    assessment_digest: str
    digest: str

    @classmethod
    def capture(
        cls,
        truth: AssumptionTruthMaintenance,
        assumption_id: str,
    ) -> "AssumptionReopeningBaseline":
        claim = truth.get(assumption_id)
        assessment = truth.assessment(assumption_id)
        payload = {
            "assumption_id": assumption_id,
            "status": assessment.status.value,
            "support_score": float(assessment.support_score),
            "refute_score": float(assessment.refute_score),
            "criticality": float(claim.criticality),
            "assessment_digest": assessment.digest,
        }
        return cls(
            assumption_id=assumption_id,
            status=assessment.status,
            support_score=float(assessment.support_score),
            refute_score=float(assessment.refute_score),
            criticality=float(claim.criticality),
            assessment_digest=assessment.digest,
            digest=stable_digest({"goal_design_assumption_reopening_baseline": payload}),
        )


@dataclass(frozen=True)
class DecisionReopeningBaseline:
    receipt_id: str
    decision_class: DecisionClass
    assumption_ids: tuple[str, ...]
    assumption_state_digest: str
    assumption_baselines: tuple[AssumptionReopeningBaseline, ...]
    uncertainty_pressure: float
    uncertainty_ids: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class ReopeningObligation:
    obligation_id: str
    receipt_id: str
    assumption_id: str
    claim: str
    blocking: bool
    status: ReopeningObligationStatus
    evidence_refs: tuple[str, ...]
    baseline_assessment_digest: str
    current_assessment_digest: str
    digest: str


@dataclass(frozen=True)
class ReopeningCase:
    case_id: str
    receipt_id: str
    status: ReopeningCaseStatus
    material_assumption_ids: tuple[str, ...]
    sensitivity_score: float
    reopening_threshold: float
    obligation_ids: tuple[str, ...]
    baseline_truth_digest: str
    current_truth_digest: str
    requires_new_receipt: bool
    digest: str


@dataclass(frozen=True)
class ReopeningAssessment:
    receipt_id: str
    disposition: ReopeningDisposition
    material_assumption_ids: tuple[str, ...]
    monitored_assumption_ids: tuple[str, ...]
    sensitivity_score: float
    reopening_threshold: float
    obligations: tuple[ReopeningObligation, ...]
    current_truth_digest: str
    digest: str


class DecisionReopeningAuthority:
    """Deterministic authority over sensitivity-driven decision reopening."""

    SCHEMA_VERSION = 1
    _THRESHOLDS = {
        DecisionClass.REVERSIBLE: 0.40,
        DecisionClass.COSTLY_REVERSIBLE: 0.28,
        DecisionClass.IRREVERSIBLE: 0.16,
    }

    def __init__(self) -> None:
        self._baselines: dict[str, DecisionReopeningBaseline] = {}
        self._cases: dict[str, ReopeningCase] = {}
        self._obligations: dict[str, ReopeningObligation] = {}

    @staticmethod
    def _uncertainty_pressure(items: Sequence[UncertaintyItem]) -> float:
        unresolved = [float(item.risk_score) for item in items if not item.resolved]
        return max(unresolved, default=0.0)

    @classmethod
    def _threshold(cls, decision_class: DecisionClass) -> float:
        return cls._THRESHOLDS[decision_class]

    @staticmethod
    def _status_transition_weight(
        baseline: AssumptionStatus,
        current: AssumptionStatus,
    ) -> float:
        if current is baseline:
            return 0.0
        if current is AssumptionStatus.REFUTED:
            return 1.0
        if current is AssumptionStatus.CONTESTED:
            return 1.0
        if current is AssumptionStatus.UNKNOWN:
            return 0.60
        # Moving toward SUPPORTED does not itself create negative decision risk.
        return 0.10

    @classmethod
    def _assumption_sensitivity(
        cls,
        baseline: AssumptionReopeningBaseline,
        current: AssumptionAssessment,
        *,
        uncertainty_pressure: float,
    ) -> float:
        score_delta = max(
            abs(float(current.support_score) - float(baseline.support_score)),
            abs(float(current.refute_score) - float(baseline.refute_score)),
        )
        transition = cls._status_transition_weight(baseline.status, current.status)
        raw = max(score_delta, transition)
        amplified = float(baseline.criticality) * raw * (1.0 + 0.5 * uncertainty_pressure)
        return min(1.0, amplified)

    @staticmethod
    def _baseline_payload(
        *,
        receipt_id: str,
        decision_class: DecisionClass,
        assumption_ids: tuple[str, ...],
        assumption_state_digest: str,
        assumption_baselines: tuple[AssumptionReopeningBaseline, ...],
        uncertainty_pressure: float,
        uncertainty_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        return {
            "receipt_id": receipt_id,
            "decision_class": decision_class.value,
            "assumption_ids": list(assumption_ids),
            "assumption_state_digest": assumption_state_digest,
            "assumption_baseline_digests": [item.digest for item in assumption_baselines],
            "uncertainty_pressure": float(uncertainty_pressure),
            "uncertainty_ids": list(uncertainty_ids),
        }

    def register_decision(
        self,
        *,
        receipt_id: str,
        decision_class: DecisionClass,
        truth: AssumptionTruthMaintenance,
        assumption_ids: Iterable[str],
        uncertainties: Sequence[UncertaintyItem] = (),
    ) -> DecisionReopeningBaseline:
        receipt_id = str(receipt_id).strip()
        assumptions = _refs(assumption_ids)
        if not receipt_id or not assumptions:
            raise ValueError("reopening baseline requires receipt_id and bound assumptions")
        snapshot = truth.snapshot(assumptions)
        baselines = tuple(
            AssumptionReopeningBaseline.capture(truth, assumption_id)
            for assumption_id in assumptions
        )
        uncertainty_ids = _refs(item.uncertainty_id for item in uncertainties)
        pressure = self._uncertainty_pressure(tuple(uncertainties))
        payload = self._baseline_payload(
            receipt_id=receipt_id,
            decision_class=decision_class,
            assumption_ids=assumptions,
            assumption_state_digest=snapshot.digest,
            assumption_baselines=baselines,
            uncertainty_pressure=pressure,
            uncertainty_ids=uncertainty_ids,
        )
        baseline = DecisionReopeningBaseline(
            receipt_id=receipt_id,
            decision_class=decision_class,
            assumption_ids=assumptions,
            assumption_state_digest=snapshot.digest,
            assumption_baselines=baselines,
            uncertainty_pressure=pressure,
            uncertainty_ids=uncertainty_ids,
            digest=stable_digest({"goal_design_decision_reopening_baseline": payload}),
        )
        existing = self._baselines.get(receipt_id)
        if existing is not None:
            if existing != baseline:
                raise ValueError(
                    f"reopening baseline identity {receipt_id} cannot be rebound to different authority content"
                )
            return existing
        self._baselines[receipt_id] = baseline
        return baseline

    def has_baseline(self, receipt_id: str) -> bool:
        return str(receipt_id) in self._baselines

    def baseline(self, receipt_id: str) -> DecisionReopeningBaseline:
        try:
            return self._baselines[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown Goal/Design reopening baseline: {receipt_id}") from exc

    def open_case(self, receipt_id: str) -> ReopeningCase | None:
        return self._cases.get(str(receipt_id))

    def ready_for_readmission(self, receipt_id: str) -> bool:
        case = self.open_case(receipt_id)
        return case is not None and case.status is ReopeningCaseStatus.READY_FOR_READMISSION

    @staticmethod
    def _obligation_payload(
        *,
        obligation_id: str,
        receipt_id: str,
        assumption_id: str,
        claim: str,
        blocking: bool,
        status: ReopeningObligationStatus,
        evidence_refs: tuple[str, ...],
        baseline_assessment_digest: str,
        current_assessment_digest: str,
    ) -> dict[str, Any]:
        return {
            "obligation_id": obligation_id,
            "receipt_id": receipt_id,
            "assumption_id": assumption_id,
            "claim": claim,
            "blocking": bool(blocking),
            "status": status.value,
            "evidence_refs": list(evidence_refs),
            "baseline_assessment_digest": baseline_assessment_digest,
            "current_assessment_digest": current_assessment_digest,
        }

    @classmethod
    def _make_obligation(
        cls,
        *,
        receipt_id: str,
        baseline: AssumptionReopeningBaseline,
        current: AssumptionAssessment,
    ) -> ReopeningObligation:
        identity = {
            "receipt_id": receipt_id,
            "assumption_id": baseline.assumption_id,
            "baseline_assessment_digest": baseline.assessment_digest,
            "current_assessment_digest": current.digest,
        }
        obligation_id = stable_digest({"goal_design_reopening_obligation_identity": identity})
        claim = (
            "Re-establish decision robustness for assumption "
            f"{baseline.assumption_id} after material truth change"
        )
        payload = cls._obligation_payload(
            obligation_id=obligation_id,
            receipt_id=receipt_id,
            assumption_id=baseline.assumption_id,
            claim=claim,
            blocking=True,
            status=ReopeningObligationStatus.OPEN,
            evidence_refs=(),
            baseline_assessment_digest=baseline.assessment_digest,
            current_assessment_digest=current.digest,
        )
        return ReopeningObligation(
            obligation_id=obligation_id,
            receipt_id=receipt_id,
            assumption_id=baseline.assumption_id,
            claim=claim,
            blocking=True,
            status=ReopeningObligationStatus.OPEN,
            evidence_refs=(),
            baseline_assessment_digest=baseline.assessment_digest,
            current_assessment_digest=current.digest,
            digest=stable_digest({"goal_design_reopening_obligation": payload}),
        )

    @staticmethod
    def _case_payload(
        *,
        case_id: str,
        receipt_id: str,
        status: ReopeningCaseStatus,
        material_assumption_ids: tuple[str, ...],
        sensitivity_score: float,
        reopening_threshold: float,
        obligation_ids: tuple[str, ...],
        baseline_truth_digest: str,
        current_truth_digest: str,
        requires_new_receipt: bool,
    ) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "receipt_id": receipt_id,
            "status": status.value,
            "material_assumption_ids": list(material_assumption_ids),
            "sensitivity_score": float(sensitivity_score),
            "reopening_threshold": float(reopening_threshold),
            "obligation_ids": list(obligation_ids),
            "baseline_truth_digest": baseline_truth_digest,
            "current_truth_digest": current_truth_digest,
            "requires_new_receipt": bool(requires_new_receipt),
        }

    @classmethod
    def _case_with_status(
        cls,
        case: ReopeningCase,
        status: ReopeningCaseStatus,
    ) -> ReopeningCase:
        payload = cls._case_payload(
            case_id=case.case_id,
            receipt_id=case.receipt_id,
            status=status,
            material_assumption_ids=case.material_assumption_ids,
            sensitivity_score=case.sensitivity_score,
            reopening_threshold=case.reopening_threshold,
            obligation_ids=case.obligation_ids,
            baseline_truth_digest=case.baseline_truth_digest,
            current_truth_digest=case.current_truth_digest,
            requires_new_receipt=case.requires_new_receipt,
        )
        return replace(
            case,
            status=status,
            digest=stable_digest({"goal_design_reopening_case": payload}),
        )

    def assess_change(
        self,
        *,
        receipt_id: str,
        truth: AssumptionTruthMaintenance,
        affected_assumption_ids: Iterable[str],
    ) -> ReopeningAssessment:
        baseline = self.baseline(receipt_id)
        affected = set(_refs(affected_assumption_ids))
        relevant = tuple(sorted(affected.intersection(baseline.assumption_ids)))
        threshold = self._threshold(baseline.decision_class)
        baseline_by_id = {
            item.assumption_id: item for item in baseline.assumption_baselines
        }
        current_by_id = {
            assumption_id: truth.assessment(assumption_id)
            for assumption_id in relevant
        }
        scores = {
            assumption_id: self._assumption_sensitivity(
                baseline_by_id[assumption_id],
                current_by_id[assumption_id],
                uncertainty_pressure=baseline.uncertainty_pressure,
            )
            for assumption_id in relevant
        }
        material = tuple(
            sorted(
                assumption_id
                for assumption_id in relevant
                if current_by_id[assumption_id].status is AssumptionStatus.REFUTED
                or scores[assumption_id] >= threshold
            )
        )
        monitored = tuple(sorted(set(relevant) - set(material)))
        sensitivity_score = max(scores.values(), default=0.0)
        current_truth_digest = truth.snapshot(baseline.assumption_ids).digest

        obligations: tuple[ReopeningObligation, ...] = ()
        disposition = ReopeningDisposition.NO_REOPEN
        if material:
            disposition = ReopeningDisposition.REOPEN_REQUIRED
            obligation_rows: list[ReopeningObligation] = []
            for assumption_id in material:
                proposed = self._make_obligation(
                    receipt_id=baseline.receipt_id,
                    baseline=baseline_by_id[assumption_id],
                    current=current_by_id[assumption_id],
                )
                existing = self._obligations.get(proposed.obligation_id)
                if existing is None:
                    self._obligations[proposed.obligation_id] = proposed
                    existing = proposed
                obligation_rows.append(existing)
            obligations = tuple(sorted(obligation_rows, key=lambda item: item.obligation_id))
            obligation_ids = tuple(item.obligation_id for item in obligations)
            identity = {
                "receipt_id": baseline.receipt_id,
                "baseline_digest": baseline.digest,
                "current_truth_digest": current_truth_digest,
                "material_assumption_ids": list(material),
                "obligation_ids": list(obligation_ids),
            }
            case_id = stable_digest({"goal_design_reopening_case_identity": identity})
            requires_new_receipt = current_truth_digest != baseline.assumption_state_digest
            existing_case = self._cases.get(baseline.receipt_id)
            if existing_case is not None and existing_case.case_id == case_id:
                case = existing_case
            else:
                case_payload = self._case_payload(
                    case_id=case_id,
                    receipt_id=baseline.receipt_id,
                    status=ReopeningCaseStatus.OPEN,
                    material_assumption_ids=material,
                    sensitivity_score=sensitivity_score,
                    reopening_threshold=threshold,
                    obligation_ids=obligation_ids,
                    baseline_truth_digest=baseline.assumption_state_digest,
                    current_truth_digest=current_truth_digest,
                    requires_new_receipt=requires_new_receipt,
                )
                case = ReopeningCase(
                    case_id=case_id,
                    receipt_id=baseline.receipt_id,
                    status=ReopeningCaseStatus.OPEN,
                    material_assumption_ids=material,
                    sensitivity_score=sensitivity_score,
                    reopening_threshold=threshold,
                    obligation_ids=obligation_ids,
                    baseline_truth_digest=baseline.assumption_state_digest,
                    current_truth_digest=current_truth_digest,
                    requires_new_receipt=requires_new_receipt,
                    digest=stable_digest({"goal_design_reopening_case": case_payload}),
                )
            if all(
                self._obligations[obligation_id].status is ReopeningObligationStatus.SATISFIED
                for obligation_id in case.obligation_ids
            ):
                case = self._case_with_status(case, ReopeningCaseStatus.READY_FOR_READMISSION)
            self._cases[baseline.receipt_id] = case

        assessment_payload = {
            "receipt_id": baseline.receipt_id,
            "baseline_digest": baseline.digest,
            "disposition": disposition.value,
            "material_assumption_ids": list(material),
            "monitored_assumption_ids": list(monitored),
            "sensitivity_score": sensitivity_score,
            "reopening_threshold": threshold,
            "obligation_digests": [item.digest for item in obligations],
            "current_truth_digest": current_truth_digest,
        }
        return ReopeningAssessment(
            receipt_id=baseline.receipt_id,
            disposition=disposition,
            material_assumption_ids=material,
            monitored_assumption_ids=monitored,
            sensitivity_score=sensitivity_score,
            reopening_threshold=threshold,
            obligations=obligations,
            current_truth_digest=current_truth_digest,
            digest=stable_digest({"goal_design_reopening_assessment": assessment_payload}),
        )

    def satisfy_obligation(
        self,
        obligation_id: str,
        *,
        evidence_refs: Iterable[str],
    ) -> ReopeningObligation:
        obligation_id = str(obligation_id).strip()
        try:
            current = self._obligations[obligation_id]
        except KeyError as exc:
            raise KeyError(f"unknown Goal/Design reopening obligation: {obligation_id}") from exc
        refs = _evidence_refs(evidence_refs)
        if current.status is ReopeningObligationStatus.SATISFIED:
            if current.evidence_refs != refs:
                raise ValueError("satisfied reopening obligation evidence cannot be rebound")
            return current
        payload = self._obligation_payload(
            obligation_id=current.obligation_id,
            receipt_id=current.receipt_id,
            assumption_id=current.assumption_id,
            claim=current.claim,
            blocking=current.blocking,
            status=ReopeningObligationStatus.SATISFIED,
            evidence_refs=refs,
            baseline_assessment_digest=current.baseline_assessment_digest,
            current_assessment_digest=current.current_assessment_digest,
        )
        updated = replace(
            current,
            status=ReopeningObligationStatus.SATISFIED,
            evidence_refs=refs,
            digest=stable_digest({"goal_design_reopening_obligation": payload}),
        )
        self._obligations[obligation_id] = updated

        case = self._cases.get(current.receipt_id)
        if case is not None and obligation_id in case.obligation_ids:
            if all(
                self._obligations[item_id].status is ReopeningObligationStatus.SATISFIED
                for item_id in case.obligation_ids
            ):
                self._cases[current.receipt_id] = self._case_with_status(
                    case,
                    ReopeningCaseStatus.READY_FOR_READMISSION,
                )
        return updated

    @staticmethod
    def _baseline_to_state(baseline: DecisionReopeningBaseline) -> dict[str, Any]:
        return {
            "receipt_id": baseline.receipt_id,
            "decision_class": baseline.decision_class.value,
            "assumption_ids": list(baseline.assumption_ids),
            "assumption_state_digest": baseline.assumption_state_digest,
            "assumption_baselines": [
                {
                    "assumption_id": item.assumption_id,
                    "status": item.status.value,
                    "support_score": item.support_score,
                    "refute_score": item.refute_score,
                    "criticality": item.criticality,
                    "assessment_digest": item.assessment_digest,
                    "digest": item.digest,
                }
                for item in baseline.assumption_baselines
            ],
            "uncertainty_pressure": baseline.uncertainty_pressure,
            "uncertainty_ids": list(baseline.uncertainty_ids),
            "digest": baseline.digest,
        }

    @staticmethod
    def _obligation_to_state(item: ReopeningObligation) -> dict[str, Any]:
        return {
            "obligation_id": item.obligation_id,
            "receipt_id": item.receipt_id,
            "assumption_id": item.assumption_id,
            "claim": item.claim,
            "blocking": item.blocking,
            "status": item.status.value,
            "evidence_refs": list(item.evidence_refs),
            "baseline_assessment_digest": item.baseline_assessment_digest,
            "current_assessment_digest": item.current_assessment_digest,
            "digest": item.digest,
        }

    @staticmethod
    def _case_to_state(case: ReopeningCase) -> dict[str, Any]:
        return {
            "case_id": case.case_id,
            "receipt_id": case.receipt_id,
            "status": case.status.value,
            "material_assumption_ids": list(case.material_assumption_ids),
            "sensitivity_score": case.sensitivity_score,
            "reopening_threshold": case.reopening_threshold,
            "obligation_ids": list(case.obligation_ids),
            "baseline_truth_digest": case.baseline_truth_digest,
            "current_truth_digest": case.current_truth_digest,
            "requires_new_receipt": case.requires_new_receipt,
            "digest": case.digest,
        }

    def to_state(self) -> dict[str, Any]:
        body = {
            "schema_version": self.SCHEMA_VERSION,
            "baselines": [
                self._baseline_to_state(self._baselines[key])
                for key in sorted(self._baselines)
            ],
            "obligations": [
                self._obligation_to_state(self._obligations[key])
                for key in sorted(self._obligations)
            ],
            "cases": [
                self._case_to_state(self._cases[key])
                for key in sorted(self._cases)
            ],
        }
        return {
            **body,
            "state_digest": stable_digest({"goal_design_reopening_state": body}),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "DecisionReopeningAuthority":
        if int(state.get("schema_version", 0)) != cls.SCHEMA_VERSION:
            raise ValueError("unsupported Goal/Design reopening schema version")
        body = {
            "schema_version": cls.SCHEMA_VERSION,
            "baselines": list(state.get("baselines", ())),
            "obligations": list(state.get("obligations", ())),
            "cases": list(state.get("cases", ())),
        }
        expected_state_digest = stable_digest({"goal_design_reopening_state": body})
        if str(state.get("state_digest", "")) != expected_state_digest:
            raise ValueError("Goal/Design reopening state digest mismatch; state may be tampered")

        authority = cls()
        for row in body["baselines"]:
            assumption_baselines: list[AssumptionReopeningBaseline] = []
            for item in row.get("assumption_baselines", ()):
                payload = {
                    "assumption_id": str(item["assumption_id"]),
                    "status": str(item["status"]),
                    "support_score": float(item["support_score"]),
                    "refute_score": float(item["refute_score"]),
                    "criticality": float(item["criticality"]),
                    "assessment_digest": str(item["assessment_digest"]),
                }
                expected = stable_digest({"goal_design_assumption_reopening_baseline": payload})
                if str(item.get("digest", "")) != expected:
                    raise ValueError("Goal/Design reopening assumption baseline digest mismatch")
                assumption_baselines.append(
                    AssumptionReopeningBaseline(
                        assumption_id=payload["assumption_id"],
                        status=AssumptionStatus(payload["status"]),
                        support_score=payload["support_score"],
                        refute_score=payload["refute_score"],
                        criticality=payload["criticality"],
                        assessment_digest=payload["assessment_digest"],
                        digest=expected,
                    )
                )
            decision_class = DecisionClass(str(row["decision_class"]))
            assumption_ids = _refs(row.get("assumption_ids", ()))
            uncertainty_ids = _refs(row.get("uncertainty_ids", ()))
            baseline_payload = cls._baseline_payload(
                receipt_id=str(row["receipt_id"]),
                decision_class=decision_class,
                assumption_ids=assumption_ids,
                assumption_state_digest=str(row["assumption_state_digest"]),
                assumption_baselines=tuple(assumption_baselines),
                uncertainty_pressure=float(row.get("uncertainty_pressure", 0.0)),
                uncertainty_ids=uncertainty_ids,
            )
            expected = stable_digest({"goal_design_decision_reopening_baseline": baseline_payload})
            if str(row.get("digest", "")) != expected:
                raise ValueError("Goal/Design reopening baseline digest mismatch")
            receipt_id = baseline_payload["receipt_id"]
            if receipt_id in authority._baselines:
                raise ValueError("duplicate Goal/Design reopening baseline identity")
            authority._baselines[receipt_id] = DecisionReopeningBaseline(
                receipt_id=receipt_id,
                decision_class=decision_class,
                assumption_ids=assumption_ids,
                assumption_state_digest=baseline_payload["assumption_state_digest"],
                assumption_baselines=tuple(assumption_baselines),
                uncertainty_pressure=baseline_payload["uncertainty_pressure"],
                uncertainty_ids=uncertainty_ids,
                digest=expected,
            )

        for row in body["obligations"]:
            obligation_id = str(row["obligation_id"])
            payload = cls._obligation_payload(
                obligation_id=obligation_id,
                receipt_id=str(row["receipt_id"]),
                assumption_id=str(row["assumption_id"]),
                claim=str(row["claim"]),
                blocking=bool(row["blocking"]),
                status=ReopeningObligationStatus(str(row["status"])),
                evidence_refs=_refs(row.get("evidence_refs", ())),
                baseline_assessment_digest=str(row["baseline_assessment_digest"]),
                current_assessment_digest=str(row["current_assessment_digest"]),
            )
            expected = stable_digest({"goal_design_reopening_obligation": payload})
            if str(row.get("digest", "")) != expected:
                raise ValueError("Goal/Design reopening obligation digest mismatch")
            if obligation_id in authority._obligations:
                raise ValueError("duplicate Goal/Design reopening obligation identity")
            authority._obligations[obligation_id] = ReopeningObligation(
                obligation_id=obligation_id,
                receipt_id=payload["receipt_id"],
                assumption_id=payload["assumption_id"],
                claim=payload["claim"],
                blocking=payload["blocking"],
                status=ReopeningObligationStatus(payload["status"]),
                evidence_refs=tuple(payload["evidence_refs"]),
                baseline_assessment_digest=payload["baseline_assessment_digest"],
                current_assessment_digest=payload["current_assessment_digest"],
                digest=expected,
            )

        for row in body["cases"]:
            case_id = str(row["case_id"])
            receipt_id = str(row["receipt_id"])
            status = ReopeningCaseStatus(str(row["status"]))
            material = _refs(row.get("material_assumption_ids", ()))
            obligation_ids = _refs(row.get("obligation_ids", ()))
            missing = [item for item in obligation_ids if item not in authority._obligations]
            if missing:
                raise ValueError("Goal/Design reopening case references unknown obligation identity")
            payload = cls._case_payload(
                case_id=case_id,
                receipt_id=receipt_id,
                status=status,
                material_assumption_ids=material,
                sensitivity_score=float(row["sensitivity_score"]),
                reopening_threshold=float(row["reopening_threshold"]),
                obligation_ids=obligation_ids,
                baseline_truth_digest=str(row["baseline_truth_digest"]),
                current_truth_digest=str(row["current_truth_digest"]),
                requires_new_receipt=bool(row["requires_new_receipt"]),
            )
            expected = stable_digest({"goal_design_reopening_case": payload})
            if str(row.get("digest", "")) != expected:
                raise ValueError("Goal/Design reopening case digest mismatch")
            if receipt_id in authority._cases:
                raise ValueError("duplicate Goal/Design reopening case identity")
            authority._cases[receipt_id] = ReopeningCase(
                case_id=case_id,
                receipt_id=receipt_id,
                status=status,
                material_assumption_ids=material,
                sensitivity_score=payload["sensitivity_score"],
                reopening_threshold=payload["reopening_threshold"],
                obligation_ids=obligation_ids,
                baseline_truth_digest=payload["baseline_truth_digest"],
                current_truth_digest=payload["current_truth_digest"],
                requires_new_receipt=payload["requires_new_receipt"],
                digest=expected,
            )
        return authority


__all__ = [
    "AssumptionReopeningBaseline",
    "DecisionReopeningAuthority",
    "DecisionReopeningBaseline",
    "ReopeningAssessment",
    "ReopeningCase",
    "ReopeningCaseStatus",
    "ReopeningDisposition",
    "ReopeningObligation",
    "ReopeningObligationStatus",
]
