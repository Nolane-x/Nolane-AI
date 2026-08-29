from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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
COMPONENT_VERSION = "0.0.1"
SCHEMA_VERSION = "candidate-synthesis-v1"
DESIGN_LINEAGE = "post-Epoch-0 native synthesis; R2.56/R2.61/R2.65 are design provenance only"
_PARAM_FIELD = "__nolane_candidate_synthesis_param_0__"


class SynthesisMode(str, Enum):
    LEARNED_ABSTRACTION_COMPOSITION = "learned_abstraction_composition"


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
        objective = _nonempty(self.objective, "synthesis objective")
        sources = _ordered_unique_ids(self.source_item_ids, "source item ids", minimum=2)
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
        objective = _nonempty(self.objective, "synthesis objective")
        sources = _ordered_unique_ids(self.source_item_ids, "source item ids", minimum=2)
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

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        if not isinstance(request, SynthesisRequest):
            raise TypeError("request must be SynthesisRequest")
        before_digest = self.library.digest
        if request.mode is not SynthesisMode.LEARNED_ABSTRACTION_COMPOSITION:
            raise ValueError("unsupported candidate synthesis mode")
        if request.generation_budget == 0:
            return self._abstain(
                before_digest,
                request,
                candidates_considered=0,
                reason="generation_budget_exhausted",
            )

        sources: list[LearnedAbstraction] = []
        for source_id in request.source_item_ids:
            try:
                source = self.library.vocabulary.get(source_id)
            except KeyError:
                return self._abstain(
                    before_digest,
                    request,
                    candidates_considered=0,
                    reason=f"source_not_found:{source_id}",
                )
            if source.parameter_count != 1:
                return self._abstain(
                    before_digest,
                    request,
                    candidates_considered=0,
                    reason=f"source_not_unary:{source_id}",
                )
            if _contains_field(source.template, _PARAM_FIELD):
                return self._abstain(
                    before_digest,
                    request,
                    candidates_considered=0,
                    reason=f"reserved_field_collision:{source_id}",
                )
            sources.append(source)

        # AbstractionCall is the synthesis IR: source order is semantic. The IR
        # is then fully expanded against the canonical vocabulary so the final
        # CapabilityCandidate is standalone-decodable by Capability Acquisition.
        composed: Expr = Field(_PARAM_FIELD)
        for source in sources:
            composed = AbstractionCall(source.abstraction_id, (composed,))
        expanded = expand_expr(composed, self.library.vocabulary)
        template = _bind_synthesis_parameter(expanded)

        support_task_ids = tuple(
            sorted({task_id for source in sources for task_id in source.support_task_ids})
        )
        generated = make_abstraction(
            template,
            parameter_count=1,
            support_task_ids=support_task_ids,
            raw_occurrence_cost=template.cost,
            rewritten_cost=template.cost,
        )

        if generated.abstraction_id in set(request.source_item_ids):
            return self._abstain(
                before_digest,
                request,
                candidates_considered=1,
                reason="candidate_matches_source",
            )
        try:
            existing = self.library.vocabulary.get(generated.abstraction_id)
        except KeyError:
            existing = None
        if existing is not None:
            if existing != generated:
                raise ValueError("generated abstraction identity collides with different library payload")
            return self._abstain(
                before_digest,
                request,
                candidates_considered=1,
                reason="candidate_already_in_library",
            )

        candidate = CapabilityCandidate.for_learned_abstraction(generated)
        result = SynthesisResult(
            candidate=candidate,
            receipt=_receipt(request, candidates_considered=1, candidate=candidate),
        )
        return self._return(before_digest, result)


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "DESIGN_LINEAGE",
    "SynthesisMode",
    "EvidencePhase",
    "EvidenceRef",
    "SynthesisRequest",
    "SynthesisReceipt",
    "SynthesisResult",
    "CandidateSynthesisEngine",
)
