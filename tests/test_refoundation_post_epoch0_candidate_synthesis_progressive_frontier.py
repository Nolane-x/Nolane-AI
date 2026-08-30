from __future__ import annotations

import itertools
import math

import pytest

from nolane.external_core.capability_acquisition import (
    CapabilityAcquisitionGovernor,
    CapabilityCandidate,
    CapabilityState,
)
from nolane.external_core.candidate_synthesis import (
    CandidateSynthesisEngine,
    EvidencePhase,
    EvidenceRef,
    SynthesisMode,
    SynthesisReceipt,
    SynthesisRequest,
)
from nolane.external_core.cognitive_library import CognitiveLibrary
from nolane.external_core.cognitive_operators import Binary, Unary
from nolane.external_core.cognitive_vocabulary import LearnedAbstraction, TemplateParam, make_abstraction
from nolane.metadata.implementation_status import build_component_implementation_ledger
from nolane.metadata.manifests import build_component_manifests


COMPONENT_ID = "external.candidate_synthesis"
PROGRESSIVE_MODE_NAME = "PROGRESSIVE_MULTI_DEPTH_SEARCH"


def _simple(op: str, task_id: str) -> LearnedAbstraction:
    template = Unary(op, TemplateParam(0))
    return make_abstraction(
        template,
        parameter_count=1,
        support_task_ids=(task_id,),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _complex(task_id: str) -> LearnedAbstraction:
    template = Binary("add", TemplateParam(0), TemplateParam(0))
    return make_abstraction(
        template,
        parameter_count=1,
        support_task_ids=(task_id,),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _search_library() -> tuple[CognitiveLibrary, tuple[LearnedAbstraction, ...]]:
    sources = (
        _simple("strip", "task.strip"),
        _simple("upper", "task.upper"),
        _complex("task.double"),
    )
    return CognitiveLibrary(abstractions=sources), sources


def _progressive_request(
    source_ids: tuple[str, ...],
    *,
    budget: int,
    evidence_phase: EvidencePhase = EvidencePhase.DISCOVERY,
) -> SynthesisRequest:
    mode = getattr(SynthesisMode, PROGRESSIVE_MODE_NAME)
    return SynthesisRequest(
        mode=mode,
        objective="search progressive multi-depth unary compositions",
        source_item_ids=source_ids,
        evidence=(EvidenceRef("evidence.progressive.discovery", evidence_phase),),
        experiment_receipt_ids=("experiment.progressive",),
        causal_program_ids=("causal.progressive",),
        generation_budget=budget,
    )


def _composition_candidate(
    engine: CandidateSynthesisEngine,
    sources: tuple[LearnedAbstraction, ...],
) -> CapabilityCandidate:
    result = engine.synthesize(
        SynthesisRequest(
            mode=SynthesisMode.LEARNED_ABSTRACTION_COMPOSITION,
            objective="derive progressive-search oracle from existing composition contract",
            source_item_ids=tuple(row.abstraction_id for row in sources),
            evidence=(),
            experiment_receipt_ids=(),
            causal_program_ids=(),
            generation_budget=1,
        )
    )
    assert result.candidate is not None
    return result.candidate


def _score(candidate: CapabilityCandidate) -> tuple[int, int, str]:
    payload = candidate.payload()
    assert isinstance(payload, LearnedAbstraction)
    return (
        payload.template.cost,
        -len(payload.support_task_ids),
        candidate.candidate_id,
    )


def _ordered_sources(sources: tuple[LearnedAbstraction, ...]) -> tuple[LearnedAbstraction, ...]:
    return tuple(sorted(sources, key=lambda row: row.abstraction_id))


def _generated_at_depth(
    engine: CandidateSynthesisEngine,
    sources: tuple[LearnedAbstraction, ...],
    depth: int,
) -> tuple[LearnedAbstraction, ...]:
    generated: list[LearnedAbstraction] = []
    for hypothesis in itertools.permutations(_ordered_sources(sources), depth):
        payload = _composition_candidate(engine, hypothesis).payload()
        assert isinstance(payload, LearnedAbstraction)
        generated.append(payload)
    return tuple(generated)


def test_component_advances_to_v004_without_legacy_schema_bump() -> None:
    manifests = {row.component_id: row for row in build_component_manifests()}
    manifest = manifests[COMPONENT_ID]
    assert str(manifest.version) == "0.0.4"
    assert manifest.state_schema == "candidate-synthesis-v1"

    ledger = build_component_implementation_ledger()[COMPONENT_ID]
    assert ledger.component_version == "0.0.4"


def test_progressive_pool_order_is_canonical_and_request_round_trips() -> None:
    _, sources = _search_library()
    ids = tuple(row.abstraction_id for row in sources)

    first = _progressive_request(ids, budget=6)
    second = _progressive_request(tuple(reversed(ids)), budget=6)

    assert first.source_item_ids == tuple(sorted(ids))
    assert second == first
    assert first.to_state()["schema_version"] == "candidate-synthesis-v1"
    assert SynthesisRequest.from_state(first.to_state()) == first


def test_partial_depth_two_frontier_abstains_even_after_novel_observations() -> None:
    library, sources = _search_library()
    ids = tuple(row.abstraction_id for row in sources)

    result = CandidateSynthesisEngine(library).synthesize(_progressive_request(ids, budget=5))

    assert result.candidate is None
    assert result.receipt.candidates_considered == 5
    assert result.receipt.abstention_reason == "generation_budget_exhausted"


def test_complete_depth_two_frontier_ranks_deterministically() -> None:
    library, sources = _search_library()
    engine = CandidateSynthesisEngine(library)
    ordered = _ordered_sources(sources)
    expected_candidates = [
        _composition_candidate(engine, pair)
        for pair in itertools.permutations(ordered, 2)
    ]
    expected = min(expected_candidates, key=_score)

    result = engine.synthesize(
        _progressive_request(tuple(row.abstraction_id for row in reversed(sources)), budget=6)
    )

    assert result.candidate is not None
    assert result.candidate.candidate_id == expected.candidate_id
    assert result.receipt.candidates_considered == math.perm(3, 2)
    assert result.receipt.abstention_reason is None


def test_installed_depth_two_frontier_allows_standalone_depth_three_candidate() -> None:
    base, sources = _search_library()
    base_engine = CandidateSynthesisEngine(base)
    pairs = _generated_at_depth(base_engine, sources, 2)
    populated = CognitiveLibrary(abstractions=(*sources, *pairs))
    before = populated.digest

    depth_three_oracle = [
        _composition_candidate(base_engine, hypothesis)
        for hypothesis in itertools.permutations(_ordered_sources(sources), 3)
    ]
    expected = min(depth_three_oracle, key=_score)

    result = CandidateSynthesisEngine(populated).synthesize(
        _progressive_request(tuple(row.abstraction_id for row in sources), budget=12)
    )

    assert result.candidate is not None
    assert result.candidate.candidate_id == expected.candidate_id
    assert result.receipt.candidates_considered == 12
    payload = result.candidate.payload()
    assert isinstance(payload, LearnedAbstraction)
    assert payload.parameter_count == 1
    assert len(payload.support_task_ids) == 3
    assert "call" not in repr(payload.template.to_data())
    assert populated.digest == before
    for pair in pairs:
        assert populated.vocabulary.get(pair.abstraction_id) == pair


def test_budget_never_descends_through_or_returns_from_partial_frontier() -> None:
    base, sources = _search_library()
    pairs = _generated_at_depth(CandidateSynthesisEngine(base), sources, 2)
    populated = CognitiveLibrary(abstractions=(*sources, *pairs))
    ids = tuple(row.abstraction_id for row in sources)
    engine = CandidateSynthesisEngine(populated)

    for budget in (5, 6, 11):
        result = engine.synthesize(_progressive_request(ids, budget=budget))
        assert result.candidate is None
        assert result.receipt.candidates_considered == budget
        assert result.receipt.abstention_reason == "generation_budget_exhausted"


def test_truncated_depth_three_frontier_is_pool_order_identity_invariant() -> None:
    base, sources = _search_library()
    pairs = _generated_at_depth(CandidateSynthesisEngine(base), sources, 2)
    populated = CognitiveLibrary(abstractions=(*sources, *pairs))
    ids = tuple(row.abstraction_id for row in sources)
    engine = CandidateSynthesisEngine(populated)

    forward = engine.synthesize(_progressive_request(ids, budget=11))
    reverse = engine.synthesize(_progressive_request(tuple(reversed(ids)), budget=11))

    assert forward.candidate is None and reverse.candidate is None
    assert forward.receipt.candidates_considered == 11
    assert reverse.receipt.candidates_considered == 11
    assert forward.receipt.abstention_reason == "generation_budget_exhausted"
    assert reverse.receipt.abstention_reason == "generation_budget_exhausted"
    assert forward.receipt.synthesis_id == reverse.receipt.synthesis_id


def test_full_multi_depth_exhaustion_has_distinct_no_novel_reason_and_no_reuse() -> None:
    base, sources = _search_library()
    engine = CandidateSynthesisEngine(base)
    pairs = _generated_at_depth(engine, sources, 2)
    triples = _generated_at_depth(engine, sources, 3)
    populated = CognitiveLibrary(abstractions=(*sources, *pairs, *triples))
    ids = tuple(row.abstraction_id for row in sources)
    total_without_reuse = sum(math.perm(3, depth) for depth in range(2, 4))
    assert total_without_reuse == 12

    result = CandidateSynthesisEngine(populated).synthesize(
        _progressive_request(ids, budget=100)
    )

    assert result.candidate is None
    assert result.receipt.candidates_considered == total_without_reuse
    assert result.receipt.abstention_reason == "no_novel_candidate"


def test_progressive_fails_closed_on_generated_identity_collision() -> None:
    library, sources = _search_library()
    engine = CandidateSynthesisEngine(library)
    first_pair = next(iter(itertools.permutations(_ordered_sources(sources), 2)))
    generated = _composition_candidate(engine, first_pair).payload()
    assert isinstance(generated, LearnedAbstraction)

    forged = LearnedAbstraction(
        abstraction_id=generated.abstraction_id,
        parameter_count=generated.parameter_count,
        template=generated.template,
        support_task_ids=("task.forged",),
        raw_occurrence_cost=generated.raw_occurrence_cost + 1,
        rewritten_cost=generated.rewritten_cost,
    )
    library.vocabulary._items[generated.abstraction_id] = forged

    ids = tuple(row.abstraction_id for row in sources)
    with pytest.raises(ValueError, match="collides with different library payload"):
        CandidateSynthesisEngine(library).synthesize(_progressive_request(ids, budget=6))


def test_zero_budget_progressive_search_performs_no_generation() -> None:
    library, sources = _search_library()
    ids = tuple(row.abstraction_id for row in sources)

    result = CandidateSynthesisEngine(library).synthesize(_progressive_request(ids, budget=0))

    assert result.candidate is None
    assert result.receipt.candidates_considered == 0
    assert result.receipt.abstention_reason == "generation_budget_exhausted"


def test_progressive_rejects_challenge_and_final_assurance_evidence() -> None:
    _, sources = _search_library()
    ids = tuple(row.abstraction_id for row in sources)

    for forbidden in (EvidencePhase.INDEPENDENT_CHALLENGE, EvidencePhase.FINAL_ASSURANCE):
        with pytest.raises(ValueError, match="discovery"):
            _progressive_request(ids, budget=6, evidence_phase=forbidden)


def test_progressive_has_no_library_or_acquisition_authority() -> None:
    library, sources = _search_library()
    governor = CapabilityAcquisitionGovernor(library)
    library_before = library.digest
    governor_before = governor.digest
    ids = tuple(row.abstraction_id for row in sources)

    result = CandidateSynthesisEngine(library).synthesize(_progressive_request(ids, budget=6))

    assert result.candidate is not None
    assert library.digest == library_before
    assert governor.digest == governor_before
    assert governor.records() == ()

    admitted = governor.admit(result.candidate)
    assert admitted.state is CapabilityState.CANDIDATE
    assert governor.record(result.candidate.candidate_id).state is CapabilityState.CANDIDATE
    assert library.digest == library_before


def test_progressive_receipt_round_trip_tamper_rejection_and_pool_identity() -> None:
    library, sources = _search_library()
    ids = tuple(row.abstraction_id for row in sources)
    engine = CandidateSynthesisEngine(library)

    forward = engine.synthesize(_progressive_request(ids, budget=6))
    reverse = engine.synthesize(_progressive_request(tuple(reversed(ids)), budget=6))

    assert forward.candidate is not None and reverse.candidate is not None
    assert forward.candidate.candidate_id == reverse.candidate.candidate_id
    assert forward.receipt.synthesis_id == reverse.receipt.synthesis_id
    assert SynthesisReceipt.from_state(forward.receipt.to_state()) == forward.receipt

    tampered = forward.receipt.to_state()
    tampered["candidates_considered"] = 5
    with pytest.raises(ValueError, match="identity"):
        SynthesisReceipt.from_state(tampered)
