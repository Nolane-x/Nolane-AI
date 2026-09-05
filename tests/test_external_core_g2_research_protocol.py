from __future__ import annotations

import copy

import pytest

from nolane.external_core.research_budget import ResearchBudget, ResearchBudgetCategory
from nolane.external_core.research_protocol import (
    ResearchClosureDisposition,
    ResearchHypothesis,
    ResearchQuestionCertificate,
    assess_research_closure,
)
from nolane.external_core.research_trials import ResearchTrialLedger, ResearchTrialOutcome


def _high_stakes_question() -> ResearchQuestionCertificate:
    primary = ResearchHypothesis.create(
        statement="candidate X improves recovery robustness",
        predicted_observations=("fewer unrecovered failures", "no regression in clean runs"),
    )
    rival = ResearchHypothesis.create(
        statement="observed improvement is caused by easier workloads",
        predicted_observations=("gain disappears under matched workload",),
    )
    return ResearchQuestionCertificate.create(
        question="Does candidate X improve recovery robustness under matched conditions?",
        decision_ref="capability:candidate-x",
        scope="recovery/matched-workload",
        unknowns=("cross-platform behavior",),
        assumptions=("same toolchain", "same workload distribution"),
        hypotheses=(primary,),
        rival_hypotheses=(rival,),
        falsifiers=("matched workload shows equal or higher unrecovered failure count",),
        closure_criteria=("required trial retained", "independent verification referenced"),
        source_constraints=("primary-or-authoritative",),
        budget_class="high",
        high_stakes=True,
    )


def test_hypothesis_identity_is_content_addressed_and_restore_recomputed():
    row = ResearchHypothesis.create(
        statement="X improves reliability",
        predicted_observations=("lower failure rate",),
    )
    assert row.hypothesis_id.startswith("research-hypothesis-")
    assert ResearchHypothesis.from_state(row.to_state()) == row

    forged = copy.deepcopy(row.to_state())
    forged["hypothesis_id"] = "research-hypothesis-forged"
    with pytest.raises(ValueError, match="hypothesis identity"):
        ResearchHypothesis.from_state(forged)


def test_high_stakes_question_requires_distinct_rival_and_falsifier():
    primary = ResearchHypothesis.create(
        statement="X helps",
        predicted_observations=("fewer failures",),
    )
    with pytest.raises(ValueError, match="rival"):
        ResearchQuestionCertificate.create(
            question="Does X help?",
            decision_ref="capability:X",
            scope="recovery",
            unknowns=("generalization",),
            assumptions=("matched workload",),
            hypotheses=(primary,),
            rival_hypotheses=(),
            falsifiers=("no matched-condition gain",),
            closure_criteria=("replicate",),
            source_constraints=("primary",),
            budget_class="high",
            high_stakes=True,
        )

    with pytest.raises(ValueError, match="falsifier"):
        ResearchQuestionCertificate.create(
            question="Does X help?",
            decision_ref="capability:X",
            scope="recovery",
            unknowns=("generalization",),
            assumptions=("matched workload",),
            hypotheses=(primary,),
            rival_hypotheses=(ResearchHypothesis.create(statement="gain is workload bias", predicted_observations=("gain disappears when matched",)),),
            falsifiers=(),
            closure_criteria=("replicate",),
            source_constraints=("primary",),
            budget_class="high",
            high_stakes=True,
        )


def test_question_restore_rejects_semantic_tampering():
    question = _high_stakes_question()
    assert ResearchQuestionCertificate.from_state(question.to_state()) == question
    forged = copy.deepcopy(question.to_state())
    forged["scope"] = "different-scope"
    with pytest.raises(ValueError):
        ResearchQuestionCertificate.from_state(forged)


def test_research_budget_is_exactly_partitioned_finite_and_bool_safe():
    budget = ResearchBudget.create(
        total_units=20,
        allocations={
            "explore": 5,
            "falsify": 5,
            "verify": 5,
            "replicate": 3,
            "integrate": 2,
        },
    )
    receipt = budget.spend(
        category=ResearchBudgetCategory.EXPLORE,
        units=5,
        reason="search primary sources",
        evidence_refs=("e-budget-1",),
    )
    assert receipt.remaining_category_units == 0
    assert budget.remaining_total_units == 15

    with pytest.raises(ValueError, match="budget"):
        budget.spend(
            category=ResearchBudgetCategory.EXPLORE,
            units=1,
            reason="hidden extra search",
            evidence_refs=("e-budget-2",),
        )
    with pytest.raises(TypeError, match="units"):
        budget.spend(
            category=ResearchBudgetCategory.VERIFY,
            units=True,
            reason="invalid scalar",
            evidence_refs=("e-budget-3",),
        )
    with pytest.raises(ValueError, match="categories"):
        ResearchBudget.create(
            total_units=20,
            allocations={"explore": 20},
        )


def test_budget_restore_replays_receipts_and_rejects_spend_tampering():
    budget = ResearchBudget.create(
        total_units=10,
        allocations={"explore": 2, "falsify": 2, "verify": 2, "replicate": 2, "integrate": 2},
    )
    budget.spend(category="falsify", units=2, reason="challenge", evidence_refs=("e1",))
    assert ResearchBudget.from_state(budget.to_state()).digest == budget.digest

    forged = copy.deepcopy(budget.to_state())
    forged["receipts"][0]["units"] = 1
    with pytest.raises(ValueError):
        ResearchBudget.from_state(forged)


def test_negative_failed_and_inconclusive_trials_are_retained_append_only():
    ledger = ResearchTrialLedger()
    outcomes = (
        ResearchTrialOutcome.NEGATIVE,
        ResearchTrialOutcome.FAILED,
        ResearchTrialOutcome.INCONCLUSIVE,
    )
    trial_ids = []
    for index, outcome in enumerate(outcomes, start=1):
        row = ledger.record(
            question_id="research-question-1",
            hypothesis_id=f"hypothesis-{index}",
            producer_agent_id="research.chief",
            protocol_digest="p" * 64,
            source_state_digest="s" * 64,
            outcome=outcome,
            observation=f"observation-{index}",
            limitations=("bounded environment",),
            evidence_refs=(f"trial-evidence-{index}",),
        )
        trial_ids.append(row.trial_id)

    restored = ResearchTrialLedger.from_state(ledger.to_state())
    assert tuple(row.trial_id for row in restored.records()) == tuple(sorted(trial_ids))
    assert {row.outcome for row in restored.records()} == set(outcomes)


def test_trial_restore_rejects_forged_outcome_or_identity():
    ledger = ResearchTrialLedger()
    row = ledger.record(
        question_id="research-question-1",
        hypothesis_id="hypothesis-1",
        producer_agent_id="research.chief",
        protocol_digest="p" * 64,
        source_state_digest="s" * 64,
        outcome="negative",
        observation="candidate regressed",
        limitations=("single platform",),
        evidence_refs=("e-neg",),
    )
    state = ledger.to_state()
    forged = copy.deepcopy(state)
    forged["trials"][0]["outcome"] = "positive"
    with pytest.raises(ValueError):
        ResearchTrialLedger.from_state(forged)
    assert ledger.get(row.trial_id) == row


def test_research_closure_is_categorical_and_does_not_claim_truth_or_assurance():
    question = _high_stakes_question()
    budget = ResearchBudget.create(
        total_units=5,
        allocations={"explore": 1, "falsify": 1, "verify": 1, "replicate": 1, "integrate": 1},
    )
    ledger = ResearchTrialLedger()
    trial = ledger.record(
        question_id=question.question_id,
        hypothesis_id=question.hypotheses[0].hypothesis_id,
        producer_agent_id="research.chief",
        protocol_digest=question.digest,
        source_state_digest="s" * 64,
        outcome="negative",
        observation="rival survived one matched-condition challenge",
        limitations=("one platform",),
        evidence_refs=("e-trial",),
    )

    closure = assess_research_closure(
        question=question,
        budget=budget,
        trial_ledger=ledger,
        required_trial_ids=(trial.trial_id,),
        stale_source_ids=(),
        unresolved_claim_keys=(),
        independent_verification_refs=("verification-receipt-1",),
        evidence_refs=("e-closure",),
    )
    assert closure.disposition is ResearchClosureDisposition.CLOSED
    assert not hasattr(closure, "assurance_disposition")
    assert not hasattr(closure, "truth_value")


def test_research_closure_blocks_stale_or_unresolved_basis_and_unknowns_missing_independence():
    question = _high_stakes_question()
    budget = ResearchBudget.create(
        total_units=5,
        allocations={"explore": 1, "falsify": 1, "verify": 1, "replicate": 1, "integrate": 1},
    )
    ledger = ResearchTrialLedger()
    trial = ledger.record(
        question_id=question.question_id,
        hypothesis_id=question.hypotheses[0].hypothesis_id,
        producer_agent_id="research.chief",
        protocol_digest=question.digest,
        source_state_digest="s" * 64,
        outcome="inconclusive",
        observation="mixed result",
        limitations=("measurement gap",),
        evidence_refs=("e-trial",),
    )

    blocked = assess_research_closure(
        question=question,
        budget=budget,
        trial_ledger=ledger,
        required_trial_ids=(trial.trial_id,),
        stale_source_ids=("source-stale",),
        unresolved_claim_keys=("claim-conflict",),
        independent_verification_refs=("verification-receipt-1",),
        evidence_refs=("e-closure",),
    )
    assert blocked.disposition is ResearchClosureDisposition.BLOCKED
    assert "stale_source" in blocked.reasons
    assert "unresolved_claim" in blocked.reasons

    unknown = assess_research_closure(
        question=question,
        budget=budget,
        trial_ledger=ledger,
        required_trial_ids=(trial.trial_id,),
        stale_source_ids=(),
        unresolved_claim_keys=(),
        independent_verification_refs=(),
        evidence_refs=("e-closure",),
    )
    assert unknown.disposition is ResearchClosureDisposition.UNKNOWN
    assert "missing_independent_verification" in unknown.reasons
