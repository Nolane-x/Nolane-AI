from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .evidence import EvidenceRecord


COMPONENT_ID = "external.causal"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder R2.58/R2.62 bounded causal-program lineage"

_NUMERIC_COMPOSITION_OPS = ("add", "sub", "rsub", "mul", "min", "max")
_COMMUTATIVE_OPS = frozenset({"add", "mul", "min", "max"})


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True, slots=True)
class PositionalSchema:
    field_names: tuple[str, ...]

    def __post_init__(self) -> None:
        fields = tuple(str(value).strip() for value in self.field_names)
        if not fields or any(not value for value in fields):
            raise ValueError("field_names must be non-empty strings")
        if len(set(fields)) != len(fields):
            raise ValueError("field_names must be distinct")
        object.__setattr__(self, "field_names", fields)

    @property
    def canonical_fields(self) -> tuple[str, ...]:
        return tuple(f"__f{index}" for index in range(len(self.field_names)))

    def to_canonical_context(self, context: Mapping[str, object]) -> dict[str, object]:
        missing = [field for field in self.field_names if field not in context]
        if missing:
            raise KeyError(f"missing schema fields: {missing}")
        return {
            canonical: context[field]
            for field, canonical in zip(self.field_names, self.canonical_fields, strict=True)
        }


@dataclass(frozen=True, slots=True)
class InterventionSpec:
    """Pure positional intervention whose identity is independent of field names."""

    bindings: tuple[tuple[int, float], ...]

    def __post_init__(self) -> None:
        normalized: list[tuple[int, float]] = []
        for position, value in tuple(self.bindings):
            position = int(position)
            value = float(value)
            if position < 0:
                raise ValueError("intervention positions must be non-negative")
            if not math.isfinite(value):
                raise ValueError("intervention values must be finite")
            normalized.append((position, value))
        if not normalized:
            raise ValueError("intervention must contain at least one binding")
        positions = [position for position, _ in normalized]
        if len(positions) != len(set(positions)):
            raise ValueError("intervention positions must be distinct")
        values = [value for _, value in normalized]
        if len(values) != len(set(values)):
            raise ValueError("intervention anchor values must be distinct")
        object.__setattr__(self, "bindings", tuple(normalized))

    @property
    def intervention_id(self) -> str:
        raw = _canonical_json(
            {"bindings": [[position, value] for position, value in self.bindings]}
        )
        return f"intv.{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

    def bind(self, field_names: Sequence[str]) -> tuple[tuple[str, float], ...]:
        fields = tuple(map(str, field_names))
        if not fields:
            raise ValueError("field_names must be non-empty")
        result: list[tuple[str, float]] = []
        for position, value in self.bindings:
            if position >= len(fields):
                raise ValueError("intervention position out of range")
            result.append((fields[position], value))
        return tuple(result)

    def apply(self, context: Mapping[str, object], field_names: Sequence[str]) -> dict[str, object]:
        result = dict(context)
        for field, value in self.bind(field_names):
            if field not in result:
                raise KeyError(field)
            result[field] = value
        return result

    def to_state(self) -> dict[str, object]:
        return {"bindings": [[position, value] for position, value in self.bindings]}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "InterventionSpec":
        raw = state.get("bindings")
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise TypeError("intervention state bindings must be a sequence")
        bindings: list[tuple[int, float]] = []
        for row in raw:
            if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) != 2:
                raise ValueError("intervention binding rows must have position and value")
            bindings.append((int(row[0]), float(row[1])))
        return cls(tuple(bindings))


def enumerate_interventions(
    field_names: Sequence[str],
    anchor_values: Sequence[float],
    *,
    arity: int = 2,
) -> tuple[InterventionSpec, ...]:
    fields = tuple(map(str, field_names))
    if not fields or any(not value.strip() for value in fields):
        raise ValueError("field_names must be non-empty strings")
    if len(set(fields)) != len(fields):
        raise ValueError("field_names must be distinct")
    arity = int(arity)
    if arity < 1:
        raise ValueError("arity must be positive")
    if arity > len(fields):
        return ()
    anchors = tuple(float(value) for value in anchor_values)
    if any(not math.isfinite(value) for value in anchors):
        raise ValueError("anchor_values must be finite")
    anchors = tuple(dict.fromkeys(anchors))
    if arity > len(anchors):
        return ()
    rows: list[InterventionSpec] = []
    for positions in itertools.combinations(range(len(fields)), arity):
        for values in itertools.permutations(anchors, arity):
            rows.append(InterventionSpec(tuple(zip(positions, values, strict=True))))
    return tuple(rows)


def _numeric(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("causal composition values must be numeric scalars")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("causal composition values must be finite")
    return result


def _equivalent(actual: object, expected: object) -> bool:
    if (
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and isinstance(expected, (int, float))
        and not isinstance(expected, bool)
    ):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
        except (TypeError, ValueError, OverflowError):
            return False
    return actual == expected


def _oracle_value(
    oracle: Callable[[Mapping[str, object]], object],
    context: Mapping[str, object],
) -> object:
    value = oracle(dict(context))
    try:
        _canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("oracle outputs must be finite JSON-compatible values") from exc
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("oracle output must be finite")
    return value


def _compose_value(op: str, left: object, right: object) -> float:
    a = _numeric(left)
    b = _numeric(right)
    if op == "add":
        out = a + b
    elif op == "sub":
        out = a - b
    elif op == "rsub":
        out = b - a
    elif op == "mul":
        out = a * b
    elif op == "min":
        out = min(a, b)
    elif op == "max":
        out = max(a, b)
    else:
        raise ValueError(f"unsupported composition op: {op}")
    if not math.isfinite(out):
        raise ValueError("composition output must be finite")
    return out


def _program_id(op: str, interventions: tuple[InterventionSpec, InterventionSpec]) -> str:
    rows = interventions
    if op in _COMMUTATIVE_OPS:
        rows = tuple(sorted(rows, key=lambda spec: spec.intervention_id))
    payload = {
        "composition_op": op,
        "interventions": [
            [[int(position), float(value)] for position, value in spec.bindings]
            for spec in rows
        ],
    }
    return f"exp2.{hashlib.sha256(_canonical_json(payload).encode('utf-8')).hexdigest()}"


@dataclass(frozen=True, slots=True)
class InterventionProfile:
    intervention: InterventionSpec
    discovery_outputs: tuple[object, ...]
    validation_outputs: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class ComplementaryExperimentProgram:
    interventions: tuple[InterventionSpec, InterventionSpec]
    composition_op: str
    program_id: str

    def __post_init__(self) -> None:
        if len(self.interventions) != 2 or not all(
            isinstance(row, InterventionSpec) for row in self.interventions
        ):
            raise ValueError("causal program requires exactly two interventions")
        if len({row.intervention_id for row in self.interventions}) != 2:
            raise ValueError("causal program interventions must be distinct")
        op = str(self.composition_op)
        if op not in _NUMERIC_COMPOSITION_OPS:
            raise ValueError("unsupported causal composition op")
        expected = _program_id(op, self.interventions)
        if str(self.program_id) != expected:
            raise ValueError("causal program id does not match canonical content")
        object.__setattr__(self, "composition_op", op)
        object.__setattr__(self, "program_id", expected)

    def to_state(self) -> dict[str, object]:
        return {
            "interventions": [row.to_state() for row in self.interventions],
            "composition_op": self.composition_op,
            "program_id": self.program_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ComplementaryExperimentProgram":
        raw = state.get("interventions")
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) != 2:
            raise ValueError("causal program state requires two interventions")
        interventions = tuple(InterventionSpec.from_state(row) for row in raw)
        return cls(
            interventions,  # type: ignore[arg-type]
            str(state["composition_op"]),
            str(state["program_id"]),
        )


@dataclass(frozen=True, slots=True)
class ComplementaryProgramCandidate:
    program: ComplementaryExperimentProgram
    left_profile: InterventionProfile
    right_profile: InterventionProfile
    left_alone_exact: bool
    right_alone_exact: bool
    left_essential_cases: int
    right_essential_cases: int
    discovery_exact: int
    validation_exact: int
    proper_subset_failures: int


@dataclass(frozen=True, slots=True)
class ComplementaryStructureReceipt:
    passed: bool
    selected: ComplementaryProgramCandidate | None
    passing_programs: int
    legal_interventions: int
    invalid_interventions_rejected: int
    degenerate_interventions_rejected: int
    intervention_candidates_considered: int
    pair_operation_candidates_considered: int
    discovery_target_outputs: tuple[object, ...]
    validation_target_outputs: tuple[object, ...]
    oracle_calls: int
    reason: str
    trainable_parameter_count: int = 0


def discover_complementary_experiment_structure(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    anchor_values: Sequence[float],
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    context_validator: Callable[[Mapping[str, object]], bool] | None = None,
    intervention_arity: int = 1,
    composition_ops: Sequence[str] = _NUMERIC_COMPOSITION_OPS,
    min_essential_cases: int = 1,
) -> ComplementaryStructureReceipt:
    if not callable(oracle):
        raise TypeError("oracle must be callable")
    if context_validator is not None and not callable(context_validator):
        raise TypeError("context_validator must be callable or None")
    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    discovery = tuple(dict(row) for row in discovery_contexts)
    validation = tuple(dict(row) for row in validation_contexts)
    if not discovery or not validation:
        raise ValueError("discovery and validation contexts must be non-empty")
    for row in (*discovery, *validation):
        schema.to_canonical_context(row)
        if context_validator is not None and not bool(context_validator(row)):
            raise ValueError("original contexts must satisfy context_validator")
    ops = tuple(dict.fromkeys(map(str, composition_ops)))
    if not ops or any(op not in _NUMERIC_COMPOSITION_OPS for op in ops):
        raise ValueError("composition_ops must be supported finite numeric operations")
    min_essential_cases = int(min_essential_cases)
    if min_essential_cases < 1:
        raise ValueError("min_essential_cases must be positive")

    oracle_calls = 0
    discovery_targets: list[object] = []
    validation_targets: list[object] = []
    for context in discovery:
        discovery_targets.append(_oracle_value(oracle, context))
        oracle_calls += 1
    for context in validation:
        validation_targets.append(_oracle_value(oracle, context))
        oracle_calls += 1

    specs = enumerate_interventions(
        schema.field_names,
        anchor_values,
        arity=int(intervention_arity),
    )
    profiles: list[InterventionProfile] = []
    invalid_rejected = 0
    degenerate_rejected = 0

    for spec in specs:
        applied_discovery = tuple(spec.apply(row, schema.field_names) for row in discovery)
        applied_validation = tuple(spec.apply(row, schema.field_names) for row in validation)
        if context_validator is not None and any(
            not bool(context_validator(row))
            for row in (*applied_discovery, *applied_validation)
        ):
            invalid_rejected += 1
            continue
        d_outputs: list[object] = []
        v_outputs: list[object] = []
        invalid = False
        for context in applied_discovery:
            try:
                d_outputs.append(_oracle_value(oracle, context))
            except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                invalid = True
                oracle_calls += 1
                break
            oracle_calls += 1
        if invalid:
            invalid_rejected += 1
            continue
        for context in applied_validation:
            try:
                v_outputs.append(_oracle_value(oracle, context))
            except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                invalid = True
                oracle_calls += 1
                break
            oracle_calls += 1
        if invalid:
            invalid_rejected += 1
            continue
        if len({_canonical_json(value) for value in d_outputs}) < 2:
            degenerate_rejected += 1
            continue
        if all(
            _equivalent(a, b)
            for a, b in zip(d_outputs, discovery_targets, strict=True)
        ) and all(
            _equivalent(a, b)
            for a, b in zip(v_outputs, validation_targets, strict=True)
        ):
            degenerate_rejected += 1
            continue
        profiles.append(InterventionProfile(spec, tuple(d_outputs), tuple(v_outputs)))

    profiles.sort(key=lambda row: row.intervention.intervention_id)
    passing: list[ComplementaryProgramCandidate] = []
    pair_ops_considered = 0
    all_targets = tuple(discovery_targets) + tuple(validation_targets)

    for left, right in itertools.combinations(profiles, 2):
        left_all = left.discovery_outputs + left.validation_outputs
        right_all = right.discovery_outputs + right.validation_outputs
        for op in ops:
            pair_ops_considered += 1
            try:
                d_composed = tuple(
                    _compose_value(op, a, b)
                    for a, b in zip(left.discovery_outputs, right.discovery_outputs, strict=True)
                )
                v_composed = tuple(
                    _compose_value(op, a, b)
                    for a, b in zip(left.validation_outputs, right.validation_outputs, strict=True)
                )
            except (TypeError, ValueError, OverflowError, ZeroDivisionError):
                continue
            d_exact = sum(
                _equivalent(a, b)
                for a, b in zip(d_composed, discovery_targets, strict=True)
            )
            if d_exact != len(discovery_targets):
                continue
            v_exact = sum(
                _equivalent(a, b)
                for a, b in zip(v_composed, validation_targets, strict=True)
            )
            if v_exact != len(validation_targets):
                continue
            left_exact = all(
                _equivalent(a, b)
                for a, b in zip(left_all, all_targets, strict=True)
            )
            right_exact = all(
                _equivalent(a, b)
                for a, b in zip(right_all, all_targets, strict=True)
            )
            if left_exact or right_exact:
                continue
            composed_all = d_composed + v_composed
            left_essential = sum(
                not _equivalent(full, right_value)
                for full, right_value in zip(composed_all, right_all, strict=True)
            )
            right_essential = sum(
                not _equivalent(full, left_value)
                for full, left_value in zip(composed_all, left_all, strict=True)
            )
            if left_essential < min_essential_cases or right_essential < min_essential_cases:
                continue
            candidate_left = left
            candidate_right = right
            interventions = (candidate_left.intervention, candidate_right.intervention)
            if op in _COMMUTATIVE_OPS:
                interventions = tuple(sorted(interventions, key=lambda spec: spec.intervention_id))  # type: ignore[assignment]
                if interventions[0] != candidate_left.intervention:
                    candidate_left, candidate_right = candidate_right, candidate_left
            program = ComplementaryExperimentProgram(
                interventions=interventions,
                composition_op=op,
                program_id=_program_id(op, interventions),
            )
            passing.append(
                ComplementaryProgramCandidate(
                    program=program,
                    left_profile=candidate_left,
                    right_profile=candidate_right,
                    left_alone_exact=False,
                    right_alone_exact=False,
                    left_essential_cases=left_essential,
                    right_essential_cases=right_essential,
                    discovery_exact=d_exact,
                    validation_exact=v_exact,
                    proper_subset_failures=2,
                )
            )

    passing.sort(
        key=lambda row: (
            row.program.interventions[0].intervention_id,
            row.program.interventions[1].intervention_id,
            ops.index(row.program.composition_op),
            row.program.program_id,
        )
    )
    selected = passing[0] if passing else None
    return ComplementaryStructureReceipt(
        passed=selected is not None,
        selected=selected,
        passing_programs=len(passing),
        legal_interventions=len(profiles),
        invalid_interventions_rejected=invalid_rejected,
        degenerate_interventions_rejected=degenerate_rejected,
        intervention_candidates_considered=len(specs),
        pair_operation_candidates_considered=pair_ops_considered,
        discovery_target_outputs=tuple(discovery_targets),
        validation_target_outputs=tuple(validation_targets),
        oracle_calls=oracle_calls,
        reason="complementary_program_discovered" if selected is not None else "no_complementary_program",
        trainable_parameter_count=0,
    )


class CausalProgramLedger:
    """Evidence-bound canonical registry for accepted bounded causal programs."""

    def __init__(self, cognitive_library_digest: str) -> None:
        self._cognitive_library_digest = _nonempty(
            cognitive_library_digest,
            "cognitive_library_digest",
        )
        self._rows: dict[str, tuple[ComplementaryExperimentProgram, EvidenceRecord]] = {}

    @property
    def cognitive_library_digest(self) -> str:
        return self._cognitive_library_digest

    def register(
        self,
        program: ComplementaryExperimentProgram,
        evidence: EvidenceRecord,
    ) -> None:
        if not isinstance(program, ComplementaryExperimentProgram):
            raise TypeError("program must be ComplementaryExperimentProgram")
        if not isinstance(evidence, EvidenceRecord):
            raise TypeError("evidence must be EvidenceRecord")
        if not evidence.passed:
            raise ValueError("causal programs require passing evidence")
        if evidence.false_accepts or evidence.regressions:
            raise ValueError("causal programs require clean evidence")
        row = (program, evidence)
        current = self._rows.get(program.program_id)
        if current is not None and current != row:
            raise ValueError("conflicting causal program registration")
        self._rows[program.program_id] = row

    def programs(self) -> tuple[ComplementaryExperimentProgram, ...]:
        return tuple(self._rows[key][0] for key in sorted(self._rows))

    def to_state(self) -> dict[str, object]:
        return {
            "cognitive_library_digest": self._cognitive_library_digest,
            "programs": [
                {
                    "program": self._rows[key][0].to_state(),
                    "evidence": self._rows[key][1].to_state(),
                }
                for key in sorted(self._rows)
            ],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "CausalProgramLedger":
        ledger = cls(str(state["cognitive_library_digest"]))
        raw = state.get("programs", ())
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise TypeError("causal program ledger rows must be a sequence")
        for row in raw:
            if not isinstance(row, Mapping):
                raise TypeError("causal program ledger row must be a mapping")
            program_state = row.get("program")
            evidence_state = row.get("evidence")
            if not isinstance(program_state, Mapping) or not isinstance(evidence_state, Mapping):
                raise TypeError("causal program ledger row requires program and evidence mappings")
            ledger.register(
                ComplementaryExperimentProgram.from_state(program_state),
                EvidenceRecord.from_state(evidence_state),
            )
        return ledger

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_state()).encode("utf-8")).hexdigest()


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
    "PositionalSchema",
    "InterventionSpec",
    "enumerate_interventions",
    "InterventionProfile",
    "ComplementaryExperimentProgram",
    "ComplementaryProgramCandidate",
    "ComplementaryStructureReceipt",
    "discover_complementary_experiment_structure",
    "CausalProgramLedger",
)
