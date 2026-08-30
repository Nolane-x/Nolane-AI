from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import permutations
from math import perm
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.capability_acquisition import CapabilityCandidate
from nolane.external_core.cognitive_library import CognitiveLibrary
from nolane.external_core.cognitive_operators import Binary, Const, Expr, Field, IfElse, Unary
from nolane.external_core.cognitive_vocabulary import (
    AbstractionCall,
    LearnedAbstraction,
    TemplateParam,
    expand_expr,
    make_abstraction,
)


COMPONENT_ID = "external.candidate_synthesis"
COMPONENT_VERSION = "0.0.4"
SCHEMA_VERSION = "candidate-synthesis-v1"
STRUCTURAL_SCHEMA_VERSION = "candidate-synthesis-v2"
DESIGN_LINEAGE = "post-Epoch-0 native synthesis; R2.56/R2.61/R2.65 are design provenance only"
_PARAM_FIELD = "__nolane_candidate_synthesis_param_0__"
_RESERVED_PARAM_PREFIX = "__nolane_candidate_synthesis_param_"
MAX_STRUCTURAL_NODES = 256
MAX_STRUCTURAL_DEPTH = 64
_MAX_EXPANSION_NODES = 10_000


class SynthesisMode(str, Enum):
    LEARNED_ABSTRACTION_COMPOSITION = "learned_abstraction_composition"
    BOUNDED_LEARNED_ABSTRACTION_SEARCH = "bounded_learned_abstraction_search"
    PROGRESSIVE_MULTI_DEPTH_SEARCH = "progressive_multi_depth_search"
    STRUCTURAL_COMPOSITION_PROGRAM = "structural_composition_program"


class EvidencePhase(str, Enum):
    DISCOVERY = "discovery"
    INDEPENDENT_CHALLENGE = "independent_challenge"
    FINAL_ASSURANCE = "final_assurance"


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _ordered_unique_ids(values: Sequence[object], name: str, *, minimum: int = 0) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence")
    rows = tuple(_nonempty(value, name) for value in values)
    if len(rows) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} values")
    if len(rows) != len(set(rows)):
        raise ValueError(f"{name} must not contain duplicate values")
    return rows


def _sorted_unique_ids(values: Sequence[object], name: str) -> tuple[str, ...]:
    return tuple(sorted(_ordered_unique_ids(values, name)))


def _source_ids_for_mode(
    mode: SynthesisMode,
    values: Sequence[object],
) -> tuple[str, ...]:
    rows = _ordered_unique_ids(values, "source item ids", minimum=2)
    if mode in (
        SynthesisMode.BOUNDED_LEARNED_ABSTRACTION_SEARCH,
        SynthesisMode.PROGRESSIVE_MULTI_DEPTH_SEARCH,
    ):
        return tuple(sorted(rows))
    return rows


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    phase: EvidencePhase

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _nonempty(self.evidence_id, "evidence id"))
        object.__setattr__(self, "phase", EvidencePhase(self.phase))

    def to_state(self) -> dict[str, str]:
        return {"evidence_id": self.evidence_id, "phase": self.phase.value}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "EvidenceRef":
        row = cls(str(state["evidence_id"]), EvidencePhase(str(state["phase"])))
        if row.to_state() != dict(state):
            raise ValueError("non-canonical synthesis evidence reference state")
        return row


@dataclass(frozen=True, slots=True)
class SynthesisRequest:
    mode: SynthesisMode
    objective: str
    source_item_ids: tuple[str, ...]
    evidence: tuple[EvidenceRef, ...] = ()
    experiment_receipt_ids: tuple[str, ...] = ()
    causal_program_ids: tuple[str, ...] = ()
    generation_budget: int = 1

    def __post_init__(self) -> None:
        mode = SynthesisMode(self.mode)
        if mode is SynthesisMode.STRUCTURAL_COMPOSITION_PROGRAM:
            raise ValueError("structural composition requires candidate-synthesis-v2 protocol")
        objective = _nonempty(self.objective, "synthesis objective")
        sources = _source_ids_for_mode(mode, self.source_item_ids)
        evidence = tuple(self.evidence)
        if not all(isinstance(row, EvidenceRef) for row in evidence):
            raise TypeError("synthesis evidence must contain EvidenceRef values")
        evidence_ids = [row.evidence_id for row in evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("synthesis evidence ids must not contain duplicates")
        if any(row.phase is not EvidencePhase.DISCOVERY for row in evidence):
            raise ValueError("candidate synthesis accepts discovery evidence only")
        evidence = tuple(sorted(evidence, key=lambda row: row.evidence_id))
        experiments = _sorted_unique_ids(self.experiment_receipt_ids, "experiment receipt ids")
        causal = _sorted_unique_ids(self.causal_program_ids, "causal program ids")
        if isinstance(self.generation_budget, bool):
            raise TypeError("generation budget must be an integer")
        budget = int(self.generation_budget)
        if budget < 0:
            raise ValueError("generation budget must be non-negative")

        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "objective", objective)
        object.__setattr__(self, "source_item_ids", sources)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "experiment_receipt_ids", experiments)
        object.__setattr__(self, "causal_program_ids", causal)
        object.__setattr__(self, "generation_budget", budget)

    def to_state(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": self.mode.value,
            "objective": self.objective,
            "source_item_ids": list(self.source_item_ids),
            "evidence": [row.to_state() for row in self.evidence],
            "experiment_receipt_ids": list(self.experiment_receipt_ids),
            "causal_program_ids": list(self.causal_program_ids),
            "generation_budget": self.generation_budget,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "SynthesisRequest":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported candidate synthesis request schema")
        raw_evidence = state.get("evidence", ())
        if isinstance(raw_evidence, (str, bytes)) or not isinstance(raw_evidence, Sequence):
            raise TypeError("synthesis evidence state must be a sequence")
        evidence: list[EvidenceRef] = []
        for row in raw_evidence:
            if not isinstance(row, Mapping):
                raise TypeError("synthesis evidence state row must be a mapping")
            evidence.append(EvidenceRef.from_state(row))
        request = cls(
            mode=SynthesisMode(str(state["mode"])),
            objective=str(state["objective"]),
            source_item_ids=tuple(str(value) for value in state.get("source_item_ids", ())),
            evidence=tuple(evidence),
            experiment_receipt_ids=tuple(str(value) for value in state.get("experiment_receipt_ids", ())),
            causal_program_ids=tuple(str(value) for value in state.get("causal_program_ids", ())),
            generation_budget=int(state.get("generation_budget", 0)),
        )
        if request.to_state() != dict(state):
            raise ValueError("non-canonical candidate synthesis request state")
        return request


@dataclass(frozen=True, slots=True)
class SynthesisReceipt:
    mode: SynthesisMode
    objective: str
    source_item_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    experiment_receipt_ids: tuple[str, ...]
    causal_program_ids: tuple[str, ...]
    generation_budget: int
    candidates_considered: int
    candidate_id: str | None
    semantic_fingerprint: str | None
    abstention_reason: str | None
    synthesis_id: str

    def __post_init__(self) -> None:
        mode = SynthesisMode(self.mode)
        if mode is SynthesisMode.STRUCTURAL_COMPOSITION_PROGRAM:
            raise ValueError("structural composition requires candidate-synthesis-v2 protocol")
        objective = _nonempty(self.objective, "synthesis objective")
        sources = _source_ids_for_mode(mode, self.source_item_ids)
        evidence_ids = _sorted_unique_ids(self.evidence_ids, "evidence ids")
        experiments = _sorted_unique_ids(self.experiment_receipt_ids, "experiment receipt ids")
        causal = _sorted_unique_ids(self.causal_program_ids, "causal program ids")
        budget = int(self.generation_budget)
        considered = int(self.candidates_considered)
        if budget < 0 or considered < 0 or considered > budget:
            raise ValueError("candidate synthesis receipt budget accounting is invalid")
        candidate_id = None if self.candidate_id is None else _nonempty(self.candidate_id, "candidate id")
        fingerprint = None if self.semantic_fingerprint is None else _nonempty(self.semantic_fingerprint, "semantic fingerprint")
        reason = None if self.abstention_reason is None else _nonempty(self.abstention_reason, "abstention reason")
        if candidate_id is None:
            if fingerprint is not None or reason is None:
                raise ValueError("abstaining synthesis receipt requires reason and no candidate fingerprint")
        elif fingerprint is None or reason is not None:
            raise ValueError("successful synthesis receipt requires candidate fingerprint and no abstention reason")

        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "objective", objective)
        object.__setattr__(self, "source_item_ids", sources)
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "experiment_receipt_ids", experiments)
        object.__setattr__(self, "causal_program_ids", causal)
        object.__setattr__(self, "generation_budget", budget)
        object.__setattr__(self, "candidates_considered", considered)
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "semantic_fingerprint", fingerprint)
        object.__setattr__(self, "abstention_reason", reason)

        expected = f"synthesis:{canonical_digest(self.semantic_state())}"
        if str(self.synthesis_id) != expected:
            raise ValueError("candidate synthesis receipt identity mismatch")
        object.__setattr__(self, "synthesis_id", expected)

    def semantic_state(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": self.mode.value,
            "objective": self.objective,
            "source_item_ids": list(self.source_item_ids),
            "evidence_ids": list(self.evidence_ids),
            "experiment_receipt_ids": list(self.experiment_receipt_ids),
            "causal_program_ids": list(self.causal_program_ids),
            "generation_budget": self.generation_budget,
            "candidates_considered": self.candidates_considered,
            "candidate_id": self.candidate_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            "abstention_reason": self.abstention_reason,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.semantic_state(), "synthesis_id": self.synthesis_id}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "SynthesisReceipt":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported candidate synthesis receipt schema")
        receipt = cls(
            mode=SynthesisMode(str(state["mode"])),
            objective=str(state["objective"]),
            source_item_ids=tuple(str(value) for value in state.get("source_item_ids", ())),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            experiment_receipt_ids=tuple(str(value) for value in state.get("experiment_receipt_ids", ())),
            causal_program_ids=tuple(str(value) for value in state.get("causal_program_ids", ())),
            generation_budget=int(state["generation_budget"]),
            candidates_considered=int(state["candidates_considered"]),
            candidate_id=None if state.get("candidate_id") is None else str(state["candidate_id"]),
            semantic_fingerprint=None if state.get("semantic_fingerprint") is None else str(state["semantic_fingerprint"]),
            abstention_reason=None if state.get("abstention_reason") is None else str(state["abstention_reason"]),
            synthesis_id=str(state["synthesis_id"]),
        )
        if receipt.to_state() != dict(state):
            raise ValueError("non-canonical candidate synthesis receipt state")
        return receipt


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    candidate: CapabilityCandidate | None
    receipt: SynthesisReceipt

    def __post_init__(self) -> None:
        if self.candidate is not None and not isinstance(self.candidate, CapabilityCandidate):
            raise TypeError("synthesis result candidate must be CapabilityCandidate or None")
        if not isinstance(self.receipt, SynthesisReceipt):
            raise TypeError("synthesis result receipt must be SynthesisReceipt")
        if self.candidate is None:
            if self.receipt.candidate_id is not None:
                raise ValueError("abstaining synthesis result cannot carry candidate identity")
        elif self.receipt.candidate_id != self.candidate.candidate_id:
            raise ValueError("synthesis result candidate/receipt identity mismatch")


def _receipt(
    request: SynthesisRequest,
    *,
    candidates_considered: int,
    candidate: CapabilityCandidate | None = None,
    abstention_reason: str | None = None,
) -> SynthesisReceipt:
    candidate_id = None if candidate is None else candidate.candidate_id
    fingerprint = None if candidate is None else canonical_digest(candidate.semantic_state())
    semantic = {
        "schema_version": SCHEMA_VERSION,
        "mode": request.mode.value,
        "objective": request.objective,
        "source_item_ids": list(request.source_item_ids),
        "evidence_ids": [row.evidence_id for row in request.evidence],
        "experiment_receipt_ids": list(request.experiment_receipt_ids),
        "causal_program_ids": list(request.causal_program_ids),
        "generation_budget": request.generation_budget,
        "candidates_considered": int(candidates_considered),
        "candidate_id": candidate_id,
        "semantic_fingerprint": fingerprint,
        "abstention_reason": abstention_reason,
    }
    return SynthesisReceipt(
        mode=request.mode,
        objective=request.objective,
        source_item_ids=request.source_item_ids,
        evidence_ids=tuple(row.evidence_id for row in request.evidence),
        experiment_receipt_ids=request.experiment_receipt_ids,
        causal_program_ids=request.causal_program_ids,
        generation_budget=request.generation_budget,
        candidates_considered=int(candidates_considered),
        candidate_id=candidate_id,
        semantic_fingerprint=fingerprint,
        abstention_reason=abstention_reason,
        synthesis_id=f"synthesis:{canonical_digest(semantic)}",
    )


@dataclass(frozen=True, slots=True)
class StructuralInput:
    index: int

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise TypeError("structural input index must be an integer")
        if self.index < 0:
            raise ValueError("structural input index must be non-negative")

    def to_state(self) -> dict[str, int]:
        return {"input": self.index}


@dataclass(frozen=True, slots=True)
class StructuralCall:
    source_abstraction_id: str
    args: tuple["StructuralNode", ...]

    def __post_init__(self) -> None:
        source_id = _nonempty(self.source_abstraction_id, "structural call source id")
        if isinstance(self.args, (str, bytes)) or not isinstance(self.args, Sequence):
            raise TypeError("structural call args must be a sequence")
        args = tuple(self.args)
        if not all(isinstance(row, (StructuralInput, StructuralCall)) for row in args):
            raise TypeError("structural call args must contain structural nodes")
        object.__setattr__(self, "source_abstraction_id", source_id)
        object.__setattr__(self, "args", args)

    def to_state(self) -> dict[str, object]:
        return {
            "call": self.source_abstraction_id,
            "args": [row.to_state() for row in self.args],
        }


StructuralNode = StructuralInput | StructuralCall


@dataclass(frozen=True, slots=True)
class _StructuralStats:
    node_count: int
    max_depth: int
    input_indices: tuple[int, ...]
    source_item_ids: tuple[str, ...]
    call_count: int

    @property
    def parameter_count(self) -> int:
        return len(self.input_indices)


def _analyze_structural_program(program: StructuralNode) -> _StructuralStats:
    if not isinstance(program, (StructuralInput, StructuralCall)):
        raise TypeError("structural program must be a structural node")
    nodes = 0
    max_depth = 0
    inputs: set[int] = set()
    sources: set[str] = set()
    calls = 0
    stack: list[tuple[StructuralNode, int]] = [(program, 1)]
    while stack:
        node, depth = stack.pop()
        nodes += 1
        if nodes > MAX_STRUCTURAL_NODES:
            raise ValueError("structural program node limit exceeded")
        if depth > MAX_STRUCTURAL_DEPTH:
            raise ValueError("structural program depth limit exceeded")
        max_depth = max(max_depth, depth)
        if isinstance(node, StructuralInput):
            inputs.add(node.index)
            continue
        calls += 1
        sources.add(node.source_abstraction_id)
        for child in reversed(node.args):
            stack.append((child, depth + 1))
    ordered_inputs = tuple(sorted(inputs))
    if ordered_inputs != tuple(range(len(ordered_inputs))):
        raise ValueError("structural input indices must be contiguous from zero")
    if calls < 1:
        raise ValueError("structural program must contain at least one call node")
    return _StructuralStats(
        node_count=nodes,
        max_depth=max_depth,
        input_indices=ordered_inputs,
        source_item_ids=tuple(sorted(sources)),
        call_count=calls,
    )


def _structural_node_from_state(state: Mapping[str, object], *, _depth: int = 1) -> StructuralNode:
    if not isinstance(state, Mapping):
        raise TypeError("structural node state must be a mapping")
    if _depth > MAX_STRUCTURAL_DEPTH:
        raise ValueError("structural program depth limit exceeded")
    keys = set(state)
    if keys == {"input"}:
        raw_index = state["input"]
        if isinstance(raw_index, bool) or not isinstance(raw_index, int):
            raise TypeError("structural input index must be an integer")
        node: StructuralNode = StructuralInput(raw_index)
    elif keys == {"call", "args"}:
        raw_args = state["args"]
        if isinstance(raw_args, (str, bytes)) or not isinstance(raw_args, Sequence):
            raise TypeError("structural call args state must be a sequence")
        args: list[StructuralNode] = []
        for raw_child in raw_args:
            if not isinstance(raw_child, Mapping):
                raise TypeError("structural child state must be a mapping")
            args.append(_structural_node_from_state(raw_child, _depth=_depth + 1))
        node = StructuralCall(str(state["call"]), tuple(args))
    else:
        raise ValueError("non-canonical structural node state")
    if node.to_state() != dict(state):
        raise ValueError("non-canonical structural node state")
    return node


def _structural_state_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _normalize_structural_evidence(values: Sequence[EvidenceRef]) -> tuple[EvidenceRef, ...]:
    evidence = tuple(values)
    if not all(isinstance(row, EvidenceRef) for row in evidence):
        raise TypeError("synthesis evidence must contain EvidenceRef values")
    evidence_ids = [row.evidence_id for row in evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("synthesis evidence ids must not contain duplicates")
    if any(row.phase is not EvidencePhase.DISCOVERY for row in evidence):
        raise ValueError("candidate synthesis accepts discovery evidence only")
    return tuple(sorted(evidence, key=lambda row: row.evidence_id))


@dataclass(frozen=True, slots=True)
class StructuralSynthesisRequest:
    program: StructuralNode
    objective: str
    evidence: tuple[EvidenceRef, ...] = ()
    experiment_receipt_ids: tuple[str, ...] = ()
    causal_program_ids: tuple[str, ...] = ()
    generation_budget: int = 1
    mode: SynthesisMode = SynthesisMode.STRUCTURAL_COMPOSITION_PROGRAM

    def __post_init__(self) -> None:
        mode = SynthesisMode(self.mode)
        if mode is not SynthesisMode.STRUCTURAL_COMPOSITION_PROGRAM:
            raise ValueError("structural synthesis request requires structural composition mode")
        stats = _analyze_structural_program(self.program)
        objective = _nonempty(self.objective, "synthesis objective")
        evidence = _normalize_structural_evidence(self.evidence)
        experiments = _sorted_unique_ids(self.experiment_receipt_ids, "experiment receipt ids")
        causal = _sorted_unique_ids(self.causal_program_ids, "causal program ids")
        if isinstance(self.generation_budget, bool) or not isinstance(self.generation_budget, int):
            raise TypeError("generation budget must be an integer")
        budget = self.generation_budget
        if budget < 0:
            raise ValueError("generation budget must be non-negative")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "objective", objective)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "experiment_receipt_ids", experiments)
        object.__setattr__(self, "causal_program_ids", causal)
        object.__setattr__(self, "generation_budget", budget)
        # Re-run analysis through the immutable canonical program so invalid
        # trees cannot gain a request identity through caller-provided metadata.
        if stats.source_item_ids != self.source_item_ids:
            raise RuntimeError("structural source derivation is inconsistent")

    @property
    def source_item_ids(self) -> tuple[str, ...]:
        return _analyze_structural_program(self.program).source_item_ids

    @property
    def parameter_count(self) -> int:
        return _analyze_structural_program(self.program).parameter_count

    def to_state(self) -> dict[str, Any]:
        return {
            "schema_version": STRUCTURAL_SCHEMA_VERSION,
            "mode": self.mode.value,
            "objective": self.objective,
            "program": self.program.to_state(),
            "source_item_ids": list(self.source_item_ids),
            "evidence": [row.to_state() for row in self.evidence],
            "experiment_receipt_ids": list(self.experiment_receipt_ids),
            "causal_program_ids": list(self.causal_program_ids),
            "generation_budget": self.generation_budget,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "StructuralSynthesisRequest":
        if str(state.get("schema_version")) != STRUCTURAL_SCHEMA_VERSION:
            raise ValueError("unsupported structural candidate synthesis request schema")
        raw_program = state.get("program")
        if not isinstance(raw_program, Mapping):
            raise TypeError("structural synthesis program state must be a mapping")
        program = _structural_node_from_state(raw_program)
        raw_evidence = state.get("evidence", ())
        if isinstance(raw_evidence, (str, bytes)) or not isinstance(raw_evidence, Sequence):
            raise TypeError("synthesis evidence state must be a sequence")
        evidence: list[EvidenceRef] = []
        for row in raw_evidence:
            if not isinstance(row, Mapping):
                raise TypeError("synthesis evidence state row must be a mapping")
            evidence.append(EvidenceRef.from_state(row))
        request = cls(
            program=program,
            objective=str(state["objective"]),
            evidence=tuple(evidence),
            experiment_receipt_ids=tuple(str(value) for value in state.get("experiment_receipt_ids", ())),
            causal_program_ids=tuple(str(value) for value in state.get("causal_program_ids", ())),
            generation_budget=_structural_state_int(
                state.get("generation_budget", 0),
                "generation budget",
            ),
            mode=SynthesisMode(str(state["mode"])),
        )
        raw_sources = state.get("source_item_ids", ())
        if isinstance(raw_sources, (str, bytes)) or not isinstance(raw_sources, Sequence):
            raise TypeError("structural source item ids state must be a sequence")
        serialized_sources = tuple(str(value) for value in raw_sources)
        if serialized_sources != request.source_item_ids:
            raise ValueError("structural source item ids mismatch")
        if request.to_state() != dict(state):
            raise ValueError("non-canonical structural synthesis request state")
        return request


@dataclass(frozen=True, slots=True)
class StructuralSynthesisReceipt:
    mode: SynthesisMode
    objective: str
    program: StructuralNode
    evidence_ids: tuple[str, ...]
    experiment_receipt_ids: tuple[str, ...]
    causal_program_ids: tuple[str, ...]
    generation_budget: int
    candidates_considered: int
    candidate_id: str | None
    semantic_fingerprint: str | None
    abstention_reason: str | None
    synthesis_id: str

    def __post_init__(self) -> None:
        mode = SynthesisMode(self.mode)
        if mode is not SynthesisMode.STRUCTURAL_COMPOSITION_PROGRAM:
            raise ValueError("structural synthesis receipt requires structural composition mode")
        _analyze_structural_program(self.program)
        objective = _nonempty(self.objective, "synthesis objective")
        evidence_ids = _sorted_unique_ids(self.evidence_ids, "evidence ids")
        experiments = _sorted_unique_ids(self.experiment_receipt_ids, "experiment receipt ids")
        causal = _sorted_unique_ids(self.causal_program_ids, "causal program ids")
        if (
            isinstance(self.generation_budget, bool)
            or not isinstance(self.generation_budget, int)
            or isinstance(self.candidates_considered, bool)
            or not isinstance(self.candidates_considered, int)
        ):
            raise TypeError("structural synthesis receipt budget values must be integers")
        budget = self.generation_budget
        considered = self.candidates_considered
        if budget < 0 or considered < 0 or considered > budget:
            raise ValueError("structural synthesis receipt budget accounting is invalid")
        candidate_id = None if self.candidate_id is None else _nonempty(self.candidate_id, "candidate id")
        fingerprint = None if self.semantic_fingerprint is None else _nonempty(self.semantic_fingerprint, "semantic fingerprint")
        reason = None if self.abstention_reason is None else _nonempty(self.abstention_reason, "abstention reason")
        if candidate_id is None:
            if fingerprint is not None or reason is None:
                raise ValueError("abstaining structural synthesis receipt requires reason and no candidate fingerprint")
        elif fingerprint is None or reason is not None:
            raise ValueError("successful structural synthesis receipt requires candidate fingerprint and no abstention reason")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "objective", objective)
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "experiment_receipt_ids", experiments)
        object.__setattr__(self, "causal_program_ids", causal)
        object.__setattr__(self, "generation_budget", budget)
        object.__setattr__(self, "candidates_considered", considered)
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "semantic_fingerprint", fingerprint)
        object.__setattr__(self, "abstention_reason", reason)
        expected = f"synthesis:{canonical_digest(self.semantic_state())}"
        if str(self.synthesis_id) != expected:
            raise ValueError("structural synthesis receipt identity mismatch")
        object.__setattr__(self, "synthesis_id", expected)

    @property
    def source_item_ids(self) -> tuple[str, ...]:
        return _analyze_structural_program(self.program).source_item_ids

    def semantic_state(self) -> dict[str, Any]:
        return {
            "schema_version": STRUCTURAL_SCHEMA_VERSION,
            "mode": self.mode.value,
            "objective": self.objective,
            "program": self.program.to_state(),
            "source_item_ids": list(self.source_item_ids),
            "evidence_ids": list(self.evidence_ids),
            "experiment_receipt_ids": list(self.experiment_receipt_ids),
            "causal_program_ids": list(self.causal_program_ids),
            "generation_budget": self.generation_budget,
            "candidates_considered": self.candidates_considered,
            "candidate_id": self.candidate_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            "abstention_reason": self.abstention_reason,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.semantic_state(), "synthesis_id": self.synthesis_id}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "StructuralSynthesisReceipt":
        if str(state.get("schema_version")) != STRUCTURAL_SCHEMA_VERSION:
            raise ValueError("unsupported structural candidate synthesis receipt schema")
        raw_program = state.get("program")
        if not isinstance(raw_program, Mapping):
            raise TypeError("structural synthesis program state must be a mapping")
        program = _structural_node_from_state(raw_program)
        receipt = cls(
            mode=SynthesisMode(str(state["mode"])),
            objective=str(state["objective"]),
            program=program,
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            experiment_receipt_ids=tuple(str(value) for value in state.get("experiment_receipt_ids", ())),
            causal_program_ids=tuple(str(value) for value in state.get("causal_program_ids", ())),
            generation_budget=_structural_state_int(
                state["generation_budget"],
                "generation budget",
            ),
            candidates_considered=_structural_state_int(
                state["candidates_considered"],
                "candidates considered",
            ),
            candidate_id=None if state.get("candidate_id") is None else str(state["candidate_id"]),
            semantic_fingerprint=None if state.get("semantic_fingerprint") is None else str(state["semantic_fingerprint"]),
            abstention_reason=None if state.get("abstention_reason") is None else str(state["abstention_reason"]),
            synthesis_id=str(state["synthesis_id"]),
        )
        raw_sources = state.get("source_item_ids", ())
        if isinstance(raw_sources, (str, bytes)) or not isinstance(raw_sources, Sequence):
            raise TypeError("structural source item ids state must be a sequence")
        serialized_sources = tuple(str(value) for value in raw_sources)
        if serialized_sources != receipt.source_item_ids:
            raise ValueError("structural source item ids mismatch")
        if receipt.to_state() != dict(state):
            raise ValueError("non-canonical structural synthesis receipt state")
        return receipt


@dataclass(frozen=True, slots=True)
class StructuralSynthesisResult:
    candidate: CapabilityCandidate | None
    receipt: StructuralSynthesisReceipt

    def __post_init__(self) -> None:
        if self.candidate is not None and not isinstance(self.candidate, CapabilityCandidate):
            raise TypeError("structural synthesis result candidate must be CapabilityCandidate or None")
        if not isinstance(self.receipt, StructuralSynthesisReceipt):
            raise TypeError("structural synthesis result receipt must be StructuralSynthesisReceipt")
        if self.candidate is None:
            if self.receipt.candidate_id is not None:
                raise ValueError("abstaining structural synthesis result cannot carry candidate identity")
        elif self.receipt.candidate_id != self.candidate.candidate_id:
            raise ValueError("structural synthesis result candidate/receipt identity mismatch")


def _structural_receipt(
    request: StructuralSynthesisRequest,
    *,
    candidates_considered: int,
    candidate: CapabilityCandidate | None = None,
    abstention_reason: str | None = None,
) -> StructuralSynthesisReceipt:
    candidate_id = None if candidate is None else candidate.candidate_id
    fingerprint = None if candidate is None else canonical_digest(candidate.semantic_state())
    semantic = {
        "schema_version": STRUCTURAL_SCHEMA_VERSION,
        "mode": request.mode.value,
        "objective": request.objective,
        "program": request.program.to_state(),
        "source_item_ids": list(request.source_item_ids),
        "evidence_ids": [row.evidence_id for row in request.evidence],
        "experiment_receipt_ids": list(request.experiment_receipt_ids),
        "causal_program_ids": list(request.causal_program_ids),
        "generation_budget": request.generation_budget,
        "candidates_considered": int(candidates_considered),
        "candidate_id": candidate_id,
        "semantic_fingerprint": fingerprint,
        "abstention_reason": abstention_reason,
    }
    return StructuralSynthesisReceipt(
        mode=request.mode,
        objective=request.objective,
        program=request.program,
        evidence_ids=tuple(row.evidence_id for row in request.evidence),
        experiment_receipt_ids=request.experiment_receipt_ids,
        causal_program_ids=request.causal_program_ids,
        generation_budget=request.generation_budget,
        candidates_considered=int(candidates_considered),
        candidate_id=candidate_id,
        semantic_fingerprint=fingerprint,
        abstention_reason=abstention_reason,
        synthesis_id=f"synthesis:{canonical_digest(semantic)}",
    )


def _contains_field(expr: Expr, field_name: str) -> bool:
    if isinstance(expr, Field):
        return expr.name == field_name
    if isinstance(expr, Unary):
        return _contains_field(expr.arg, field_name)
    if isinstance(expr, Binary):
        return _contains_field(expr.left, field_name) or _contains_field(expr.right, field_name)
    if isinstance(expr, IfElse):
        return any(
            _contains_field(row, field_name)
            for row in (expr.condition, expr.when_true, expr.when_false)
        )
    if isinstance(expr, AbstractionCall):
        return any(_contains_field(row, field_name) for row in expr.args)
    return False


def _contains_reserved_param_field(expr: Expr) -> bool:
    if isinstance(expr, Field):
        return expr.name.startswith(_RESERVED_PARAM_PREFIX)
    if isinstance(expr, Unary):
        return _contains_reserved_param_field(expr.arg)
    if isinstance(expr, Binary):
        return _contains_reserved_param_field(expr.left) or _contains_reserved_param_field(expr.right)
    if isinstance(expr, IfElse):
        return any(
            _contains_reserved_param_field(row)
            for row in (expr.condition, expr.when_true, expr.when_false)
        )
    if isinstance(expr, AbstractionCall):
        return any(_contains_reserved_param_field(row) for row in expr.args)
    return False


def _bind_synthesis_parameter(expr: Expr) -> Expr:
    if isinstance(expr, Field):
        return TemplateParam(0) if expr.name == _PARAM_FIELD else expr
    if isinstance(expr, (Const, TemplateParam)):
        return expr
    if isinstance(expr, Unary):
        return Unary(expr.op, _bind_synthesis_parameter(expr.arg))
    if isinstance(expr, Binary):
        return Binary(
            expr.op,
            _bind_synthesis_parameter(expr.left),
            _bind_synthesis_parameter(expr.right),
        )
    if isinstance(expr, IfElse):
        return IfElse(
            _bind_synthesis_parameter(expr.condition),
            _bind_synthesis_parameter(expr.when_true),
            _bind_synthesis_parameter(expr.when_false),
        )
    if isinstance(expr, AbstractionCall):
        raise ValueError("candidate synthesis expansion left an unresolved abstraction call")
    raise TypeError("unknown cognitive expression node")


def _reserved_param_field(index: int) -> str:
    return f"{_RESERVED_PARAM_PREFIX}{index}__"


def _bind_structural_parameters(expr: Expr, parameter_count: int) -> Expr:
    field_to_index = {_reserved_param_field(index): index for index in range(parameter_count)}
    if isinstance(expr, Field):
        if expr.name in field_to_index:
            return TemplateParam(field_to_index[expr.name])
        if expr.name.startswith(_RESERVED_PARAM_PREFIX):
            raise ValueError("candidate synthesis expansion contains unexpected reserved field")
        return expr
    if isinstance(expr, (Const, TemplateParam)):
        return expr
    if isinstance(expr, Unary):
        return Unary(expr.op, _bind_structural_parameters(expr.arg, parameter_count))
    if isinstance(expr, Binary):
        return Binary(
            expr.op,
            _bind_structural_parameters(expr.left, parameter_count),
            _bind_structural_parameters(expr.right, parameter_count),
        )
    if isinstance(expr, IfElse):
        return IfElse(
            _bind_structural_parameters(expr.condition, parameter_count),
            _bind_structural_parameters(expr.when_true, parameter_count),
            _bind_structural_parameters(expr.when_false, parameter_count),
        )
    if isinstance(expr, AbstractionCall):
        raise ValueError("candidate synthesis expansion left an unresolved abstraction call")
    raise TypeError("unknown cognitive expression node")


def _candidate_score(candidate: CapabilityCandidate) -> tuple[int, int, str]:
    payload = candidate.payload()
    if not isinstance(payload, LearnedAbstraction):
        raise TypeError("candidate synthesis ranking requires learned abstraction payload")
    return (
        payload.template.cost,
        -len(payload.support_task_ids),
        candidate.candidate_id,
    )


class _StructuralAbstention(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class CandidateSynthesisEngine:
    """Stateless, fail-closed proposal generator with no lifecycle authority."""

    def __init__(self, library: CognitiveLibrary) -> None:
        if not isinstance(library, CognitiveLibrary):
            raise TypeError("library must be CognitiveLibrary")
        self.library = library

    def _return(self, before_digest: str, result: SynthesisResult) -> SynthesisResult:
        if self.library.digest != before_digest:
            raise RuntimeError("candidate synthesis must not mutate Cognitive Library")
        return result

    def _abstain(
        self,
        before_digest: str,
        request: SynthesisRequest,
        *,
        candidates_considered: int,
        reason: str,
    ) -> SynthesisResult:
        return self._return(
            before_digest,
            SynthesisResult(
                candidate=None,
                receipt=_receipt(
                    request,
                    candidates_considered=candidates_considered,
                    abstention_reason=reason,
                ),
            ),
        )

    def _structural_return(
        self,
        before_digest: str,
        result: StructuralSynthesisResult,
    ) -> StructuralSynthesisResult:
        if self.library.digest != before_digest:
            raise RuntimeError("candidate synthesis must not mutate Cognitive Library")
        return result

    def _structural_abstain(
        self,
        before_digest: str,
        request: StructuralSynthesisRequest,
        *,
        candidates_considered: int,
        reason: str,
    ) -> StructuralSynthesisResult:
        return self._structural_return(
            before_digest,
            StructuralSynthesisResult(
                candidate=None,
                receipt=_structural_receipt(
                    request,
                    candidates_considered=candidates_considered,
                    abstention_reason=reason,
                ),
            ),
        )

    def _resolve_sources(
        self,
        before_digest: str,
        request: SynthesisRequest,
    ) -> tuple[list[LearnedAbstraction] | None, SynthesisResult | None]:
        sources: list[LearnedAbstraction] = []
        for source_id in request.source_item_ids:
            try:
                source = self.library.vocabulary.get(source_id)
            except KeyError:
                return None, self._abstain(
                    before_digest,
                    request,
                    candidates_considered=0,
                    reason=f"source_not_found:{source_id}",
                )
            if source.parameter_count != 1:
                return None, self._abstain(
                    before_digest,
                    request,
                    candidates_considered=0,
                    reason=f"source_not_unary:{source_id}",
                )
            if _contains_field(source.template, _PARAM_FIELD):
                return None, self._abstain(
                    before_digest,
                    request,
                    candidates_considered=0,
                    reason=f"reserved_field_collision:{source_id}",
                )
            sources.append(source)
        return sources, None

    def _compose_sources(self, sources: Sequence[LearnedAbstraction]) -> LearnedAbstraction:
        composed: Expr = Field(_PARAM_FIELD)
        for source in sources:
            composed = AbstractionCall(source.abstraction_id, (composed,))
        expanded = expand_expr(composed, self.library.vocabulary)
        template = _bind_synthesis_parameter(expanded)
        support_task_ids = tuple(
            sorted({task_id for source in sources for task_id in source.support_task_ids})
        )
        return make_abstraction(
            template,
            parameter_count=1,
            support_task_ids=support_task_ids,
            raw_occurrence_cost=template.cost,
            rewritten_cost=template.cost,
        )

    def _installed_abstraction(self, generated: LearnedAbstraction) -> LearnedAbstraction | None:
        try:
            existing = self.library.vocabulary.get(generated.abstraction_id)
        except KeyError:
            return None
        if existing != generated:
            raise ValueError("generated abstraction identity collides with different library payload")
        return existing

    def _synthesize_composition(
        self,
        before_digest: str,
        request: SynthesisRequest,
        sources: Sequence[LearnedAbstraction],
    ) -> SynthesisResult:
        generated = self._compose_sources(sources)
        if generated.abstraction_id in set(request.source_item_ids):
            return self._abstain(
                before_digest,
                request,
                candidates_considered=1,
                reason="candidate_matches_source",
            )
        if self._installed_abstraction(generated) is not None:
            return self._abstain(
                before_digest,
                request,
                candidates_considered=1,
                reason="candidate_already_in_library",
            )
        candidate = CapabilityCandidate.for_learned_abstraction(generated)
        return self._return(
            before_digest,
            SynthesisResult(
                candidate=candidate,
                receipt=_receipt(request, candidates_considered=1, candidate=candidate),
            ),
        )

    def _synthesize_bounded_search(
        self,
        before_digest: str,
        request: SynthesisRequest,
        sources: Sequence[LearnedAbstraction],
    ) -> SynthesisResult:
        source_ids = set(request.source_item_ids)
        seen_candidate_ids: set[str] = set()
        best_candidate: CapabilityCandidate | None = None
        best_score: tuple[int, int, str] | None = None
        considered = 0

        for pair in permutations(sources, 2):
            if considered >= request.generation_budget:
                break
            considered += 1
            generated = self._compose_sources(pair)
            if generated.abstraction_id in source_ids:
                continue
            if self._installed_abstraction(generated) is not None:
                continue
            candidate = CapabilityCandidate.for_learned_abstraction(generated)
            if candidate.candidate_id in seen_candidate_ids:
                continue
            seen_candidate_ids.add(candidate.candidate_id)
            score = _candidate_score(candidate)
            if best_score is None or score < best_score:
                best_score = score
                best_candidate = candidate

        if best_candidate is None:
            return self._abstain(
                before_digest,
                request,
                candidates_considered=considered,
                reason="no_novel_candidate_within_budget",
            )
        return self._return(
            before_digest,
            SynthesisResult(
                candidate=best_candidate,
                receipt=_receipt(
                    request,
                    candidates_considered=considered,
                    candidate=best_candidate,
                ),
            ),
        )

    def _synthesize_progressive_search(
        self,
        before_digest: str,
        request: SynthesisRequest,
        sources: Sequence[LearnedAbstraction],
    ) -> SynthesisResult:
        source_ids = set(request.source_item_ids)
        seen_candidate_ids: set[str] = set()
        considered = 0
        source_count = len(sources)

        for depth in range(2, source_count + 1):
            frontier_size = perm(source_count, depth)
            remaining = request.generation_budget - considered

            if remaining < frontier_size:
                attempted = 0
                for hypothesis in permutations(sources, depth):
                    if attempted >= remaining:
                        break
                    attempted += 1
                    considered += 1
                    generated = self._compose_sources(hypothesis)
                    if generated.abstraction_id in source_ids:
                        continue
                    if self._installed_abstraction(generated) is not None:
                        continue
                    candidate = CapabilityCandidate.for_learned_abstraction(generated)
                    seen_candidate_ids.add(candidate.candidate_id)
                return self._abstain(
                    before_digest,
                    request,
                    candidates_considered=considered,
                    reason="generation_budget_exhausted",
                )

            frontier_candidates: dict[str, CapabilityCandidate] = {}
            for hypothesis in permutations(sources, depth):
                considered += 1
                generated = self._compose_sources(hypothesis)
                if generated.abstraction_id in source_ids:
                    continue
                if self._installed_abstraction(generated) is not None:
                    continue
                candidate = CapabilityCandidate.for_learned_abstraction(generated)
                if candidate.candidate_id in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(candidate.candidate_id)
                frontier_candidates[candidate.candidate_id] = candidate

            if frontier_candidates:
                best_candidate = min(frontier_candidates.values(), key=_candidate_score)
                return self._return(
                    before_digest,
                    SynthesisResult(
                        candidate=best_candidate,
                        receipt=_receipt(
                            request,
                            candidates_considered=considered,
                            candidate=best_candidate,
                        ),
                    ),
                )

        return self._abstain(
            before_digest,
            request,
            candidates_considered=considered,
            reason="no_novel_candidate",
        )

    def _compile_structural_node(
        self,
        node: StructuralNode,
        support_task_ids: set[str],
    ) -> Expr:
        if isinstance(node, StructuralInput):
            return Field(_reserved_param_field(node.index))
        try:
            source = self.library.vocabulary.get(node.source_abstraction_id)
        except KeyError:
            raise _StructuralAbstention(f"source_not_found:{node.source_abstraction_id}") from None
        if not isinstance(source, LearnedAbstraction):
            raise TypeError("structural synthesis source must be LearnedAbstraction")
        if len(node.args) != source.parameter_count:
            raise _StructuralAbstention(f"source_arity_mismatch:{node.source_abstraction_id}")
        if _contains_reserved_param_field(source.template):
            raise _StructuralAbstention(f"reserved_field_collision:{node.source_abstraction_id}")
        support_task_ids.update(source.support_task_ids)
        return AbstractionCall(
            source.abstraction_id,
            tuple(self._compile_structural_node(child, support_task_ids) for child in node.args),
        )

    def _synthesize_structural_inner(
        self,
        before_digest: str,
        request: StructuralSynthesisRequest,
    ) -> StructuralSynthesisResult:
        if request.generation_budget == 0:
            return self._structural_abstain(
                before_digest,
                request,
                candidates_considered=0,
                reason="generation_budget_exhausted",
            )
        support_task_ids: set[str] = set()
        try:
            lowered = self._compile_structural_node(request.program, support_task_ids)
        except _StructuralAbstention as exc:
            return self._structural_abstain(
                before_digest,
                request,
                candidates_considered=1,
                reason=exc.reason,
            )
        expanded = expand_expr(
            lowered,
            self.library.vocabulary,
            max_expansion_nodes=_MAX_EXPANSION_NODES,
        )
        template = _bind_structural_parameters(expanded, request.parameter_count)
        generated = make_abstraction(
            template,
            parameter_count=request.parameter_count,
            support_task_ids=tuple(sorted(support_task_ids)),
            raw_occurrence_cost=template.cost,
            rewritten_cost=template.cost,
        )
        if generated.abstraction_id in set(request.source_item_ids):
            return self._structural_abstain(
                before_digest,
                request,
                candidates_considered=1,
                reason="candidate_matches_source",
            )
        if self._installed_abstraction(generated) is not None:
            return self._structural_abstain(
                before_digest,
                request,
                candidates_considered=1,
                reason="candidate_already_in_library",
            )
        candidate = CapabilityCandidate.for_learned_abstraction(generated)
        return self._structural_return(
            before_digest,
            StructuralSynthesisResult(
                candidate=candidate,
                receipt=_structural_receipt(
                    request,
                    candidates_considered=1,
                    candidate=candidate,
                ),
            ),
        )

    def _synthesize_structural(
        self,
        request: StructuralSynthesisRequest,
    ) -> StructuralSynthesisResult:
        before_digest = self.library.digest
        try:
            return self._synthesize_structural_inner(before_digest, request)
        finally:
            if self.library.digest != before_digest:
                raise RuntimeError("candidate synthesis must not mutate Cognitive Library")

    def synthesize(
        self,
        request: SynthesisRequest | StructuralSynthesisRequest,
    ) -> SynthesisResult | StructuralSynthesisResult:
        if isinstance(request, StructuralSynthesisRequest):
            return self._synthesize_structural(request)
        if not isinstance(request, SynthesisRequest):
            raise TypeError("request must be SynthesisRequest or StructuralSynthesisRequest")
        before_digest = self.library.digest
        if request.generation_budget == 0:
            return self._abstain(
                before_digest,
                request,
                candidates_considered=0,
                reason="generation_budget_exhausted",
            )

        sources, abstention = self._resolve_sources(before_digest, request)
        if abstention is not None:
            return abstention
        assert sources is not None

        if request.mode is SynthesisMode.LEARNED_ABSTRACTION_COMPOSITION:
            return self._synthesize_composition(before_digest, request, sources)
        if request.mode is SynthesisMode.BOUNDED_LEARNED_ABSTRACTION_SEARCH:
            return self._synthesize_bounded_search(before_digest, request, sources)
        if request.mode is SynthesisMode.PROGRESSIVE_MULTI_DEPTH_SEARCH:
            return self._synthesize_progressive_search(before_digest, request, sources)
        raise ValueError("unsupported candidate synthesis mode")


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "STRUCTURAL_SCHEMA_VERSION",
    "DESIGN_LINEAGE",
    "MAX_STRUCTURAL_NODES",
    "MAX_STRUCTURAL_DEPTH",
    "SynthesisMode",
    "EvidencePhase",
    "EvidenceRef",
    "SynthesisRequest",
    "SynthesisReceipt",
    "SynthesisResult",
    "StructuralInput",
    "StructuralCall",
    "StructuralSynthesisRequest",
    "StructuralSynthesisReceipt",
    "StructuralSynthesisResult",
    "CandidateSynthesisEngine",
)
