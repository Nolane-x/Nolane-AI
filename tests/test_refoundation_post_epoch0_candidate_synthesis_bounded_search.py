from __future__ import annotations

import itertools

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
SEARCH_MODE_NAME = "BOUNDED_LEARNED_ABSTRACTION_SEARCH"


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


def _search_request(
    source_ids: tuple[str, ...],
    *,
    budget: int,
    evidence_phase: EvidencePhase = EvidencePhase.DISCOVERY,
) -> SynthesisRequest:
    mode = getattr(SynthesisMode, SEARCH_MODE_NAME)
    return SynthesisRequest(
        mode=mode,
        objective="search bounded unary compositions",
        source_item_ids=source_ids,
        evidence=(EvidenceRef("evidence.search.discovery", evidence_phase),),
        experiment_receipt_ids=("experiment.search",),
        causal_program_ids=("causal.search",),
        generation_budget=budget,
    )


def _composition_candidate(
    engine: CandidateSynthesisEngine,
    first: LearnedAbstraction,
    second: LearnedAbstraction,
) -> CapabilityCandidate:
    result = engine.synthesize(
        SynthesisRequest(
            mode=SynthesisMode.LEARNED_ABSTRACTION_COMPOSITION,
            objective="derive ranking oracle from existing composition contract",
            source_item_ids=(first.abstraction_id, second.abstraction_id),
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


def test_component_is_v004_while_bounded_search_schema_stays_v1() -> None:
    manifests = {row.component_id: row for row in build_component_manifests()}
    manifest = manifests[COMPONENT_ID]
    assert str(manifest.version) == "0.0.4"
    assert manifest.state_schema == "candidate-synthesis-v1"

    ledger = build_component_implementation_ledger()[COMPONENT_ID]
    assert ledger.component_version == "0.0.4"


def test_search_pool_order_is_canonical_and_identity_invariant() -> None:
    library, sources = _search_library()
    engine = CandidateSynthesisEngine(library)
    ids = tuple(row.abstraction_id for row in sources)

    first_request = _search_request(ids, budget=6)
    second_request = _search_request(tuple(reversed(ids)), budget=6)
    first = engine.synthesize(first_request)
    second = engine.synthesize(second_request)

    assert first_request.source_item_ids == tuple(sorted(ids))
    assert second_request.source_item_ids == first_request.source_item_ids
    assert first.candidate is not None and second.candidate is not None
    assert first.candidate.candidate_id == second.candidate.candidate_id
    assert first.receipt.synthesis_id == second.receipt.synthesis_id
    assert first.receipt.candidates_considered == 6


def test_search_ranks_all_bounded_ordered_pairs_deterministically() -> None:
    library, sources = _search_library()
    engine = CandidateSynthesisEngine(library)
    ids = tuple(row.abstraction_id for row in sources)

    expected_candidates = [
        _composition_candidate(engine, first, second)
        for first, second in itertools.permutations(sorted(sources, key=lambda row: row.abstraction_id), 2)
    ]
    expected = min(expected_candidates, key=_score)

    result = engine.synthesize(_search_request(ids, budget=len(expected_candidates)))

    assert result.candidate is not None
    assert result.candidate.candidate_id == expected.candidate_id
    assert result.receipt.candidates_considered == len(expected_candidates)
    assert result.receipt.candidates_considered <= result.receipt.generation_budget


def test_generation_budget_is_a_hard_hypothesis_cap() -> None:
    library, sources = _search_library()
    engine = CandidateSynthesisEngine(library)
    ids = tuple(row.abstraction_id for row in sources)

    one = engine.synthesize(_search_request(ids, budget=1))
    two = engine.synthesize(_search_request(tuple(reversed(ids)), budget=2))

    assert one.candidate is not None
    assert two.candidate is not None
    assert one.receipt.candidates_considered == 1
    assert two.receipt.candidates_considered == 2
    assert one.receipt.generation_budget == 1
    assert two.receipt.generation_budget == 2


def test_zero_budget_search_abstains_without_generation() -> None:
    library, sources = _search_library()
    ids = tuple(row.abstraction_id for row in sources)

    result = CandidateSynthesisEngine(library).synthesize(_search_request(ids, budget=0))

    assert result.candidate is None
    assert result.receipt.candidates_considered == 0
    assert result.receipt.abstention_reason == "generation_budget_exhausted"


def test_search_rejects_challenge_and_final_assurance_evidence() -> None:
    _, sources = _search_library()
    ids = tuple(row.abstraction_id for row in sources)

    for forbidden in (EvidencePhase.INDEPENDENT_CHALLENGE, EvidencePhase.FINAL_ASSURANCE):
        with pytest.raises(ValueError, match="discovery"):
            _search_request(ids, budget=2, evidence_phase=forbidden)


def test_search_skips_installed_candidates_and_abstains_when_no_novel_candidate_remains() -> None:
    base, sources = _search_library()
    engine = CandidateSynthesisEngine(base)
    ordered = tuple(sorted(sources, key=lambda row: row.abstraction_id))
    generated = tuple(
        _composition_candidate(engine, first, second).payload()
        for first, second in itertools.permutations(ordered, 2)
    )
    assert all(isinstance(row, LearnedAbstraction) for row in generated)

    populated = CognitiveLibrary(abstractions=(*sources, *generated))
    ids = tuple(row.abstraction_id for row in sources)
    result = CandidateSynthesisEngine(populated).synthesize(_search_request(ids, budget=6))

    assert result.candidate is None
    assert result.receipt.candidates_considered == 6
    assert result.receipt.abstention_reason == "no_novel_candidate_within_budget"


def test_search_has_no_library_or_acquisition_authority() -> None:
    library, sources = _search_library()
    governor = CapabilityAcquisitionGovernor(library)
    library_before = library.digest
    governor_before = governor.digest
    ids = tuple(row.abstraction_id for row in sources)

    result = CandidateSynthesisEngine(library).synthesize(_search_request(ids, budget=6))

    assert result.candidate is not None
    assert library.digest == library_before
    assert governor.digest == governor_before
    assert governor.records() == ()

    admitted = governor.admit(result.candidate)
    assert admitted.state is CapabilityState.CANDIDATE
    assert governor.record(result.candidate.candidate_id).state is CapabilityState.CANDIDATE
    assert library.digest == library_before


def test_search_request_receipt_round_trip_and_tamper_rejection() -> None:
    library, sources = _search_library()
    request = _search_request(tuple(row.abstraction_id for row in sources), budget=4)
    assert SynthesisRequest.from_state(request.to_state()) == request

    result = CandidateSynthesisEngine(library).synthesize(request)
    assert SynthesisReceipt.from_state(result.receipt.to_state()) == result.receipt

    tampered = result.receipt.to_state()
    tampered["candidates_considered"] = 0
    with pytest.raises(ValueError, match="identity"):
        SynthesisReceipt.from_state(tampered)
