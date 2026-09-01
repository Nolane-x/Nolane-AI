"""Quantified stress-world and reversibility authority for D. Goal / Design.

This module is a companion admission authority. It consumes existing Goal/Design
scenarios and option utilities, adds evidence-bearing stress/recovery metadata,
and emits deterministic admission tokens. It does not own truth and it does not
rewrite historical decision receipt identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Iterable, Sequence

from . import _goal_design_base as _base
from ._goal_design_base import DecisionClass, DesignOption, DesignScenario, GoalSpec, stable_digest

__version__ = "0.1.1"


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _required_refs(name: str, values: Iterable[str]) -> tuple[str, ...]:
    refs = _refs(values)
    if not refs:
        raise ValueError(f"{name} requires evidence refs")
    return refs


def _bounded(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return value


class StressWorldKind(str, Enum):
    COUNTERFACTUAL = "counterfactual"
    ADVERSARIAL = "adversarial"
    TAIL = "tail"
    FAILURE = "failure"


@dataclass(frozen=True)
class StressWorldEvidence:
    world_id: str
    scenario_id: str
    kind: StressWorldKind
    plausibility: float
    severity: float
    evidence_refs: tuple[str, ...]
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        world_id = str(self.world_id).strip()
        scenario_id = str(self.scenario_id).strip()
        if not world_id or not scenario_id:
            raise ValueError("stress world requires world_id and scenario_id")
        object.__setattr__(self, "world_id", world_id)
        object.__setattr__(self, "scenario_id", scenario_id)
        object.__setattr__(self, "kind", StressWorldKind(self.kind))
        object.__setattr__(self, "plausibility", _bounded("stress plausibility", self.plausibility))
        object.__setattr__(self, "severity", _bounded("stress severity", self.severity))
        object.__setattr__(
            self,
            "evidence_refs",
            _required_refs("stress world", self.evidence_refs),
        )
        payload = {
            "world_id": self.world_id,
            "scenario_id": self.scenario_id,
            "kind": self.kind.value,
            "plausibility": self.plausibility,
            "severity": self.severity,
            "evidence_refs": list(self.evidence_refs),
        }
        object.__setattr__(
            self,
            "digest",
            stable_digest({"goal_design_stress_world_evidence": payload}),
        )


@dataclass(frozen=True)
class RecoveryProfile:
    option_id: str
    recovery_probability: float
    recovery_cost: float
    recovery_latency: float
    residual_harm: float
    evidence_refs: tuple[str, ...]
    rollback_ref: str | None = None
    containment_ref: str | None = None
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        option_id = str(self.option_id).strip()
        if not option_id:
            raise ValueError("recovery profile requires option_id")
        object.__setattr__(self, "option_id", option_id)
        object.__setattr__(
            self,
            "rollback_ref",
            str(self.rollback_ref).strip() if self.rollback_ref is not None else None,
        )
        object.__setattr__(
            self,
            "containment_ref",
            str(self.containment_ref).strip() if self.containment_ref is not None else None,
        )
        object.__setattr__(
            self,
            "recovery_probability",
            _bounded("recovery_probability", self.recovery_probability),
        )
        object.__setattr__(self, "recovery_cost", _bounded("recovery_cost", self.recovery_cost))
        object.__setattr__(
            self,
            "recovery_latency",
            _bounded("recovery_latency", self.recovery_latency),
        )
        object.__setattr__(self, "residual_harm", _bounded("residual_harm", self.residual_harm))
        object.__setattr__(
            self,
            "evidence_refs",
            _required_refs("recovery profile", self.evidence_refs),
        )
        payload = {
            "option_id": self.option_id,
            "rollback_ref": self.rollback_ref,
            "containment_ref": self.containment_ref,
            "recovery_probability": self.recovery_probability,
            "recovery_cost": self.recovery_cost,
            "recovery_latency": self.recovery_latency,
            "residual_harm": self.residual_harm,
            "evidence_refs": list(self.evidence_refs),
        }
        object.__setattr__(
            self,
            "digest",
            stable_digest({"goal_design_recovery_profile": payload}),
        )

    @property
    def recovery_score(self) -> float:
        return (
            self.recovery_probability
            * (1.0 - self.recovery_cost)
            * (1.0 - self.recovery_latency)
            * (1.0 - self.residual_harm)
        )


@dataclass(frozen=True)
class StressPolicy:
    costly_max_exposure: float = 0.60
    costly_min_recovery_score: float = 0.12
    costly_max_residual_harm: float = 0.50
    irreversible_max_exposure: float = 0.45
    irreversible_min_recovery_score: float = 0.08
    irreversible_max_residual_harm: float = 0.35
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "costly_max_exposure",
            "costly_min_recovery_score",
            "costly_max_residual_harm",
            "irreversible_max_exposure",
            "irreversible_min_recovery_score",
            "irreversible_max_residual_harm",
        ):
            object.__setattr__(self, name, _bounded(name, getattr(self, name)))
        payload = {
            "costly_max_exposure": self.costly_max_exposure,
            "costly_min_recovery_score": self.costly_min_recovery_score,
            "costly_max_residual_harm": self.costly_max_residual_harm,
            "irreversible_max_exposure": self.irreversible_max_exposure,
            "irreversible_min_recovery_score": self.irreversible_min_recovery_score,
            "irreversible_max_residual_harm": self.irreversible_max_residual_harm,
        }
        object.__setattr__(
            self,
            "digest",
            stable_digest({"goal_design_stress_policy": payload}),
        )


@dataclass(frozen=True)
class StressAdmissionToken:
    token_id: str
    goal_digest: str
    scenario_set_digest: str
    option_set_digest: str
    selected_option_id: str
    decision_class: DecisionClass
    policy_digest: str
    stress_world_digests: tuple[str, ...]
    recovery_profile_digests: tuple[str, ...]
    max_stress_exposure: float
    max_allowed_exposure: float
    selected_recovery_score: float
    selected_residual_harm: float
    frontier_option_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    authorized: bool
    digest: str


@dataclass(frozen=True)
class DecisionStressReceipt:
    receipt_id: str
    decision_receipt_id: str
    stress_token_id: str
    stress_token_digest: str
    digest: str


class GoalDesignStressAuthority:
    """Deterministic quantified stress gate for non-trivial design decisions."""

    _OPTIONALITY = {
        DecisionClass.REVERSIBLE: 1.0,
        DecisionClass.COSTLY_REVERSIBLE: 0.5,
        DecisionClass.IRREVERSIBLE: 0.0,
    }

    def __init__(self, *, default_policy: StressPolicy | None = None) -> None:
        self.default_policy = default_policy or StressPolicy()
        self._decision_receipts: dict[str, DecisionStressReceipt] = {}

    @staticmethod
    def _canonical_inputs(
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
    ) -> tuple[str, str, str, tuple[DesignScenario, ...], tuple[DesignOption, ...]]:
        canonical_scenarios = tuple(sorted(scenarios, key=lambda item: item.scenario_id))
        canonical_options = tuple(sorted(options, key=lambda item: item.option_id))
        scenario_ids = [item.scenario_id for item in canonical_scenarios]
        option_ids = [item.option_id for item in canonical_options]
        if not canonical_scenarios or len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("stress authority requires unique design scenarios")
        if not canonical_options or len(option_ids) != len(set(option_ids)):
            raise ValueError("stress authority requires unique design options")
        return (
            stable_digest({"goal_design_stress_goal": goal}),
            stable_digest({"goal_design_stress_scenarios": canonical_scenarios}),
            stable_digest({"goal_design_stress_options": canonical_options}),
            canonical_scenarios,
            canonical_options,
        )

    @staticmethod
    def _canonical_worlds(
        worlds: Sequence[StressWorldEvidence],
        *,
        scenario_ids: set[str],
    ) -> tuple[StressWorldEvidence, ...]:
        canonical = tuple(sorted(worlds, key=lambda item: item.world_id))
        world_ids = [item.world_id for item in canonical]
        world_scenarios = [item.scenario_id for item in canonical]
        if len(world_ids) != len(set(world_ids)):
            raise ValueError("duplicate Goal/Design stress world identity")
        if len(world_scenarios) != len(set(world_scenarios)):
            raise ValueError("multiple stress worlds cannot launder one scenario into multiple coverage classes")
        unknown = sorted(set(world_scenarios) - scenario_ids)
        if unknown:
            raise ValueError(f"stress worlds reference unknown design scenarios: {unknown}")
        return canonical

    @staticmethod
    def _canonical_profiles(
        profiles: Sequence[RecoveryProfile],
        *,
        option_ids: set[str],
    ) -> tuple[RecoveryProfile, ...]:
        canonical = tuple(sorted(profiles, key=lambda item: item.option_id))
        ids = [item.option_id for item in canonical]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Goal/Design recovery profile option identity")
        unknown = sorted(set(ids) - option_ids)
        if unknown:
            raise ValueError(f"recovery profiles reference unknown design options: {unknown}")
        return canonical

    @classmethod
    def _reversibility_frontier(
        cls,
        *,
        evaluation: _base.DesignEvaluation,
        options: Sequence[DesignOption],
        profiles: Sequence[RecoveryProfile],
    ) -> tuple[str, ...]:
        robust_by_id = {item.option_id: float(item.robust_score) for item in evaluation.options}
        profile_by_id = {item.option_id: item for item in profiles}
        # DecisionClass carries a structural lower bound on exit capacity. Evidence
        # may prove stronger recovery than that baseline, but caller-supplied
        # profiles must never be able to degrade a rival below its structural
        # class and thereby launder the selected option onto the frontier.
        reversibility = {
            option.option_id: max(
                cls._OPTIONALITY[option.decision_class],
                (
                    profile_by_id[option.option_id].recovery_score
                    if option.option_id in profile_by_id
                    else 0.0
                ),
            )
            for option in options
        }

        frontier: list[str] = []
        eps = 1e-12
        for option in options:
            option_id = option.option_id
            dominated = False
            for other in options:
                if other.option_id == option_id:
                    continue
                robust_weak = robust_by_id[other.option_id] + eps >= robust_by_id[option_id]
                reversible_weak = reversibility[other.option_id] + eps >= reversibility[option_id]
                strict = (
                    robust_by_id[other.option_id] > robust_by_id[option_id] + eps
                    or reversibility[other.option_id] > reversibility[option_id] + eps
                )
                if robust_weak and reversible_weak and strict:
                    dominated = True
                    break
            if not dominated:
                frontier.append(option_id)
        return tuple(sorted(frontier))

    @staticmethod
    def _token_payload(
        *,
        goal_digest: str,
        scenario_set_digest: str,
        option_set_digest: str,
        selected_option_id: str,
        decision_class: DecisionClass,
        policy_digest: str,
        stress_world_digests: tuple[str, ...],
        recovery_profile_digests: tuple[str, ...],
        max_stress_exposure: float,
        max_allowed_exposure: float,
        selected_recovery_score: float,
        selected_residual_harm: float,
        frontier_option_ids: tuple[str, ...],
        blockers: tuple[str, ...],
        authorized: bool,
    ) -> dict[str, object]:
        return {
            "goal_digest": goal_digest,
            "scenario_set_digest": scenario_set_digest,
            "option_set_digest": option_set_digest,
            "selected_option_id": selected_option_id,
            "decision_class": decision_class.value,
            "policy_digest": policy_digest,
            "stress_world_digests": list(stress_world_digests),
            "recovery_profile_digests": list(recovery_profile_digests),
            "max_stress_exposure": max_stress_exposure,
            "max_allowed_exposure": max_allowed_exposure,
            "selected_recovery_score": selected_recovery_score,
            "selected_residual_harm": selected_residual_harm,
            "frontier_option_ids": list(frontier_option_ids),
            "blockers": list(blockers),
            "authorized": bool(authorized),
        }

    def authorize(
        self,
        *,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
        selected_option_id: str,
        worlds: Sequence[StressWorldEvidence] = (),
        recovery_profiles: Sequence[RecoveryProfile] = (),
        policy: StressPolicy | None = None,
    ) -> StressAdmissionToken:
        policy = policy or self.default_policy
        if not isinstance(policy, StressPolicy):
            raise TypeError("stress policy must be StressPolicy")
        goal_digest, scenario_digest, option_digest, canonical_scenarios, canonical_options = self._canonical_inputs(
            goal, scenarios, options
        )
        selected_option_id = str(selected_option_id).strip()
        selected = next(
            (option for option in canonical_options if option.option_id == selected_option_id),
            None,
        )
        if selected is None:
            raise ValueError(f"stress authority selected option does not exist: {selected_option_id}")

        scenario_ids = {item.scenario_id for item in canonical_scenarios}
        option_ids = {item.option_id for item in canonical_options}
        canonical_worlds = self._canonical_worlds(tuple(worlds), scenario_ids=scenario_ids)
        canonical_profiles = self._canonical_profiles(
            tuple(recovery_profiles), option_ids=option_ids
        )
        profile_by_id = {item.option_id: item for item in canonical_profiles}
        selected_profile = profile_by_id.get(selected.option_id)

        evaluation = _base.GoalDesignCoherencePlane().evaluate_options(
            goal,
            canonical_scenarios,
            canonical_options,
        )
        frontier = self._reversibility_frontier(
            evaluation=evaluation,
            options=canonical_options,
            profiles=canonical_profiles,
        )

        kinds = {world.kind for world in canonical_worlds}
        exposures = tuple(
            world.plausibility
            * world.severity
            * (1.0 - float(selected.utilities[world.scenario_id]))
            for world in canonical_worlds
        )
        max_exposure = max(exposures, default=0.0)
        selected_recovery_score = selected_profile.recovery_score if selected_profile else 0.0
        selected_residual_harm = selected_profile.residual_harm if selected_profile else 1.0
        blockers: list[str] = []

        if selected.decision_class is DecisionClass.COSTLY_REVERSIBLE:
            max_allowed_exposure = policy.costly_max_exposure
            if not ({StressWorldKind.ADVERSARIAL, StressWorldKind.COUNTERFACTUAL} & kinds):
                blockers.append("costly reversible decision requires evidence-bearing adversarial or counterfactual stress world")
            if selected_profile is None:
                blockers.append("costly reversible decision requires a recovery profile")
            else:
                if not selected.rollback_ref or selected_profile.rollback_ref != selected.rollback_ref:
                    blockers.append("costly reversible recovery profile rollback reference must match selected option")
                if selected_profile.recovery_score < policy.costly_min_recovery_score:
                    blockers.append("costly reversible recovery score is below stress policy floor")
                if selected_profile.residual_harm > policy.costly_max_residual_harm:
                    blockers.append("costly reversible residual harm exceeds stress policy ceiling")
            if max_exposure > policy.costly_max_exposure:
                blockers.append("costly reversible stress exposure exceeds policy ceiling")
        elif selected.decision_class is DecisionClass.IRREVERSIBLE:
            max_allowed_exposure = policy.irreversible_max_exposure
            if not ({StressWorldKind.ADVERSARIAL, StressWorldKind.COUNTERFACTUAL} & kinds):
                blockers.append("irreversible decision requires evidence-bearing adversarial or counterfactual stress world")
            if not ({StressWorldKind.TAIL, StressWorldKind.FAILURE} & kinds):
                blockers.append("irreversible decision requires independent tail or failure stress world")
            if selected_profile is None:
                blockers.append("irreversible decision requires a recovery/containment profile")
            else:
                if not (selected_profile.containment_ref or "").strip():
                    blockers.append("irreversible recovery profile requires containment authority")
                if selected_profile.recovery_score < policy.irreversible_min_recovery_score:
                    blockers.append("irreversible recovery/containment score is below stress policy floor")
                if selected_profile.residual_harm > policy.irreversible_max_residual_harm:
                    blockers.append("irreversible residual harm exceeds stress policy ceiling")
            if max_exposure > policy.irreversible_max_exposure:
                blockers.append("irreversible stress exposure exceeds policy ceiling")
        else:
            max_allowed_exposure = 1.0
            selected_residual_harm = selected_profile.residual_harm if selected_profile else 0.0

        if selected.decision_class is not DecisionClass.REVERSIBLE and selected.option_id not in frontier:
            blockers.append("selected option is outside the robust-score × reversibility frontier")

        blockers_tuple = tuple(sorted(set(blockers)))
        authorized = not blockers_tuple
        world_digests = tuple(item.digest for item in canonical_worlds)
        profile_digests = tuple(item.digest for item in canonical_profiles)
        payload = self._token_payload(
            goal_digest=goal_digest,
            scenario_set_digest=scenario_digest,
            option_set_digest=option_digest,
            selected_option_id=selected.option_id,
            decision_class=selected.decision_class,
            policy_digest=policy.digest,
            stress_world_digests=world_digests,
            recovery_profile_digests=profile_digests,
            max_stress_exposure=max_exposure,
            max_allowed_exposure=max_allowed_exposure,
            selected_recovery_score=selected_recovery_score,
            selected_residual_harm=selected_residual_harm,
            frontier_option_ids=frontier,
            blockers=blockers_tuple,
            authorized=authorized,
        )
        token_id = stable_digest({"goal_design_stress_admission_token_identity": payload})
        digest = stable_digest(
            {"goal_design_stress_admission_token": {**payload, "token_id": token_id}}
        )
        return StressAdmissionToken(
            token_id=token_id,
            goal_digest=goal_digest,
            scenario_set_digest=scenario_digest,
            option_set_digest=option_digest,
            selected_option_id=selected.option_id,
            decision_class=selected.decision_class,
            policy_digest=policy.digest,
            stress_world_digests=world_digests,
            recovery_profile_digests=profile_digests,
            max_stress_exposure=max_exposure,
            max_allowed_exposure=max_allowed_exposure,
            selected_recovery_score=selected_recovery_score,
            selected_residual_harm=selected_residual_harm,
            frontier_option_ids=frontier,
            blockers=blockers_tuple,
            authorized=authorized,
            digest=digest,
        )

    def verify_token(
        self,
        token: StressAdmissionToken,
        *,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
        selected_option_id: str,
        worlds: Sequence[StressWorldEvidence] = (),
        recovery_profiles: Sequence[RecoveryProfile] = (),
        policy: StressPolicy | None = None,
    ) -> StressAdmissionToken:
        expected = self.authorize(
            goal=goal,
            scenarios=scenarios,
            options=options,
            selected_option_id=selected_option_id,
            worlds=worlds,
            recovery_profiles=recovery_profiles,
            policy=policy,
        )
        if token != expected:
            raise ValueError("Goal/Design stress token mismatch or stale authority")
        return expected

    def bind_decision(
        self,
        token: StressAdmissionToken,
        *,
        decision_receipt_id: str,
    ) -> DecisionStressReceipt:
        decision_receipt_id = str(decision_receipt_id).strip()
        if not decision_receipt_id:
            raise ValueError("decision stress receipt requires decision_receipt_id")
        if not token.authorized:
            raise ValueError("cannot bind unauthorized Goal/Design stress token")
        payload = {
            "decision_receipt_id": decision_receipt_id,
            "stress_token_id": token.token_id,
            "stress_token_digest": token.digest,
        }
        receipt_id = stable_digest({"goal_design_decision_stress_receipt_identity": payload})
        digest = stable_digest(
            {"goal_design_decision_stress_receipt": {**payload, "receipt_id": receipt_id}}
        )
        receipt = DecisionStressReceipt(
            receipt_id=receipt_id,
            decision_receipt_id=decision_receipt_id,
            stress_token_id=token.token_id,
            stress_token_digest=token.digest,
            digest=digest,
        )
        existing = self._decision_receipts.get(decision_receipt_id)
        if existing is not None and existing != receipt:
            raise ValueError("decision stress authority cannot be rebound to a different token")
        self._decision_receipts[decision_receipt_id] = receipt
        return receipt

    def decision_receipt(self, decision_receipt_id: str) -> DecisionStressReceipt | None:
        return self._decision_receipts.get(str(decision_receipt_id))


__all__ = [
    "DecisionStressReceipt",
    "GoalDesignStressAuthority",
    "RecoveryProfile",
    "StressAdmissionToken",
    "StressPolicy",
    "StressWorldEvidence",
    "StressWorldKind",
]
