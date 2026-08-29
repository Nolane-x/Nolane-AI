from __future__ import annotations

import importlib.util

import pytest

from nolane.external_core.capability_acquisition import (
    CapabilityAcquisitionGovernor,
    CapabilityCandidate,
    CapabilityState,
)
from nolane.external_core.cognitive_library import CognitiveLibrary
from nolane.external_core.cognitive_operators import Binary, Unary
from nolane.external_core.cognitive_vocabulary import (
    AbstractionCall,
    LearnedAbstraction,
    TemplateParam,
    evaluate_with_vocabulary,
    make_abstraction,
)
from nolane.metadata.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.metadata.manifests import build_component_manifests


COMPONENT_ID = "external.candidate_synthesis"
CANONICAL_MODULE = "nolane.external_core.candidate_synthesis"


def _api():
    try:
        from nolane.external_core.candidate_synthesis import (
            CandidateSynthesisEngine,
            EvidencePhase,
            EvidenceRef,
            SynthesisMode,
            SynthesisReceipt,
            SynthesisRequest,
        )
    except ImportError as exc:
        pytest.fail(f"production candidate-synthesis behavior API is missing: {exc}")
    return (
        CandidateSynthesisEngine,
        EvidencePhase,
        EvidenceRef,
        SynthesisMode,
        SynthesisReceipt,
        SynthesisRequest,
    )


def _unary_abstraction(op: str, task_id: str) -> LearnedAbstraction:
    template = Unary(op, TemplateParam(0))
    return make_abstraction(
        template,
        parameter_count=1,
        support_task_ids=(task_id,),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _binary_abstraction() -> LearnedAbstraction:
    template = Binary("add", TemplateParam(0), TemplateParam(1))
    return make_abstraction(
        template,
        parameter_count=2,
        support_task_ids=("task.binary",),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _library() -> tuple[CognitiveLibrary, LearnedAbstraction, LearnedAbstraction]:
    strip = _unary_abstraction("strip", "task.strip")
    upper = _unary_abstraction("upper", "task.upper")
    return CognitiveLibrary(abstractions=(strip, upper)), strip, upper


def _request(source_ids: tuple[str, ...], *, budget: int = 1, reverse_provenance: bool = False):
    _, EvidencePhase, EvidenceRef, SynthesisMode, _, SynthesisRequest = _api()
    evidence = (
        EvidenceRef("evidence.beta", EvidencePhase.DISCOVERY),
        EvidenceRef("evidence.alpha", EvidencePhase.DISCOVERY),
    )
    experiments = ("experiment.beta", "experiment.alpha")
    causal = ("causal.beta", "causal.alpha")
    if reverse_provenance:
        evidence = tuple(reversed(evidence))
        experiments = tuple(reversed(experiments))
        causal = tuple(reversed(causal))
    return SynthesisRequest(
        mode=SynthesisMode.LEARNED_ABSTRACTION_COMPOSITION,
        objective="compose verified text normalization",
        source_item_ids=source_ids,
        evidence=evidence,
        experiment_receipt_ids=experiments,
        causal_program_ids=causal,
        generation_budget=budget,
    )


def test_candidate_synthesis_is_declared_as_native_v003_component() -> None:
    assert importlib.util.find_spec(CANONICAL_MODULE) is not None

    manifests = {row.component_id: row for row in build_component_manifests()}
    assert COMPONENT_ID in manifests
    manifest = manifests[COMPONENT_ID]
    assert str(manifest.version) == "0.0.3"
    assert manifest.layer == "external_core"
    assert manifest.state_schema == "candidate-synthesis-v1"

    ledger = build_component_implementation_ledger()
    record = ledger[COMPONENT_ID]
    assert record.status is ImplementationStatus.CANONICAL_NATIVE
    assert record.component_version == "0.0.3"
    assert record.canonical_module == CANONICAL_MODULE
    assert record.legacy_sources == ()


def test_ordered_unary_composition_generates_standalone_capability_candidate() -> None:
    CandidateSynthesisEngine, *_ = _api()
    library, strip, upper = _library()
    before = library.digest

    result = CandidateSynthesisEngine(library).synthesize(
        _request((strip.abstraction_id, upper.abstraction_id))
    )

    assert isinstance(result.candidate, CapabilityCandidate)
    payload = result.candidate.payload()
    assert isinstance(payload, LearnedAbstraction)
    assert payload.parameter_count == 1
    assert payload.template.to_data() == {
        "op": "upper",
        "arg": {"op": "strip", "arg": {"param": 0}},
    }
    assert "call" not in repr(payload.template.to_data())
    assert payload.support_task_ids == ("task.strip", "task.upper")
    assert result.receipt.candidates_considered == 1
    assert result.receipt.candidate_id == result.candidate.candidate_id
    assert result.receipt.abstention_reason is None
    assert library.digest == before

    verification_library = CognitiveLibrary(abstractions=(strip, upper, payload))
    probe = AbstractionCall(payload.abstraction_id, (Unary("strip", TemplateParam(0)),))
    # Candidate is standalone-decodable; canonical registration requires no hidden dependency.
    assert verification_library.vocabulary.get(payload.abstraction_id) == payload
    assert probe.abstraction_id == payload.abstraction_id


def test_same_semantics_and_set_like_provenance_have_stable_identity() -> None:
    CandidateSynthesisEngine, *_ = _api()
    library, strip, upper = _library()
    engine = CandidateSynthesisEngine(library)

    first = engine.synthesize(_request((strip.abstraction_id, upper.abstraction_id)))
    second = engine.synthesize(
        _request((strip.abstraction_id, upper.abstraction_id), reverse_provenance=True)
    )

    assert first.candidate is not None and second.candidate is not None
    assert first.candidate.candidate_id == second.candidate.candidate_id
    assert first.receipt.synthesis_id == second.receipt.synthesis_id
    assert first.receipt.evidence_ids == ("evidence.alpha", "evidence.beta")
    assert first.receipt.experiment_receipt_ids == ("experiment.alpha", "experiment.beta")
    assert first.receipt.causal_program_ids == ("causal.alpha", "causal.beta")


def test_source_order_is_semantic() -> None:
    CandidateSynthesisEngine, *_ = _api()
    library, strip, upper = _library()
    engine = CandidateSynthesisEngine(library)

    forward = engine.synthesize(_request((strip.abstraction_id, upper.abstraction_id)))
    reverse = engine.synthesize(_request((upper.abstraction_id, strip.abstraction_id)))

    assert forward.candidate is not None and reverse.candidate is not None
    assert forward.candidate.candidate_id != reverse.candidate.candidate_id
    assert forward.receipt.synthesis_id != reverse.receipt.synthesis_id
    assert forward.candidate.payload().template.to_data() != reverse.candidate.payload().template.to_data()


def test_zero_generation_budget_abstains_without_candidate() -> None:
    CandidateSynthesisEngine, *_ = _api()
    library, strip, upper = _library()

    result = CandidateSynthesisEngine(library).synthesize(
        _request((strip.abstraction_id, upper.abstraction_id), budget=0)
    )

    assert result.candidate is None
    assert result.receipt.candidates_considered == 0
    assert result.receipt.candidate_id is None
    assert result.receipt.abstention_reason == "generation_budget_exhausted"


def test_request_rejects_duplicate_sources_and_non_discovery_evidence() -> None:
    _, EvidencePhase, EvidenceRef, SynthesisMode, _, SynthesisRequest = _api()
    _, strip, upper = _library()

    with pytest.raises(ValueError, match="source"):
        SynthesisRequest(
            mode=SynthesisMode.LEARNED_ABSTRACTION_COMPOSITION,
            objective="duplicate",
            source_item_ids=(strip.abstraction_id, strip.abstraction_id),
            evidence=(),
            experiment_receipt_ids=(),
            causal_program_ids=(),
            generation_budget=1,
        )

    for forbidden in (EvidencePhase.INDEPENDENT_CHALLENGE, EvidencePhase.FINAL_ASSURANCE):
        with pytest.raises(ValueError, match="discovery"):
            SynthesisRequest(
                mode=SynthesisMode.LEARNED_ABSTRACTION_COMPOSITION,
                objective="forbidden verification leakage",
                source_item_ids=(strip.abstraction_id, upper.abstraction_id),
                evidence=(EvidenceRef("evidence.forbidden", forbidden),),
                experiment_receipt_ids=(),
                causal_program_ids=(),
                generation_budget=1,
            )


def test_missing_or_non_unary_source_fails_closed_as_abstention() -> None:
    CandidateSynthesisEngine, *_ = _api()
    library, strip, upper = _library()

    missing = CandidateSynthesisEngine(library).synthesize(
        _request((strip.abstraction_id, "abs.missing"))
    )
    assert missing.candidate is None
    assert missing.receipt.abstention_reason == "source_not_found:abs.missing"

    binary = _binary_abstraction()
    mixed = CognitiveLibrary(abstractions=(strip, upper, binary))
    non_unary = CandidateSynthesisEngine(mixed).synthesize(
        _request((strip.abstraction_id, binary.abstraction_id))
    )
    assert non_unary.candidate is None
    assert non_unary.receipt.abstention_reason == f"source_not_unary:{binary.abstraction_id}"


def test_already_installed_generated_abstraction_is_deduplicated() -> None:
    CandidateSynthesisEngine, *_ = _api()
    library, strip, upper = _library()
    request = _request((strip.abstraction_id, upper.abstraction_id))
    first = CandidateSynthesisEngine(library).synthesize(request)
    assert first.candidate is not None
    generated = first.candidate.payload()
    assert isinstance(generated, LearnedAbstraction)

    populated = CognitiveLibrary(abstractions=(strip, upper, generated))
    duplicate = CandidateSynthesisEngine(populated).synthesize(request)

    assert duplicate.candidate is None
    assert duplicate.receipt.candidates_considered == 1
    assert duplicate.receipt.abstention_reason == "candidate_already_in_library"


def test_synthesis_does_not_mutate_acquisition_and_explicit_admit_stays_candidate() -> None:
    CandidateSynthesisEngine, *_ = _api()
    library, strip, upper = _library()
    governor = CapabilityAcquisitionGovernor(library)
    library_before = library.digest
    governor_before = governor.digest

    result = CandidateSynthesisEngine(library).synthesize(
        _request((strip.abstraction_id, upper.abstraction_id))
    )

    assert result.candidate is not None
    assert library.digest == library_before
    assert governor.digest == governor_before
    assert governor.records() == ()

    admitted = governor.admit(result.candidate)
    assert admitted.state is CapabilityState.CANDIDATE
    assert governor.record(result.candidate.candidate_id).state is CapabilityState.CANDIDATE
    assert library.digest == library_before


def test_request_and_receipt_round_trip_and_tampering_fails() -> None:
    CandidateSynthesisEngine, _, _, _, SynthesisReceipt, SynthesisRequest = _api()
    library, strip, upper = _library()
    request = _request((strip.abstraction_id, upper.abstraction_id))
    restored_request = SynthesisRequest.from_state(request.to_state())
    assert restored_request == request

    result = CandidateSynthesisEngine(library).synthesize(request)
    restored_receipt = SynthesisReceipt.from_state(result.receipt.to_state())
    assert restored_receipt == result.receipt

    tampered = result.receipt.to_state()
    tampered["synthesis_id"] = "synthesis:tampered"
    with pytest.raises(ValueError, match="identity"):
        SynthesisReceipt.from_state(tampered)
