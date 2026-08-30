from __future__ import annotations

from dataclasses import replace

import pytest

from nolane.external_core.candidate_synthesis import (
    CandidateSynthesisEngine,
    StructuralCall,
    StructuralInput,
    StructuralSynthesisReceipt,
    StructuralSynthesisRequest,
)
from nolane.external_core.cognitive_library import CognitiveLibrary
from nolane.external_core.cognitive_operators import Unary
from nolane.external_core.cognitive_vocabulary import TemplateParam, make_abstraction


def _unary_source():
    template = Unary("abs", TemplateParam(0))
    return make_abstraction(
        template,
        parameter_count=1,
        support_task_ids=("task.abs",),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _request(program, *, budget: int = 1) -> StructuralSynthesisRequest:
    return StructuralSynthesisRequest(
        program=program,
        objective="harden canonical structural protocol",
        evidence=(),
        experiment_receipt_ids=(),
        causal_program_ids=(),
        generation_budget=budget,
    )


def test_structural_request_restore_rejects_boolean_budget() -> None:
    source = _unary_source()
    request = _request(StructuralCall(source.abstraction_id, (StructuralInput(0),)))
    state = request.to_state()
    state["generation_budget"] = True

    with pytest.raises(TypeError, match="budget|integer"):
        StructuralSynthesisRequest.from_state(state)


@pytest.mark.parametrize("non_integer", ("1", 1.5))
def test_structural_request_constructor_rejects_non_integer_budget(non_integer: object) -> None:
    source = _unary_source()
    program = StructuralCall(source.abstraction_id, (StructuralInput(0),))

    with pytest.raises(TypeError, match="budget|integer"):
        _request(program, budget=non_integer)  # type: ignore[arg-type]


def test_structural_receipt_restore_rejects_boolean_budget_accounting() -> None:
    source = _unary_source()
    library = CognitiveLibrary(abstractions=(source,))
    request = _request(StructuralCall(source.abstraction_id, (StructuralInput(0),)))
    result = CandidateSynthesisEngine(library).synthesize(request)
    assert result.candidate is None
    assert result.receipt.abstention_reason == "candidate_matches_source"

    budget_state = result.receipt.to_state()
    budget_state["generation_budget"] = True
    with pytest.raises(TypeError, match="budget|integer"):
        StructuralSynthesisReceipt.from_state(budget_state)

    considered_state = result.receipt.to_state()
    considered_state["candidates_considered"] = True
    with pytest.raises(TypeError, match="budget|integer|considered"):
        StructuralSynthesisReceipt.from_state(considered_state)


@pytest.mark.parametrize("field_name", ("generation_budget", "candidates_considered"))
@pytest.mark.parametrize("non_integer", ("1", 1.5))
def test_structural_receipt_constructor_rejects_non_integer_budget_accounting(
    field_name: str,
    non_integer: object,
) -> None:
    source = _unary_source()
    library = CognitiveLibrary(abstractions=(source,))
    request = _request(StructuralCall(source.abstraction_id, (StructuralInput(0),)))
    result = CandidateSynthesisEngine(library).synthesize(request)
    assert result.candidate is None

    with pytest.raises(TypeError, match="budget|integer|considered"):
        replace(result.receipt, **{field_name: non_integer})


def test_structural_depth_limit_accepts_exact_64_and_rejects_65() -> None:
    program = StructuralInput(0)
    for _ in range(63):
        program = StructuralCall("abs.synthetic.unary", (program,))
    accepted = _request(program)
    assert accepted.parameter_count == 1

    too_deep = StructuralCall("abs.synthetic.unary", (program,))
    with pytest.raises(ValueError, match="depth"):
        _request(too_deep)


def test_structural_node_limit_accepts_exact_256_and_rejects_257() -> None:
    accepted_program = StructuralCall(
        "abs.synthetic.wide",
        tuple(StructuralInput(0) for _ in range(255)),
    )
    accepted = _request(accepted_program)
    assert accepted.parameter_count == 1

    too_wide = StructuralCall(
        "abs.synthetic.wide",
        tuple(StructuralInput(0) for _ in range(256)),
    )
    with pytest.raises(ValueError, match="node"):
        _request(too_wide)
