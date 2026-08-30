from __future__ import annotations

import importlib.util

import pytest

from nolane.external_core.capability_acquisition import (
    CapabilityAcquisitionGovernor,
    CapabilityCandidate,
    CapabilityState,
)
from nolane.external_core.cognitive_library import CognitiveLibrary
from nolane.external_core.cognitive_operators import Binary, Const, Field, Unary
from nolane.external_core.cognitive_vocabulary import LearnedAbstraction, TemplateParam, make_abstraction
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
            STRUCTURAL_SCHEMA_VERSION,
            CandidateSynthesisEngine,
            EvidencePhase,
            EvidenceRef,
            StructuralCall,
            StructuralInput,
            StructuralSynthesisReceipt,
            StructuralSynthesisRequest,
            StructuralSynthesisResult,
            SynthesisMode,
            SynthesisRequest,
        )
    except ImportError as exc:
        pytest.fail(f"production structural candidate-synthesis API is missing: {exc}")
    return (
        STRUCTURAL_SCHEMA_VERSION,
        CandidateSynthesisEngine,
        EvidencePhase,
        EvidenceRef,
        StructuralCall,
        StructuralInput,
        StructuralSynthesisReceipt,
        StructuralSynthesisRequest,
        StructuralSynthesisResult,
        SynthesisMode,
        SynthesisRequest,
    )


def _unary(op: str, task_id: str) -> LearnedAbstraction:
    template = Unary(op, TemplateParam(0))
    return make_abstraction(
        template,
        parameter_count=1,
        support_task_ids=(task_id,),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _binary(op: str, task_id: str) -> LearnedAbstraction:
    template = Binary(op, TemplateParam(0), TemplateParam(1))
    return make_abstraction(
        template,
        parameter_count=2,
        support_task_ids=(task_id,),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _nullary(value: int, task_id: str) -> LearnedAbstraction:
    template = Const(value)
    return make_abstraction(
        template,
        parameter_count=0,
        support_task_ids=(task_id,),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _first(task_id: str = "task.first") -> LearnedAbstraction:
    template = TemplateParam(0)
    return make_abstraction(
        template,
        parameter_count=2,
        support_task_ids=(task_id,),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _doubling(task_id: str = "task.double") -> LearnedAbstraction:
    template = Binary("add", TemplateParam(0), TemplateParam(0))
    return make_abstraction(
        template,
        parameter_count=1,
        support_task_ids=(task_id,),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _library():
    abs_ = _unary("abs", "task.abs")
    neg = _unary("neg", "task.neg")
    add = _binary("add", "task.add")
    max_ = _binary("max", "task.max")
    return CognitiveLibrary(abstractions=(abs_, neg, add, max_)), abs_, neg, add, max_


def _request(program, *, budget: int = 1, reverse_provenance: bool = False):
    (
        _,
        _,
        EvidencePhase,
        EvidenceRef,
        _,
        _,
        _,
        StructuralSynthesisRequest,
        _,
        _,
        _,
    ) = _api()
    evidence = (
        EvidenceRef("evidence.structural.beta", EvidencePhase.DISCOVERY),
        EvidenceRef("evidence.structural.alpha", EvidencePhase.DISCOVERY),
    )
    experiments = ("experiment.structural.beta", "experiment.structural.alpha")
    causal = ("causal.structural.beta", "causal.structural.alpha")
    if reverse_provenance:
        evidence = tuple(reversed(evidence))
        experiments = tuple(reversed(experiments))
        causal = tuple(reversed(causal))
    return StructuralSynthesisRequest(
        program=program,
        objective="compose a canonical structural capability",
        evidence=evidence,
        experiment_receipt_ids=experiments,
        causal_program_ids=causal,
        generation_budget=budget,
    )


def _binary_program(abs_id: str, neg_id: str, add_id: str):
    _, _, _, _, StructuralCall, StructuralInput, *_ = _api()
    return StructuralCall(
        add_id,
        (
            StructuralCall(abs_id, (StructuralInput(0),)),
            StructuralCall(neg_id, (StructuralInput(1),)),
        ),
    )


def test_component_advances_to_v004_with_separate_structural_v2_protocol() -> None:
    STRUCTURAL_SCHEMA_VERSION, *_ = _api()
    assert importlib.util.find_spec(CANONICAL_MODULE) is not None
    assert STRUCTURAL_SCHEMA_VERSION == "candidate-synthesis-v2"

    manifests = {row.component_id: row for row in build_component_manifests()}
    manifest = manifests[COMPONENT_ID]
    assert str(manifest.version) == "0.0.4"
    assert manifest.state_schema == "candidate-synthesis-v1"

    record = build_component_implementation_ledger()[COMPONENT_ID]
    assert record.status is ImplementationStatus.CANONICAL_NATIVE
    assert record.component_version == "0.0.4"
    assert record.canonical_module == CANONICAL_MODULE


def test_structural_request_round_trip_derives_sources_and_normalizes_provenance() -> None:
    _, _, _, _, _, _, _, StructuralSynthesisRequest, *_ = _api()
    _, abs_, neg, add, _ = _library()
    program = _binary_program(abs_.abstraction_id, neg.abstraction_id, add.abstraction_id)

    first = _request(program)
    second = _request(program, reverse_provenance=True)

    assert first == second
    assert first.source_item_ids == tuple(
        sorted((abs_.abstraction_id, neg.abstraction_id, add.abstraction_id))
    )
    state = first.to_state()
    assert state["schema_version"] == "candidate-synthesis-v2"
    assert StructuralSynthesisRequest.from_state(state) == first

    tampered = dict(state)
    tampered["source_item_ids"] = ["abs.forged"]
    with pytest.raises(ValueError, match="source"):
        StructuralSynthesisRequest.from_state(tampered)


def test_legacy_v1_request_rejects_structural_mode() -> None:
    *_, SynthesisMode, SynthesisRequest = _api()
    with pytest.raises(ValueError, match="structural|v2"):
        SynthesisRequest(
            mode=SynthesisMode.STRUCTURAL_COMPOSITION_PROGRAM,
            objective="must use v2",
            source_item_ids=("abs.a", "abs.b"),
            evidence=(),
            experiment_receipt_ids=(),
            causal_program_ids=(),
            generation_budget=1,
        )


def test_binary_structural_program_emits_two_parameter_standalone_candidate() -> None:
    _, CandidateSynthesisEngine, _, _, _, _, _, _, StructuralSynthesisResult, *_ = _api()
    library, abs_, neg, add, _ = _library()
    before = library.digest
    request = _request(_binary_program(abs_.abstraction_id, neg.abstraction_id, add.abstraction_id))

    result = CandidateSynthesisEngine(library).synthesize(request)

    assert isinstance(result, StructuralSynthesisResult)
    assert isinstance(result.candidate, CapabilityCandidate)
    payload = result.candidate.payload()
    assert isinstance(payload, LearnedAbstraction)
    assert payload.parameter_count == 2
    assert payload.template.to_data() == {
        "op": "add",
        "left": {"op": "abs", "arg": {"param": 0}},
        "right": {"op": "neg", "arg": {"param": 1}},
    }
    assert payload.support_task_ids == ("task.abs", "task.add", "task.neg")
    assert "call" not in repr(payload.template.to_data())
    assert result.receipt.candidates_considered == 1
    assert result.receipt.candidate_id == result.candidate.candidate_id
    assert library.digest == before


def test_nested_three_input_program_preserves_semantic_child_order() -> None:
    _, CandidateSynthesisEngine, _, _, StructuralCall, StructuralInput, *_ = _api()
    library, abs_, neg, add, max_ = _library()
    program = StructuralCall(
        max_.abstraction_id,
        (
            StructuralCall(
                add.abstraction_id,
                (
                    StructuralCall(abs_.abstraction_id, (StructuralInput(0),)),
                    StructuralCall(neg.abstraction_id, (StructuralInput(1),)),
                ),
            ),
            StructuralCall(abs_.abstraction_id, (StructuralInput(2),)),
        ),
    )

    result = CandidateSynthesisEngine(library).synthesize(_request(program))
    assert result.candidate is not None
    payload = result.candidate.payload()
    assert isinstance(payload, LearnedAbstraction)
    assert payload.parameter_count == 3
    assert payload.template.to_data() == {
        "op": "max",
        "left": {
            "op": "add",
            "left": {"op": "abs", "arg": {"param": 0}},
            "right": {"op": "neg", "arg": {"param": 1}},
        },
        "right": {"op": "abs", "arg": {"param": 2}},
    }


def test_repeated_source_and_repeated_input_are_valid() -> None:
    _, CandidateSynthesisEngine, _, _, StructuralCall, StructuralInput, *_ = _api()
    library, abs_, _, add, _ = _library()
    program = StructuralCall(
        add.abstraction_id,
        (
            StructuralCall(abs_.abstraction_id, (StructuralInput(0),)),
            StructuralCall(abs_.abstraction_id, (StructuralInput(0),)),
        ),
    )

    result = CandidateSynthesisEngine(library).synthesize(_request(program))
    assert result.candidate is not None
    payload = result.candidate.payload()
    assert isinstance(payload, LearnedAbstraction)
    assert payload.parameter_count == 1
    assert payload.support_task_ids == ("task.abs", "task.add")


def test_nullary_tree_can_emit_novel_zero_parameter_candidate() -> None:
    _, CandidateSynthesisEngine, _, _, StructuralCall, *_ = _api()
    add = _binary("add", "task.add")
    two = _nullary(2, "task.two")
    three = _nullary(3, "task.three")
    library = CognitiveLibrary(abstractions=(add, two, three))
    program = StructuralCall(
        add.abstraction_id,
        (StructuralCall(two.abstraction_id, ()), StructuralCall(three.abstraction_id, ())),
    )

    result = CandidateSynthesisEngine(library).synthesize(_request(program))
    assert result.candidate is not None
    payload = result.candidate.payload()
    assert isinstance(payload, LearnedAbstraction)
    assert payload.parameter_count == 0
    assert payload.template.to_data() == {
        "op": "add",
        "left": {"const": 2},
        "right": {"const": 3},
    }


def test_static_protocol_rejects_input_only_non_contiguous_bool_and_malformed_state() -> None:
    _, _, _, _, StructuralCall, StructuralInput, _, StructuralSynthesisRequest, *_ = _api()
    _, _, _, add, _ = _library()

    with pytest.raises(ValueError, match="call"):
        _request(StructuralInput(0))
    with pytest.raises((TypeError, ValueError), match="index|integer"):
        StructuralInput(True)
    with pytest.raises(ValueError, match="contiguous"):
        _request(StructuralCall(add.abstraction_id, (StructuralInput(0), StructuralInput(2))))

    valid = _request(StructuralCall(add.abstraction_id, (StructuralInput(0), StructuralInput(1))))
    state = valid.to_state()
    malformed = dict(state)
    malformed["program"] = {"input": 0, "extra": 1}
    with pytest.raises(ValueError, match="canonical|structural"):
        StructuralSynthesisRequest.from_state(malformed)


def test_structural_node_and_depth_bounds_are_static_protocol_errors() -> None:
    _, _, _, _, StructuralCall, StructuralInput, *_ = _api()
    unary_id = "abs.synthetic.unary"
    binary_id = "abs.synthetic.binary"

    deep = StructuralInput(0)
    for _ in range(65):
        deep = StructuralCall(unary_id, (deep,))
    with pytest.raises(ValueError, match="depth"):
        _request(deep)

    level = [StructuralInput(0) for _ in range(256)]
    while len(level) > 1:
        next_level = []
        for index in range(0, len(level), 2):
            next_level.append(StructuralCall(binary_id, (level[index], level[index + 1])))
        level = next_level
    with pytest.raises(ValueError, match="node"):
        _request(level[0])


def test_missing_source_and_arity_mismatch_abstain_after_one_attempt() -> None:
    _, CandidateSynthesisEngine, _, _, StructuralCall, StructuralInput, *_ = _api()
    library, _, _, add, _ = _library()

    missing = CandidateSynthesisEngine(library).synthesize(
        _request(StructuralCall("abs.missing", (StructuralInput(0),)))
    )
    assert missing.candidate is None
    assert missing.receipt.candidates_considered == 1
    assert missing.receipt.abstention_reason == "source_not_found:abs.missing"

    mismatch = CandidateSynthesisEngine(library).synthesize(
        _request(StructuralCall(add.abstraction_id, (StructuralInput(0),)))
    )
    assert mismatch.candidate is None
    assert mismatch.receipt.candidates_considered == 1
    assert mismatch.receipt.abstention_reason == f"source_arity_mismatch:{add.abstraction_id}"


def test_reserved_field_collision_abstains_without_mutation() -> None:
    _, CandidateSynthesisEngine, _, _, StructuralCall, StructuralInput, *_ = _api()
    template = Field("__nolane_candidate_synthesis_param_999__")
    poisoned = make_abstraction(
        template,
        parameter_count=1,
        support_task_ids=("task.poisoned",),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )
    library = CognitiveLibrary(abstractions=(poisoned,))
    before = library.digest

    result = CandidateSynthesisEngine(library).synthesize(
        _request(StructuralCall(poisoned.abstraction_id, (StructuralInput(0),)))
    )
    assert result.candidate is None
    assert result.receipt.abstention_reason == f"reserved_field_collision:{poisoned.abstraction_id}"
    assert result.receipt.candidates_considered == 1
    assert library.digest == before


def test_zero_budget_considers_zero_and_positive_budget_attempts_exactly_once() -> None:
    _, CandidateSynthesisEngine, _, _, _, _, *_ = _api()
    library, abs_, neg, add, _ = _library()
    program = _binary_program(abs_.abstraction_id, neg.abstraction_id, add.abstraction_id)

    zero = CandidateSynthesisEngine(library).synthesize(_request(program, budget=0))
    assert zero.candidate is None
    assert zero.receipt.candidates_considered == 0
    assert zero.receipt.abstention_reason == "generation_budget_exhausted"

    many = CandidateSynthesisEngine(library).synthesize(_request(program, budget=99))
    assert many.candidate is not None
    assert many.receipt.candidates_considered == 1
    assert many.receipt.generation_budget == 99


def test_candidate_matching_source_and_exact_installed_candidate_abstain() -> None:
    _, CandidateSynthesisEngine, _, _, StructuralCall, StructuralInput, *_ = _api()
    library, abs_, neg, add, max_ = _library()

    matches = CandidateSynthesisEngine(library).synthesize(
        _request(StructuralCall(abs_.abstraction_id, (StructuralInput(0),)))
    )
    assert matches.candidate is None
    assert matches.receipt.abstention_reason == "candidate_matches_source"

    program = _binary_program(abs_.abstraction_id, neg.abstraction_id, add.abstraction_id)
    first = CandidateSynthesisEngine(library).synthesize(_request(program))
    assert first.candidate is not None
    payload = first.candidate.payload()
    assert isinstance(payload, LearnedAbstraction)
    populated = CognitiveLibrary(abstractions=(abs_, neg, add, max_, payload))

    duplicate = CandidateSynthesisEngine(populated).synthesize(_request(program))
    assert duplicate.candidate is None
    assert duplicate.receipt.abstention_reason == "candidate_already_in_library"
    assert duplicate.receipt.candidates_considered == 1


def test_generated_identity_collision_fails_closed() -> None:
    _, CandidateSynthesisEngine, _, _, *_ = _api()
    library, abs_, neg, add, _ = _library()
    program = _binary_program(abs_.abstraction_id, neg.abstraction_id, add.abstraction_id)
    first = CandidateSynthesisEngine(library).synthesize(_request(program))
    assert first.candidate is not None
    generated = first.candidate.payload()
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

    with pytest.raises(ValueError, match="collides with different library payload"):
        CandidateSynthesisEngine(library).synthesize(_request(program))


def test_expansion_budget_failure_is_fail_closed_and_non_mutating() -> None:
    _, CandidateSynthesisEngine, _, _, StructuralCall, StructuralInput, *_ = _api()
    doubling = _doubling()
    library = CognitiveLibrary(abstractions=(doubling,))
    before = library.digest
    program = StructuralInput(0)
    for _ in range(14):
        program = StructuralCall(doubling.abstraction_id, (program,))

    with pytest.raises(ValueError, match="expansion node budget exceeded"):
        CandidateSynthesisEngine(library).synthesize(_request(program))
    assert library.digest == before


def test_structural_receipt_round_trip_and_wiring_tampering_rejected() -> None:
    _, CandidateSynthesisEngine, _, _, StructuralCall, StructuralInput, StructuralSynthesisReceipt, *_ = _api()
    library, abs_, neg, add, _ = _library()
    program = _binary_program(abs_.abstraction_id, neg.abstraction_id, add.abstraction_id)
    result = CandidateSynthesisEngine(library).synthesize(_request(program))
    assert result.candidate is not None
    assert StructuralSynthesisReceipt.from_state(result.receipt.to_state()) == result.receipt

    tampered = result.receipt.to_state()
    tampered["program"] = StructuralCall(
        add.abstraction_id,
        (
            StructuralCall(neg.abstraction_id, (StructuralInput(1),)),
            StructuralCall(abs_.abstraction_id, (StructuralInput(0),)),
        ),
    ).to_state()
    with pytest.raises(ValueError, match="identity|canonical|source"):
        StructuralSynthesisReceipt.from_state(tampered)


def test_same_source_set_different_wiring_has_distinct_synthesis_identity() -> None:
    _, CandidateSynthesisEngine, _, _, StructuralCall, StructuralInput, *_ = _api()
    library, abs_, neg, add, _ = _library()
    first_program = _binary_program(abs_.abstraction_id, neg.abstraction_id, add.abstraction_id)
    second_program = StructuralCall(
        add.abstraction_id,
        (
            StructuralCall(neg.abstraction_id, (StructuralInput(1),)),
            StructuralCall(abs_.abstraction_id, (StructuralInput(0),)),
        ),
    )
    engine = CandidateSynthesisEngine(library)
    first = engine.synthesize(_request(first_program))
    second = engine.synthesize(_request(second_program))

    assert first.receipt.source_item_ids == second.receipt.source_item_ids
    assert first.receipt.synthesis_id != second.receipt.synthesis_id


def test_distinct_program_provenance_can_share_candidate_identity() -> None:
    _, CandidateSynthesisEngine, _, _, StructuralCall, StructuralInput, *_ = _api()
    first = _first()
    abs_ = _unary("abs", "task.abs")
    neg = _unary("neg", "task.neg")
    add = _binary("add", "task.add")
    library = CognitiveLibrary(abstractions=(first, abs_, neg, add))

    fixed_head = StructuralCall(abs_.abstraction_id, (StructuralInput(0),))
    program_a = StructuralCall(
        first.abstraction_id,
        (
            fixed_head,
            StructuralCall(
                add.abstraction_id,
                (
                    StructuralCall(abs_.abstraction_id, (StructuralInput(1),)),
                    StructuralCall(neg.abstraction_id, (StructuralInput(1),)),
                ),
            ),
        ),
    )
    program_b = StructuralCall(
        first.abstraction_id,
        (
            fixed_head,
            StructuralCall(
                add.abstraction_id,
                (
                    StructuralCall(neg.abstraction_id, (StructuralInput(1),)),
                    StructuralCall(abs_.abstraction_id, (StructuralInput(1),)),
                ),
            ),
        ),
    )

    engine = CandidateSynthesisEngine(library)
    result_a = engine.synthesize(_request(program_a))
    result_b = engine.synthesize(_request(program_b))
    assert result_a.candidate is not None and result_b.candidate is not None
    assert result_a.candidate.candidate_id == result_b.candidate.candidate_id
    assert result_a.receipt.synthesis_id != result_b.receipt.synthesis_id


def test_structural_synthesis_has_no_acquisition_authority() -> None:
    _, CandidateSynthesisEngine, _, _, *_ = _api()
    library, abs_, neg, add, _ = _library()
    governor = CapabilityAcquisitionGovernor(library)
    library_before = library.digest
    governor_before = governor.digest
    program = _binary_program(abs_.abstraction_id, neg.abstraction_id, add.abstraction_id)

    result = CandidateSynthesisEngine(library).synthesize(_request(program))
    assert result.candidate is not None
    assert library.digest == library_before
    assert governor.digest == governor_before
    assert governor.records() == ()

    admitted = governor.admit(result.candidate)
    assert admitted.state is CapabilityState.CANDIDATE
    assert governor.record(result.candidate.candidate_id).state is CapabilityState.CANDIDATE
    assert library.digest == library_before


def test_structural_request_rejects_challenge_and_final_assurance_evidence() -> None:
    _, _, EvidencePhase, EvidenceRef, StructuralCall, StructuralInput, _, StructuralSynthesisRequest, *_ = _api()
    _, abs_, _, _, _ = _library()
    program = StructuralCall(abs_.abstraction_id, (StructuralInput(0),))

    for forbidden in (EvidencePhase.INDEPENDENT_CHALLENGE, EvidencePhase.FINAL_ASSURANCE):
        with pytest.raises(ValueError, match="discovery"):
            StructuralSynthesisRequest(
                program=program,
                objective="forbidden evidence leakage",
                evidence=(EvidenceRef("evidence.forbidden", forbidden),),
                experiment_receipt_ids=(),
                causal_program_ids=(),
                generation_budget=1,
            )
