from __future__ import annotations

import importlib
import importlib.util
from math import inf, nan

import pytest


CANONICAL_MODULE = "nolane.external_core.reasoning_invention"
COMPONENT_ID = "external.reasoning_invention"


def _api():
    try:
        from nolane.external_core.reasoning_invention import (
            CapabilityGap,
            CapabilityKind,
            ChallengeVerdict,
            EvidencePhase,
            HypothesisChallenge,
            InventionAssessment,
            InventionCandidate,
            InventionHypothesis,
            PredictedDelta,
            ReasoningEvidenceRef,
            ReasoningInventionReceipt,
            TransferIntent,
            VerificationPlan,
            dominates,
            pareto_frontier,
        )
    except ImportError as exc:
        pytest.fail(f"production Reasoning/Invention behavior API is missing: {exc}")
    return {
        "CapabilityGap": CapabilityGap,
        "CapabilityKind": CapabilityKind,
        "ChallengeVerdict": ChallengeVerdict,
        "EvidencePhase": EvidencePhase,
        "HypothesisChallenge": HypothesisChallenge,
        "InventionAssessment": InventionAssessment,
        "InventionCandidate": InventionCandidate,
        "InventionHypothesis": InventionHypothesis,
        "PredictedDelta": PredictedDelta,
        "ReasoningEvidenceRef": ReasoningEvidenceRef,
        "ReasoningInventionReceipt": ReasoningInventionReceipt,
        "TransferIntent": TransferIntent,
        "VerificationPlan": VerificationPlan,
        "dominates": dominates,
        "pareto_frontier": pareto_frontier,
    }


def _evidence(evidence_id: str, phase_name: str = "DISCOVERY"):
    api = _api()
    phase = getattr(api["EvidencePhase"], phase_name)
    return api["ReasoningEvidenceRef"](
        evidence_id=evidence_id,
        phase=phase,
        source_component="external.evidence",
        witness_id=f"witness:{evidence_id}",
    )


def _plan(*, reverse_sets: bool = False):
    VerificationPlan = _api()["VerificationPlan"]
    perturbations = ("probe.beta", "probe.alpha")
    controls = ("control.beta", "control.alpha")
    ablations = ("ablation.beta", "ablation.alpha")
    stops = ("stop.budget", "stop.confidence")
    if reverse_sets:
        perturbations = tuple(reversed(perturbations))
        controls = tuple(reversed(controls))
        ablations = tuple(reversed(ablations))
        stops = tuple(reversed(stops))
    return VerificationPlan(
        metric_id="metric.heldout_accuracy",
        baseline_id="baseline:cognitive-library:abc",
        success_threshold=0.75,
        perturbation_ids=perturbations,
        negative_control_ids=controls,
        ablation_ids=ablations,
        stop_condition_ids=stops,
        max_cost=8.0,
        expected_information_gain=4.0,
    )


def _hypothesis(*, reverse_sets: bool = False):
    api = _api()
    evidence = (_evidence("evidence.beta"), _evidence("evidence.alpha"))
    assumptions = ("runtime is deterministic", "heldout split is isolated")
    variables = ("normalization_strategy", "input_shape")
    invariants = ("output semantics preserved", "no hidden mutable state")
    deltas = (
        api["PredictedDelta"]("metric.robustness", 0.05, 0.20),
        api["PredictedDelta"]("metric.heldout_accuracy", 0.10, 0.30),
    )
    if reverse_sets:
        evidence = tuple(reversed(evidence))
        assumptions = tuple(reversed(assumptions))
        variables = tuple(reversed(variables))
        invariants = tuple(reversed(invariants))
        deltas = tuple(reversed(deltas))
    return api["InventionHypothesis"](
        statement="Composing verified normalization primitives improves heldout accuracy without changing output semantics.",
        discovery_evidence=evidence,
        assumptions=assumptions,
        generalized_variables=variables,
        invariants=invariants,
        predicted_deltas=deltas,
        verification_plan=_plan(reverse_sets=reverse_sets),
        candidate_synthesis_id="synthesis:proposal.alpha",
    )


def _assessment(**overrides: float):
    Assessment = _api()["InventionAssessment"]
    values = {
        "evidence_alignment": 0.80,
        "anomaly_coverage": 0.70,
        "expected_gain": 0.65,
        "robustness": 0.75,
        "transferability": 0.60,
        "uncertainty": 0.30,
        "complexity": 0.40,
        "verification_cost": 0.35,
    }
    values.update(overrides)
    return Assessment(**values)


def _candidate(assessment=None, *, causal=(), experiments=()):
    Candidate = _api()["InventionCandidate"]
    return Candidate(
        hypothesis=_hypothesis(),
        assessment=assessment or _assessment(),
        causal_program_ids=causal,
        experiment_receipt_ids=experiments,
    )


def test_reasoning_invention_canonical_module_exists() -> None:
    spec = importlib.util.find_spec(CANONICAL_MODULE)
    assert spec is not None, "canonical Reasoning/Invention protocol module is missing"


def test_reasoning_invention_declares_exact_component_revision() -> None:
    module = importlib.import_module(CANONICAL_MODULE)
    assert module.COMPONENT_ID == COMPONENT_ID
    assert module.COMPONENT_VERSION == "0.0.4"
    assert module.SCHEMA_VERSION == "reasoning-invention-v1"


def test_evidence_reference_is_phase_typed_and_round_trips_canonically() -> None:
    api = _api()
    EvidenceRef = api["ReasoningEvidenceRef"]
    EvidencePhase = api["EvidencePhase"]

    ref = EvidenceRef(
        evidence_id="evidence.alpha",
        phase=EvidencePhase.DISCOVERY,
        source_component="external.evidence",
        witness_id="witness.alpha",
    )
    assert EvidenceRef.from_state(ref.to_state()) == ref

    with pytest.raises(ValueError, match="evidence id"):
        EvidenceRef(" ", EvidencePhase.DISCOVERY, "external.evidence", "witness.alpha")
    with pytest.raises(ValueError, match="source component"):
        EvidenceRef("evidence.alpha", EvidencePhase.DISCOVERY, " ", "witness.alpha")
    with pytest.raises(ValueError, match="witness id"):
        EvidenceRef("evidence.alpha", EvidencePhase.DISCOVERY, "external.evidence", " ")


def test_verification_plan_requires_falsification_controls_and_finite_budget() -> None:
    VerificationPlan = _api()["VerificationPlan"]
    plan = _plan()
    assert plan.perturbation_ids == ("probe.alpha", "probe.beta")
    assert plan.negative_control_ids == ("control.alpha", "control.beta")
    assert plan.ablation_ids == ("ablation.alpha", "ablation.beta")
    assert plan.stop_condition_ids == ("stop.budget", "stop.confidence")
    assert plan.information_efficiency == pytest.approx(0.5)
    assert VerificationPlan.from_state(plan.to_state()) == plan

    base = dict(
        metric_id="metric.x",
        baseline_id="baseline.x",
        success_threshold=0.5,
        perturbation_ids=("probe.x",),
        negative_control_ids=("control.x",),
        ablation_ids=("ablation.x",),
        stop_condition_ids=("stop.x",),
        max_cost=1.0,
        expected_information_gain=0.5,
    )
    for field in ("perturbation_ids", "negative_control_ids", "ablation_ids", "stop_condition_ids"):
        row = dict(base)
        row[field] = ()
        with pytest.raises(ValueError, match="at least 1"):
            VerificationPlan(**row)
    for bad_cost in (0.0, -1.0, nan, inf, True):
        row = dict(base)
        row["max_cost"] = bad_cost
        with pytest.raises((TypeError, ValueError)):
            VerificationPlan(**row)
    for field in ("success_threshold", "expected_information_gain"):
        for bad in (nan, inf, True):
            row = dict(base)
            row[field] = bad
            with pytest.raises((TypeError, ValueError)):
                VerificationPlan(**row)


def test_hypothesis_is_discovery_bound_content_addressed_and_set_order_invariant() -> None:
    api = _api()
    Hypothesis = api["InventionHypothesis"]
    EvidencePhase = api["EvidencePhase"]

    first = _hypothesis()
    second = _hypothesis(reverse_sets=True)
    assert first.hypothesis_id == second.hypothesis_id
    assert first.discovery_evidence == second.discovery_evidence
    assert first.verification_plan.plan_id == second.verification_plan.plan_id
    assert Hypothesis.from_state(first.to_state()) == first

    with pytest.raises(ValueError, match="discovery evidence"):
        Hypothesis(
            statement=first.statement,
            discovery_evidence=(
                api["ReasoningEvidenceRef"](
                    "evidence.challenge",
                    EvidencePhase.INDEPENDENT_CHALLENGE,
                    "external.evidence",
                    "witness.challenge",
                ),
            ),
            assumptions=first.assumptions,
            generalized_variables=first.generalized_variables,
            invariants=first.invariants,
            predicted_deltas=first.predicted_deltas,
            verification_plan=first.verification_plan,
            candidate_synthesis_id=first.candidate_synthesis_id,
        )


def test_predicted_delta_rejects_non_finite_or_inverted_ranges() -> None:
    PredictedDelta = _api()["PredictedDelta"]
    with pytest.raises(ValueError, match="minimum"):
        PredictedDelta("metric.x", 0.5, 0.1)
    for bad in (nan, inf, True):
        with pytest.raises((TypeError, ValueError)):
            PredictedDelta("metric.x", bad, 0.5)


def test_assessment_is_bounded_and_pareto_dominance_has_no_hidden_scalar() -> None:
    api = _api()
    dominates = api["dominates"]

    strong = _assessment(
        evidence_alignment=0.9,
        anomaly_coverage=0.9,
        expected_gain=0.8,
        robustness=0.9,
        transferability=0.8,
        uncertainty=0.2,
        complexity=0.3,
        verification_cost=0.2,
    )
    weak = _assessment(
        evidence_alignment=0.7,
        anomaly_coverage=0.6,
        expected_gain=0.6,
        robustness=0.7,
        transferability=0.5,
        uncertainty=0.4,
        complexity=0.5,
        verification_cost=0.4,
    )
    tradeoff = _assessment(expected_gain=0.95, uncertainty=0.55)

    assert dominates(strong, weak)
    assert not dominates(weak, strong)
    assert not dominates(strong, tradeoff)
    assert not dominates(tradeoff, strong)
    assert not dominates(strong, strong)

    Assessment = api["InventionAssessment"]
    for field in (
        "evidence_alignment",
        "anomaly_coverage",
        "expected_gain",
        "robustness",
        "transferability",
        "uncertainty",
        "complexity",
        "verification_cost",
    ):
        values = _assessment().to_state()
        values.pop("schema_version", None)
        values[field] = 1.01
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            Assessment(**values)


def test_pareto_frontier_is_order_invariant_and_keeps_legitimate_tradeoffs() -> None:
    frontier = _api()["pareto_frontier"]
    dominant = _candidate(
        _assessment(
            evidence_alignment=0.95,
            anomaly_coverage=0.90,
            expected_gain=0.80,
            robustness=0.90,
            transferability=0.75,
            uncertainty=0.15,
            complexity=0.25,
            verification_cost=0.20,
        ),
        causal=("causal.strong",),
    )
    dominated = _candidate(
        _assessment(
            evidence_alignment=0.70,
            anomaly_coverage=0.60,
            expected_gain=0.55,
            robustness=0.65,
            transferability=0.50,
            uncertainty=0.45,
            complexity=0.55,
            verification_cost=0.50,
        ),
        causal=("causal.weak",),
    )
    high_gain_tradeoff = _candidate(
        _assessment(expected_gain=0.99, uncertainty=0.60),
        experiments=("experiment.tradeoff",),
    )

    first = frontier((dominated, high_gain_tradeoff, dominant))
    second = frontier((dominant, dominated, high_gain_tradeoff))
    assert tuple(row.candidate_id for row in first) == tuple(row.candidate_id for row in second)
    assert tuple(row.candidate_id for row in first) == tuple(sorted(row.candidate_id for row in first))
    assert {row.candidate_id for row in first} == {dominant.candidate_id, high_gain_tradeoff.candidate_id}


def test_independent_challenge_cannot_reuse_discovery_or_self_verify_without_support() -> None:
    api = _api()
    Challenge = api["HypothesisChallenge"]
    Verdict = api["ChallengeVerdict"]

    challenge_evidence = (_evidence("evidence.challenge", "INDEPENDENT_CHALLENGE"),)
    verified = Challenge(
        hypothesis_id=_hypothesis().hypothesis_id,
        challenge_evidence=challenge_evidence,
        causal_program_ids=("causal.alpha",),
        experiment_receipt_ids=(),
        verdict=Verdict.VERIFIED,
        reason="bounded intervention reproduced the predicted effect",
    )
    assert Challenge.from_state(verified.to_state()) == verified

    with pytest.raises(ValueError, match="independent-challenge evidence"):
        Challenge(
            hypothesis_id=_hypothesis().hypothesis_id,
            challenge_evidence=(_evidence("evidence.discovery"),),
            causal_program_ids=("causal.alpha",),
            experiment_receipt_ids=(),
            verdict=Verdict.VERIFIED,
            reason="phase confusion",
        )
    with pytest.raises(ValueError, match="causal or experiment"):
        Challenge(
            hypothesis_id=_hypothesis().hypothesis_id,
            challenge_evidence=challenge_evidence,
            causal_program_ids=(),
            experiment_receipt_ids=(),
            verdict=Verdict.VERIFIED,
            reason="unsupported verification label",
        )


def test_capability_gap_is_intent_only_and_binds_exact_library_baseline() -> None:
    api = _api()
    CapabilityGap = api["CapabilityGap"]
    CapabilityKind = api["CapabilityKind"]

    gap = CapabilityGap(
        objective="acquire robust text normalization",
        capability_kind=CapabilityKind.ABSTRACTION,
        cognitive_library_digest="library:digest:abc",
        insufficiency_evidence=(
            _evidence("evidence.gap.beta"),
            _evidence("evidence.gap.alpha", "INDEPENDENT_CHALLENGE"),
        ),
        acceptance_test_ids=("test.holdout", "test.negative-control"),
        candidate_synthesis_id="candidate:synthesis.alpha",
        verified_challenge_id="challenge:verified.alpha",
    )
    assert gap.cognitive_library_digest == "library:digest:abc"
    assert CapabilityGap.from_state(gap.to_state()) == gap
    assert not hasattr(gap, "promote")
    assert not hasattr(gap, "admit")

    with pytest.raises(ValueError, match="insufficiency evidence"):
        CapabilityGap(
            objective=gap.objective,
            capability_kind=gap.capability_kind,
            cognitive_library_digest=gap.cognitive_library_digest,
            insufficiency_evidence=(),
            acceptance_test_ids=gap.acceptance_test_ids,
            candidate_synthesis_id=gap.candidate_synthesis_id,
            verified_challenge_id=None,
        )
    with pytest.raises(ValueError, match="acceptance test"):
        CapabilityGap(
            objective=gap.objective,
            capability_kind=gap.capability_kind,
            cognitive_library_digest=gap.cognitive_library_digest,
            insufficiency_evidence=gap.insufficiency_evidence,
            acceptance_test_ids=(),
            candidate_synthesis_id=gap.candidate_synthesis_id,
            verified_challenge_id=None,
        )


def test_transfer_intent_is_destination_bound_and_requires_invariants_and_trials() -> None:
    TransferIntent = _api()["TransferIntent"]
    intent = TransferIntent(
        source_domain="repo.python",
        target_domain="repo.rust",
        source_receipt_ids=("receipt.beta", "receipt.alpha"),
        verified_challenge_ids=("challenge.beta", "challenge.alpha"),
        generalized_variables=("repository_language", "symbol_graph"),
        invariants=("semantic target preserved",),
        target_assumptions=("target parser is available",),
        transfer_trial_ids=("trial.heldout", "trial.adversarial"),
    )
    restored = TransferIntent.from_state(intent.to_state())
    assert restored == intent
    assert restored.source_receipt_ids == ("receipt.alpha", "receipt.beta")
    assert not hasattr(intent, "accept")
    assert not hasattr(intent, "reuse")

    with pytest.raises(ValueError, match="must differ"):
        TransferIntent(
            source_domain="repo.python",
            target_domain="repo.python",
            source_receipt_ids=("receipt.alpha",),
            verified_challenge_ids=(),
            generalized_variables=("language",),
            invariants=("semantics",),
            target_assumptions=(),
            transfer_trial_ids=("trial.one",),
        )
    for field in ("generalized_variables", "invariants", "transfer_trial_ids"):
        row = dict(
            source_domain="repo.python",
            target_domain="repo.rust",
            source_receipt_ids=("receipt.alpha",),
            verified_challenge_ids=(),
            generalized_variables=("language",),
            invariants=("semantics",),
            target_assumptions=(),
            transfer_trial_ids=("trial.one",),
        )
        row[field] = ()
        with pytest.raises(ValueError, match="at least 1"):
            TransferIntent(**row)


def test_receipt_aggregates_canonical_ids_without_mutation_authority() -> None:
    api = _api()
    Receipt = api["ReasoningInventionReceipt"]
    hypothesis = _hypothesis()
    candidate = _candidate(causal=("causal.alpha",))
    receipt = Receipt(
        hypothesis_ids=(hypothesis.hypothesis_id,),
        frontier_candidate_ids=(candidate.candidate_id,),
        challenge_ids=("challenge.alpha",),
        capability_gap_ids=("gap.alpha",),
        transfer_intent_ids=("transfer.alpha",),
    )
    assert Receipt.from_state(receipt.to_state()) == receipt
    for forbidden in ("promoted", "installed", "reused", "assurance_receipt_id"):
        assert not hasattr(receipt, forbidden)


def test_derived_identity_tampering_and_noncanonical_order_fail_closed() -> None:
    api = _api()
    Hypothesis = api["InventionHypothesis"]
    Receipt = api["ReasoningInventionReceipt"]

    hypothesis = _hypothesis()
    tampered = hypothesis.to_state()
    tampered["hypothesis_id"] = "hypothesis:tampered"
    with pytest.raises(ValueError, match="identity"):
        Hypothesis.from_state(tampered)

    noncanonical = hypothesis.to_state()
    noncanonical["assumptions"] = list(reversed(noncanonical["assumptions"]))
    with pytest.raises(ValueError, match="non-canonical"):
        Hypothesis.from_state(noncanonical)

    receipt = Receipt(
        hypothesis_ids=("hypothesis.beta", "hypothesis.alpha"),
        frontier_candidate_ids=("candidate.beta", "candidate.alpha"),
        challenge_ids=(),
        capability_gap_ids=(),
        transfer_intent_ids=(),
    )
    state = receipt.to_state()
    state["receipt_id"] = "reasoning:tampered"
    with pytest.raises(ValueError, match="identity"):
        Receipt.from_state(state)


def test_protocol_surface_does_not_import_mutable_c_governors_or_assurance() -> None:
    module = importlib.import_module(CANONICAL_MODULE)
    forbidden = {
        "CapabilityAcquisitionGovernor",
        "TransferMetaGovernor",
        "AssuranceControlPlane",
        "CognitiveLibrary",
    }
    assert forbidden.isdisjoint(module.__dict__)
