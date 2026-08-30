"""Goal / Design coherence authority for the Nolane external core.

This module binds the five Goal/Design authorities (requirements, planning,
architecture, integration and context) without collapsing them into a single
mutable god-object. It is dependency-light and content-addressed so specialist
planes can evolve independently while decisions remain reproducible, auditable
and fail-closed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Iterable, Mapping, Sequence

__version__ = "0.2.0"


class CoherenceError(RuntimeError):
    """Raised when a decision cannot cross the Goal/Design authority gate."""


class DecisionClass(str, Enum):
    REVERSIBLE = "reversible"
    COSTLY_REVERSIBLE = "costly_reversible"
    IRREVERSIBLE = "irreversible"


class ObjectiveDirection(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class ProofStatus(str, Enum):
    OPEN = "open"
    SATISFIED = "satisfied"
    WAIVED = "waived"


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


def _canonical(value):
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list, set, frozenset)):
        seq = [_canonical(v) for v in value]
        if isinstance(value, (set, frozenset)):
            seq.sort(key=lambda v: json.dumps(v, sort_keys=True, separators=(",", ":")))
        return seq
    if isinstance(value, Enum):
        return value.value
    return value


def stable_digest(value) -> str:
    raw = json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _bounded(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return value


@dataclass(frozen=True)
class GoalObjective:
    objective_id: str
    direction: ObjectiveDirection = ObjectiveDirection.MAXIMIZE
    weight: float = 1.0
    description: str = ""

    def __post_init__(self):
        if not self.objective_id:
            raise ValueError("objective_id is required")
        if not math.isfinite(self.weight) or self.weight < 0:
            raise ValueError("objective weight must be finite and non-negative")


@dataclass(frozen=True)
class GoalSpec:
    goal_id: str
    statement: str
    objectives: tuple[GoalObjective, ...] = ()
    non_goals: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    success_metrics: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.goal_id or not self.statement.strip():
            raise ValueError("goal_id and statement are required")
        ids = [objective.objective_id for objective in self.objectives]
        if len(ids) != len(set(ids)):
            raise ValueError("goal objectives must have unique ids")


@dataclass(frozen=True)
class UncertaintyItem:
    uncertainty_id: str
    statement: str
    uncertainty: float
    impact: float
    decision_sensitivity: float
    observability: float = 0.5
    evidence_refs: tuple[str, ...] = ()
    resolved: bool = False
    mitigation_ref: str | None = None

    def __post_init__(self):
        if not self.uncertainty_id or not self.statement.strip():
            raise ValueError("uncertainty_id and statement are required")
        _bounded("uncertainty", self.uncertainty)
        _bounded("impact", self.impact)
        _bounded("decision_sensitivity", self.decision_sensitivity)
        _bounded("observability", self.observability)

    @property
    def risk_score(self) -> float:
        if self.resolved:
            return 0.0
        return self.uncertainty * self.impact * self.decision_sensitivity * (1.15 - 0.15 * self.observability)


@dataclass(frozen=True)
class DesignScenario:
    scenario_id: str
    probability: float = 1.0
    tags: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.scenario_id:
            raise ValueError("scenario_id is required")
        if not math.isfinite(self.probability) or self.probability < 0:
            raise ValueError("scenario probability must be finite and non-negative")


@dataclass(frozen=True)
class DesignOption:
    option_id: str
    label: str
    utilities: Mapping[str, float]
    objective_values: Mapping[str, float]
    decision_class: DecisionClass = DecisionClass.REVERSIBLE
    rollback_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    requirement_refs: tuple[str, ...] = ()
    component_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.option_id or not self.label.strip():
            raise ValueError("option_id and label are required")
        for key, value in self.utilities.items():
            _bounded(f"utility[{key}]", value)
        for key, value in self.objective_values.items():
            if not math.isfinite(float(value)):
                raise ValueError(f"objective value {key} must be finite")


@dataclass(frozen=True)
class ProofObligation:
    proof_id: str
    claim: str
    status: ProofStatus = ProofStatus.OPEN
    evidence_refs: tuple[str, ...] = ()
    waiver_reason: str | None = None
    blocking: bool = True

    def __post_init__(self):
        if not self.proof_id or not self.claim.strip():
            raise ValueError("proof_id and claim are required")
        if self.status is ProofStatus.WAIVED and not (self.waiver_reason or "").strip():
            raise ValueError("waived proof obligations require a waiver_reason")


@dataclass(frozen=True)
class PlaneState:
    revision: str
    digest: str | None = None

    @property
    def token(self) -> str:
        return f"{self.revision}@{self.digest}" if self.digest else self.revision


@dataclass(frozen=True)
class GoalDesignVersionVector:
    requirements: str | PlaneState
    planning: str | PlaneState
    architecture: str | PlaneState
    integration: str | PlaneState
    context: str | PlaneState

    def tokens(self) -> Mapping[str, str]:
        def token(value):
            return value.token if isinstance(value, PlaneState) else str(value)

        return {
            "requirements": token(self.requirements),
            "planning": token(self.planning),
            "architecture": token(self.architecture),
            "integration": token(self.integration),
            "context": token(self.context),
        }


@dataclass(frozen=True)
class GoalDesignSnapshot:
    version_vector: GoalDesignVersionVector
    digest: str


@dataclass(frozen=True)
class TraceabilityState:
    active_requirement_ids: tuple[str, ...] = ()
    planned_requirement_ids: tuple[str, ...] = ()
    planned_component_ids: tuple[str, ...] = ()
    architecture_component_ids: tuple[str, ...] = ()
    integration_component_refs: tuple[str, ...] = ()
    context_component_refs: tuple[str, ...] = ()
    context_snapshot_digest: str | None = None
    expected_snapshot_digest: str | None = None


@dataclass(frozen=True)
class CoherenceIssue:
    code: str
    message: str
    severity: IssueSeverity
    subject: str = ""

    @property
    def blocking(self) -> bool:
        return self.severity is IssueSeverity.BLOCKER


@dataclass(frozen=True)
class CoherenceReport:
    issues: tuple[CoherenceIssue, ...] = ()

    @property
    def coherent(self) -> bool:
        return not any(issue.blocking for issue in self.issues)


@dataclass(frozen=True)
class OptionEvaluation:
    option_id: str
    expected_utility: float
    worst_case_utility: float
    lower_tail_utility: float
    max_regret: float
    optionality: float
    robust_score: float


@dataclass(frozen=True)
class DesignEvaluation:
    options: tuple[OptionEvaluation, ...]
    pareto_option_ids: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class DecisionReceipt:
    receipt_id: str
    goal_id: str
    selected_option_id: str
    snapshot_digest: str
    version_vector: Mapping[str, str]
    evaluation_digest: str
    proof_obligation_ids: tuple[str, ...]
    uncertainty_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    goal_digest: str = ""
    scenario_set_digest: str = ""
    option_set_digest: str = ""
    proof_state_digest: str = ""
    uncertainty_state_digest: str = ""
    traceability_digest: str = ""
    input_manifest_digest: str = ""


class GoalDesignCoherencePlane:
    """Cross-plane design authority with fail-closed admission semantics."""

    def __init__(self, *, irreversible_uncertainty_threshold: float = 0.55):
        if irreversible_uncertainty_threshold < 0:
            raise ValueError("irreversible_uncertainty_threshold must be non-negative")
        self.irreversible_uncertainty_threshold = float(irreversible_uncertainty_threshold)

    def uncertainty_frontier(self, items: Iterable[UncertaintyItem]) -> tuple[UncertaintyItem, ...]:
        return tuple(sorted(items, key=lambda item: (-item.risk_score, item.uncertainty_id)))

    def pareto_frontier(self, goal: GoalSpec, options: Sequence[DesignOption]) -> tuple[DesignOption, ...]:
        if not options:
            return ()
        objectives = {objective.objective_id: objective for objective in goal.objectives}
        if not objectives:
            return tuple(options)
        for option in options:
            missing = set(objectives) - set(option.objective_values)
            if missing:
                raise ValueError(f"option {option.option_id} missing objective values: {sorted(missing)}")

        def dominates(a: DesignOption, b: DesignOption) -> bool:
            weakly_better = True
            strictly_better = False
            for objective_id, objective in objectives.items():
                av = float(a.objective_values[objective_id])
                bv = float(b.objective_values[objective_id])
                if objective.direction is ObjectiveDirection.MAXIMIZE:
                    if av < bv:
                        weakly_better = False
                    if av > bv:
                        strictly_better = True
                else:
                    if av > bv:
                        weakly_better = False
                    if av < bv:
                        strictly_better = True
            return weakly_better and strictly_better

        return tuple(
            option
            for option in options
            if not any(
                other.option_id != option.option_id and dominates(other, option)
                for other in options
            )
        )

    def evaluate_options(
        self,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
    ) -> DesignEvaluation:
        if not scenarios:
            raise ValueError("at least one design scenario is required")
        if not options:
            raise ValueError("at least one design option is required")
        scenario_ids = [scenario.scenario_id for scenario in scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("scenario ids must be unique")
        option_ids = [option.option_id for option in options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("option ids must be unique")
        total_probability = sum(s.probability for s in scenarios)
        if total_probability <= 0:
            raise ValueError("scenario probabilities must have positive mass")
        probabilities = {s.scenario_id: s.probability / total_probability for s in scenarios}
        for option in options:
            missing = set(scenario_ids) - set(option.utilities)
            if missing:
                raise ValueError(f"option {option.option_id} missing utilities for scenarios: {sorted(missing)}")

        scenario_best = {
            sid: max(float(option.utilities[sid]) for option in options)
            for sid in scenario_ids
        }
        optionality_map = {
            DecisionClass.REVERSIBLE: 1.0,
            DecisionClass.COSTLY_REVERSIBLE: 0.5,
            DecisionClass.IRREVERSIBLE: 0.0,
        }
        evaluations: list[OptionEvaluation] = []
        for option in options:
            values = [float(option.utilities[sid]) for sid in scenario_ids]
            expected = sum(
                probabilities[sid] * float(option.utilities[sid])
                for sid in scenario_ids
            )
            worst = min(values)
            max_regret = max(
                scenario_best[sid] - float(option.utilities[sid])
                for sid in scenario_ids
            )
            remaining = 0.25
            tail_sum = 0.0
            tail_mass = 0.0
            for scenario in sorted(
                scenarios,
                key=lambda s: float(option.utilities[s.scenario_id]),
            ):
                mass = min(probabilities[scenario.scenario_id], remaining)
                if mass > 0:
                    tail_sum += mass * float(option.utilities[scenario.scenario_id])
                    tail_mass += mass
                    remaining -= mass
                if remaining <= 1e-12:
                    break
            lower_tail = tail_sum / tail_mass if tail_mass else worst
            optionality = optionality_map[option.decision_class]
            robust_score = (
                0.35 * expected
                + 0.25 * worst
                + 0.20 * lower_tail
                + 0.15 * (1.0 - max_regret)
                + 0.05 * optionality
            )
            evaluations.append(
                OptionEvaluation(
                    option.option_id,
                    expected,
                    worst,
                    lower_tail,
                    max_regret,
                    optionality,
                    robust_score,
                )
            )

        pareto = self.pareto_frontier(goal, options)
        evaluations.sort(key=lambda item: (-item.robust_score, item.option_id))
        canonical_scenarios = tuple(sorted(scenarios, key=lambda item: item.scenario_id))
        canonical_options = tuple(sorted(options, key=lambda item: item.option_id))
        pareto_ids = tuple(sorted(option.option_id for option in pareto))
        payload = {
            "goal": goal,
            "scenarios": canonical_scenarios,
            "options": canonical_options,
            "evaluations": tuple(evaluations),
            "pareto_option_ids": pareto_ids,
        }
        return DesignEvaluation(tuple(evaluations), pareto_ids, stable_digest(payload))

    def freeze_snapshot(self, vector: GoalDesignVersionVector) -> GoalDesignSnapshot:
        digest = stable_digest({"goal_design_version_vector": vector.tokens()})
        return GoalDesignSnapshot(version_vector=vector, digest=digest)

    def verify_snapshot(
        self,
        snapshot: GoalDesignSnapshot,
        current_vector: GoalDesignVersionVector,
    ) -> CoherenceReport:
        issues: list[CoherenceIssue] = []
        expected = snapshot.version_vector.tokens()
        current = current_vector.tokens()
        if snapshot.digest != stable_digest({"goal_design_version_vector": expected}):
            issues.append(
                CoherenceIssue(
                    "CORRUPT_SNAPSHOT",
                    "snapshot digest does not match its version vector",
                    IssueSeverity.BLOCKER,
                )
            )
        for plane in ("requirements", "planning", "architecture", "integration", "context"):
            if expected[plane] != current[plane]:
                issues.append(
                    CoherenceIssue(
                        f"STALE_{plane.upper()}",
                        f"{plane} changed after Goal/Design snapshot was frozen: "
                        f"{expected[plane]} -> {current[plane]}",
                        IssueSeverity.BLOCKER,
                        subject=plane,
                    )
                )
        return CoherenceReport(tuple(issues))

    def coherence_report(self, state: TraceabilityState) -> CoherenceReport:
        issues: list[CoherenceIssue] = []
        for requirement_id in sorted(
            set(state.active_requirement_ids) - set(state.planned_requirement_ids)
        ):
            issues.append(
                CoherenceIssue(
                    "UNPLANNED_REQUIREMENT",
                    f"active requirement {requirement_id} has no planning trace",
                    IssueSeverity.BLOCKER,
                    requirement_id,
                )
            )
        for component_id in sorted(
            set(state.planned_component_ids) - set(state.architecture_component_ids)
        ):
            issues.append(
                CoherenceIssue(
                    "MISSING_ARCHITECTURE_COMPONENT",
                    f"planned component {component_id} has no architecture authority",
                    IssueSeverity.BLOCKER,
                    component_id,
                )
            )
        for component_id in sorted(
            set(state.integration_component_refs) - set(state.architecture_component_ids)
        ):
            issues.append(
                CoherenceIssue(
                    "STALE_INTEGRATION_REFERENCE",
                    f"integration references unknown architecture component {component_id}",
                    IssueSeverity.BLOCKER,
                    component_id,
                )
            )
        for component_id in sorted(
            set(state.context_component_refs) - set(state.architecture_component_ids)
        ):
            issues.append(
                CoherenceIssue(
                    "STALE_CONTEXT_REFERENCE",
                    f"context references unknown architecture component {component_id}",
                    IssueSeverity.WARNING,
                    component_id,
                )
            )
        if state.expected_snapshot_digest and state.context_snapshot_digest != state.expected_snapshot_digest:
            issues.append(
                CoherenceIssue(
                    "CONTEXT_SNAPSHOT_MISMATCH",
                    "context was compiled against a different Goal/Design snapshot",
                    IssueSeverity.BLOCKER,
                    "context",
                )
            )
        return CoherenceReport(tuple(issues))

    @staticmethod
    def _traceability_manifest_state(traceability: TraceabilityState | None):
        if traceability is None:
            return None
        return {
            "active_requirement_ids": sorted(traceability.active_requirement_ids),
            "planned_requirement_ids": sorted(traceability.planned_requirement_ids),
            "planned_component_ids": sorted(traceability.planned_component_ids),
            "architecture_component_ids": sorted(traceability.architecture_component_ids),
            "integration_component_refs": sorted(traceability.integration_component_refs),
            "context_component_refs": sorted(traceability.context_component_refs),
            "context_snapshot_digest": traceability.context_snapshot_digest,
            "expected_snapshot_digest": traceability.expected_snapshot_digest,
        }

    def admit_decision(
        self,
        *,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
        selected_option_id: str,
        snapshot: GoalDesignSnapshot,
        current_vector: GoalDesignVersionVector,
        proof_obligations: Sequence[ProofObligation] = (),
        uncertainties: Sequence[UncertaintyItem] = (),
        traceability: TraceabilityState | None = None,
    ) -> DecisionReceipt:
        selected = next(
            (option for option in options if option.option_id == selected_option_id),
            None,
        )
        if selected is None:
            raise CoherenceError(f"selected option {selected_option_id!r} does not exist")

        blockers: list[str] = []
        blockers.extend(
            issue.message
            for issue in self.verify_snapshot(snapshot, current_vector).issues
            if issue.blocking
        )
        if traceability is not None:
            blockers.extend(
                issue.message
                for issue in self.coherence_report(traceability).issues
                if issue.blocking
            )
        open_proofs = [
            proof
            for proof in proof_obligations
            if proof.blocking and proof.status is ProofStatus.OPEN
        ]
        if open_proofs:
            blockers.append(
                "open proof obligations: "
                + ", ".join(proof.proof_id for proof in open_proofs)
            )
        nontrivial = selected.decision_class in {
            DecisionClass.COSTLY_REVERSIBLE,
            DecisionClass.IRREVERSIBLE,
        }
        if nontrivial and len(options) < 2:
            blockers.append(
                "costly or irreversible decision requires at least one explicit alternative"
            )
        if nontrivial:
            tags = {tag.lower() for scenario in scenarios for tag in scenario.tags}
            if not ({"counterfactual", "adversarial"} & tags):
                blockers.append(
                    "costly or irreversible decision requires a counterfactual or adversarial scenario"
                )
        if (
            selected.decision_class is DecisionClass.COSTLY_REVERSIBLE
            and not selected.rollback_ref
        ):
            blockers.append("costly reversible decision requires a rollback reference")
        if selected.decision_class is DecisionClass.IRREVERSIBLE:
            high_risk = [
                item
                for item in uncertainties
                if not item.resolved
                and not item.mitigation_ref
                and item.risk_score >= self.irreversible_uncertainty_threshold
            ]
            if high_risk:
                blockers.append(
                    "irreversible decision has unresolved high-risk uncertainty: "
                    + ", ".join(item.uncertainty_id for item in high_risk)
                )
        if blockers:
            raise CoherenceError("Goal/Design admission blocked: " + "; ".join(blockers))

        evaluation = self.evaluate_options(goal, scenarios, options)
        if goal.objectives and selected_option_id not in evaluation.pareto_option_ids:
            raise CoherenceError(
                f"selected option {selected_option_id} is Pareto-dominated under the declared goal vector"
            )

        canonical_scenarios = tuple(sorted(scenarios, key=lambda item: item.scenario_id))
        canonical_options = tuple(sorted(options, key=lambda item: item.option_id))
        canonical_proofs = tuple(sorted(proof_obligations, key=lambda item: item.proof_id))
        canonical_uncertainties = tuple(
            sorted(uncertainties, key=lambda item: item.uncertainty_id)
        )
        traceability_state = self._traceability_manifest_state(traceability)

        goal_digest = stable_digest({"goal": goal})
        scenario_set_digest = stable_digest({"scenarios": canonical_scenarios})
        option_set_digest = stable_digest({"options": canonical_options})
        proof_state_digest = stable_digest({"proof_obligations": canonical_proofs})
        uncertainty_state_digest = stable_digest(
            {"uncertainties": canonical_uncertainties}
        )
        traceability_digest = stable_digest({"traceability": traceability_state})

        input_manifest_payload = {
            "goal_digest": goal_digest,
            "scenario_set_digest": scenario_set_digest,
            "option_set_digest": option_set_digest,
            "proof_state_digest": proof_state_digest,
            "uncertainty_state_digest": uncertainty_state_digest,
            "traceability_digest": traceability_digest,
            "selected_option_id": selected_option_id,
            "snapshot_digest": snapshot.digest,
            "version_vector": snapshot.version_vector.tokens(),
        }
        input_manifest_digest = stable_digest(
            {"goal_design_decision_input_manifest": input_manifest_payload}
        )

        evidence_refs = set(goal.evidence_refs) | set(selected.evidence_refs)
        for scenario in scenarios:
            evidence_refs.update(scenario.evidence_refs)
        for proof in proof_obligations:
            evidence_refs.update(proof.evidence_refs)
        for uncertainty in uncertainties:
            evidence_refs.update(uncertainty.evidence_refs)

        receipt_payload = {
            "goal_id": goal.goal_id,
            "selected_option_id": selected_option_id,
            "snapshot_digest": snapshot.digest,
            "version_vector": snapshot.version_vector.tokens(),
            "evaluation_digest": evaluation.digest,
            "proof_obligation_ids": [proof.proof_id for proof in canonical_proofs],
            "uncertainty_ids": [item.uncertainty_id for item in canonical_uncertainties],
            "evidence_refs": sorted(evidence_refs),
            "goal_digest": goal_digest,
            "scenario_set_digest": scenario_set_digest,
            "option_set_digest": option_set_digest,
            "proof_state_digest": proof_state_digest,
            "uncertainty_state_digest": uncertainty_state_digest,
            "traceability_digest": traceability_digest,
            "input_manifest_digest": input_manifest_digest,
        }
        return DecisionReceipt(
            receipt_id=stable_digest({"goal_design_decision": receipt_payload}),
            goal_id=goal.goal_id,
            selected_option_id=selected_option_id,
            snapshot_digest=snapshot.digest,
            version_vector=snapshot.version_vector.tokens(),
            evaluation_digest=evaluation.digest,
            proof_obligation_ids=tuple(receipt_payload["proof_obligation_ids"]),
            uncertainty_ids=tuple(receipt_payload["uncertainty_ids"]),
            evidence_refs=tuple(receipt_payload["evidence_refs"]),
            goal_digest=goal_digest,
            scenario_set_digest=scenario_set_digest,
            option_set_digest=option_set_digest,
            proof_state_digest=proof_state_digest,
            uncertainty_state_digest=uncertainty_state_digest,
            traceability_digest=traceability_digest,
            input_manifest_digest=input_manifest_digest,
        )
