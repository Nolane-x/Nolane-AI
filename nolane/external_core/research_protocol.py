from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.research_budget import ResearchBudget
from nolane.external_core.research_trials import ResearchTrialLedger


class ResearchClosureDisposition(str, Enum):
    CLOSED = "closed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ResearchHypothesis:
    hypothesis_id: str
    statement: str
    predicted_observations: tuple[str, ...]
    digest: str

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "predicted_observations": list(self.predicted_observations),
        }

    def to_state(self) -> dict[str, Any]:
        return {"hypothesis_id": self.hypothesis_id, **self.semantic_payload(), "digest": self.digest}

    @classmethod
    def create(
        cls,
        *,
        statement: str,
        predicted_observations: tuple[str, ...],
    ) -> "ResearchHypothesis":
        observations = _unique_explicit(
            predicted_observations, "research hypothesis predicted observation"
        )
        if not observations:
            raise ValueError("research hypothesis requires predicted observations")
        payload = {
            "statement": _explicit(statement, "research hypothesis statement"),
            "predicted_observations": list(observations),
        }
        digest = canonical_digest(payload)
        return cls(
            hypothesis_id="research-hypothesis-" + digest[:24],
            statement=payload["statement"],
            predicted_observations=observations,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ResearchHypothesis":
        expected = cls.create(
            statement=str(state["statement"]),
            predicted_observations=tuple(
                str(x) for x in state.get("predicted_observations", ())
            ),
        )
        if str(state.get("hypothesis_id", "")) != expected.hypothesis_id:
            raise ValueError("research hypothesis identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("research hypothesis digest mismatch")
        return expected


@dataclass(frozen=True, slots=True)
class ResearchQuestionCertificate:
    question_id: str
    question: str
    decision_ref: str
    scope: str
    unknowns: tuple[str, ...]
    assumptions: tuple[str, ...]
    hypotheses: tuple[ResearchHypothesis, ...]
    rival_hypotheses: tuple[ResearchHypothesis, ...]
    falsifiers: tuple[str, ...]
    closure_criteria: tuple[str, ...]
    source_constraints: tuple[str, ...]
    budget_class: str
    high_stakes: bool
    digest: str

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "decision_ref": self.decision_ref,
            "scope": self.scope,
            "unknowns": list(self.unknowns),
            "assumptions": list(self.assumptions),
            "hypotheses": [row.to_state() for row in self.hypotheses],
            "rival_hypotheses": [row.to_state() for row in self.rival_hypotheses],
            "falsifiers": list(self.falsifiers),
            "closure_criteria": list(self.closure_criteria),
            "source_constraints": list(self.source_constraints),
            "budget_class": self.budget_class,
            "high_stakes": self.high_stakes,
        }

    def to_state(self) -> dict[str, Any]:
        return {"question_id": self.question_id, **self.semantic_payload(), "digest": self.digest}

    @classmethod
    def create(
        cls,
        *,
        question: str,
        decision_ref: str,
        scope: str,
        unknowns: tuple[str, ...],
        assumptions: tuple[str, ...],
        hypotheses: tuple[ResearchHypothesis, ...],
        rival_hypotheses: tuple[ResearchHypothesis, ...],
        falsifiers: tuple[str, ...],
        closure_criteria: tuple[str, ...],
        source_constraints: tuple[str, ...],
        budget_class: str,
        high_stakes: bool,
    ) -> "ResearchQuestionCertificate":
        if not isinstance(high_stakes, bool):
            raise TypeError("research question high_stakes must be bool")
        primary = _unique_hypotheses(hypotheses, "primary")
        rivals = _unique_hypotheses(rival_hypotheses, "rival")
        if not primary:
            raise ValueError("research question requires at least one hypothesis")
        primary_ids = {row.hypothesis_id for row in primary}
        rival_ids = {row.hypothesis_id for row in rivals}
        if primary_ids & rival_ids:
            raise ValueError("research rival hypotheses must be distinct from primary hypotheses")
        falsifier_rows = _unique_explicit(falsifiers, "research falsifier")
        if high_stakes and not rivals:
            raise ValueError("high-stakes research requires at least one rival hypothesis")
        if high_stakes and not falsifier_rows:
            raise ValueError("high-stakes research requires at least one falsifier")
        unknown_rows = _unique_explicit(unknowns, "research unknown")
        assumption_rows = _unique_explicit(assumptions, "research assumption")
        closure_rows = _unique_explicit(closure_criteria, "research closure criterion")
        source_rows = _unique_explicit(source_constraints, "research source constraint")
        if not closure_rows:
            raise ValueError("research question requires explicit closure criteria")
        if not source_rows:
            raise ValueError("research question requires source constraints")
        payload = {
            "question": _explicit(question, "research question"),
            "decision_ref": _explicit(decision_ref, "research decision ref"),
            "scope": _explicit(scope, "research scope"),
            "unknowns": list(unknown_rows),
            "assumptions": list(assumption_rows),
            "hypotheses": [row.to_state() for row in primary],
            "rival_hypotheses": [row.to_state() for row in rivals],
            "falsifiers": list(falsifier_rows),
            "closure_criteria": list(closure_rows),
            "source_constraints": list(source_rows),
            "budget_class": _explicit(budget_class, "research budget class"),
            "high_stakes": high_stakes,
        }
        digest = canonical_digest(payload)
        return cls(
            question_id="research-question-" + digest[:24],
            question=payload["question"],
            decision_ref=payload["decision_ref"],
            scope=payload["scope"],
            unknowns=unknown_rows,
            assumptions=assumption_rows,
            hypotheses=primary,
            rival_hypotheses=rivals,
            falsifiers=falsifier_rows,
            closure_criteria=closure_rows,
            source_constraints=source_rows,
            budget_class=payload["budget_class"],
            high_stakes=high_stakes,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ResearchQuestionCertificate":
        expected = cls.create(
            question=str(state["question"]),
            decision_ref=str(state["decision_ref"]),
            scope=str(state["scope"]),
            unknowns=tuple(str(x) for x in state.get("unknowns", ())),
            assumptions=tuple(str(x) for x in state.get("assumptions", ())),
            hypotheses=tuple(
                ResearchHypothesis.from_state(raw) for raw in state.get("hypotheses", ())
            ),
            rival_hypotheses=tuple(
                ResearchHypothesis.from_state(raw)
                for raw in state.get("rival_hypotheses", ())
            ),
            falsifiers=tuple(str(x) for x in state.get("falsifiers", ())),
            closure_criteria=tuple(str(x) for x in state.get("closure_criteria", ())),
            source_constraints=tuple(str(x) for x in state.get("source_constraints", ())),
            budget_class=str(state["budget_class"]),
            high_stakes=state["high_stakes"],
        )
        if str(state.get("question_id", "")) != expected.question_id:
            raise ValueError("research question identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("research question digest mismatch")
        return expected


@dataclass(frozen=True, slots=True)
class ResearchClosureCertificate:
    closure_id: str
    question_id: str
    question_digest: str
    budget_digest: str
    trial_ids: tuple[str, ...]
    independent_verification_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    disposition: ResearchClosureDisposition
    reasons: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question_digest": self.question_digest,
            "budget_digest": self.budget_digest,
            "trial_ids": list(self.trial_ids),
            "independent_verification_refs": list(self.independent_verification_refs),
            "evidence_refs": list(self.evidence_refs),
            "disposition": self.disposition.value,
            "reasons": list(self.reasons),
        }

    def to_state(self) -> dict[str, Any]:
        return {"closure_id": self.closure_id, **self.payload(), "digest": self.digest}



def assess_research_closure(
    *,
    question: ResearchQuestionCertificate,
    budget: ResearchBudget,
    trial_ledger: ResearchTrialLedger,
    required_trial_ids: tuple[str, ...],
    stale_source_ids: tuple[str, ...],
    unresolved_claim_keys: tuple[str, ...],
    independent_verification_refs: tuple[str, ...],
    evidence_refs: tuple[str, ...],
) -> ResearchClosureCertificate:
    """Assess whether the declared research work is closed.

    CLOSED means the research obligations represented here have been completed;
    it is deliberately not a Truth value, Assurance disposition, promotion, or
    execution authorization.
    """

    required = _unique_explicit(required_trial_ids, "required research trial id")
    stale = _unique_explicit(stale_source_ids, "stale research source id")
    unresolved = _unique_explicit(unresolved_claim_keys, "unresolved research claim key")
    independent = _unique_explicit(
        independent_verification_refs, "independent research verification ref"
    )
    evidence = _unique_explicit(evidence_refs, "research closure evidence ref")
    if not evidence:
        raise ValueError("research closure requires evidence refs")

    reasons: list[str] = []
    trial_rows = []
    for trial_id in required:
        try:
            trial = trial_ledger.get(trial_id)
        except KeyError:
            reasons.append("missing_required_trial")
            continue
        if trial.question_id != question.question_id:
            reasons.append("trial_question_mismatch")
        if trial.protocol_digest != question.digest:
            reasons.append("trial_protocol_mismatch")
        trial_rows.append(trial)

    if stale:
        reasons.append("stale_source")
    if unresolved:
        reasons.append("unresolved_claim")

    blocking_codes = {
        "stale_source",
        "unresolved_claim",
        "trial_question_mismatch",
        "trial_protocol_mismatch",
    }
    if any(reason in blocking_codes for reason in reasons):
        disposition = ResearchClosureDisposition.BLOCKED
    else:
        if "missing_required_trial" in reasons:
            disposition = ResearchClosureDisposition.UNKNOWN
        elif question.high_stakes and not independent:
            reasons.append("missing_independent_verification")
            disposition = ResearchClosureDisposition.UNKNOWN
        else:
            disposition = ResearchClosureDisposition.CLOSED

    normalized_reasons = tuple(dict.fromkeys(reasons))
    payload = {
        "question_id": question.question_id,
        "question_digest": question.digest,
        "budget_digest": budget.digest,
        "trial_ids": list(required),
        "independent_verification_refs": list(independent),
        "evidence_refs": list(evidence),
        "disposition": disposition.value,
        "reasons": list(normalized_reasons),
    }
    digest = canonical_digest(payload)
    return ResearchClosureCertificate(
        closure_id="research-closure-" + digest[:24],
        question_id=question.question_id,
        question_digest=question.digest,
        budget_digest=budget.digest,
        trial_ids=required,
        independent_verification_refs=independent,
        evidence_refs=evidence,
        disposition=disposition,
        reasons=normalized_reasons,
        digest=digest,
    )


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


def _unique_hypotheses(
    values: tuple[ResearchHypothesis, ...], label: str
) -> tuple[ResearchHypothesis, ...]:
    rows = tuple(values)
    if not all(isinstance(row, ResearchHypothesis) for row in rows):
        raise TypeError(f"research {label} hypotheses must be ResearchHypothesis objects")
    if len({row.hypothesis_id for row in rows}) != len(rows):
        raise ValueError(f"duplicate research {label} hypothesis")
    return tuple(sorted(rows, key=lambda row: row.hypothesis_id))


__all__ = (
    "ResearchClosureCertificate",
    "ResearchClosureDisposition",
    "ResearchHypothesis",
    "ResearchQuestionCertificate",
    "assess_research_closure",
)
