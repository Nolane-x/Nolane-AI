from __future__ import annotations

import hashlib
import itertools
import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r239_predicate_macros import ProbeMacro, instantiate_macro
from .r239_typed_probe_dsl import (
    ProbeType,
    TypedProbe,
    and_probe,
    bool_atom,
    equiv_probe,
    or_probe,
    trit_atom,
    typed_prediction_row,
    xor_probe,
)
from .r241_macro_competition import MacroCompetitionState

_CONNECTIVES = {
    'and': and_probe,
    'or': or_probe,
    'xor': xor_probe,
    'equiv': equiv_probe,
}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def _binary_entropy(p: float) -> float:
    p = max(0.0, min(1.0, float(p)))
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def _normalize_posterior(posterior: Mapping[str, float], hypothesis_ids: Sequence[str]) -> dict[str, float]:
    normalized_input = {str(k): float(v) for k, v in posterior.items()}
    if set(normalized_input) != set(map(str, hypothesis_ids)):
        raise ValueError('posterior/hypothesis coverage mismatch')
    out = {str(h): normalized_input[str(h)] for h in hypothesis_ids}
    if any((not math.isfinite(v)) or v < 0.0 for v in out.values()):
        raise ValueError('posterior must contain finite non-negative masses')
    total = sum(out.values())
    if total <= 0.0:
        raise ValueError('posterior mass must be positive')
    return {h: v / total for h, v in out.items()}


def _row_information(row: Mapping[str, bool], posterior: Mapping[str, float]) -> float:
    positive_mass = sum(posterior[h] for h, label in row.items() if bool(label))
    return _binary_entropy(positive_mass)


def _semantic_key(row: Mapping[str, bool], hypothesis_ids: Sequence[str]) -> tuple[bool, ...]:
    return tuple(bool(row[h]) for h in hypothesis_ids)


def _argument_candidates(
    macro: ProbeMacro,
    pools: Mapping[ProbeType, Sequence[str]],
) -> tuple[tuple[TypedProbe, ...], ...]:
    choices: list[tuple[TypedProbe, ...]] = []
    for expected in macro.parameter_types:
        raw_ids = tuple(sorted({str(v).strip().lower() for v in pools.get(expected, ()) if str(v).strip()}))
        if not raw_ids:
            return ()
        ctor = trit_atom if expected is ProbeType.TRIT else bool_atom
        choices.append(tuple(ctor(atom_id) for atom_id in raw_ids))

    rows: list[tuple[TypedProbe, ...]] = []
    for args in itertools.product(*choices):
        # Reusing one atom in distinct parameters usually produces degenerate
        # self-comparisons and can leak around a family-specific scope.
        typed_ids = [(arg.output_type, arg.atom_id) for arg in args]
        if len(set(typed_ids)) != len(typed_ids):
            continue
        rows.append(tuple(args))
    return tuple(rows)


@dataclass(frozen=True)
class MacroApplication:
    macro_id: str
    program: TypedProbe
    information_gain: float
    semantic_key: tuple[bool, ...]
    compression_gain: float


@dataclass(frozen=True)
class ComposedMacroCandidate:
    composition_id: str
    macro_ids: tuple[str, str]
    connective: str
    program: TypedProbe
    information_gain: float
    best_parent_information_gain: float
    synergy: float
    score: float
    semantic_key: tuple[bool, ...]


@dataclass(frozen=True)
class CompositionDiscoveryDecision:
    status: str
    composition_id: str | None
    selected_macro_ids: tuple[str, ...]
    connective: str | None
    program: TypedProbe | None
    information_gain: float
    best_parent_information_gain: float
    synergy: float
    candidates_evaluated: int
    counterexamples_checked: int
    rejected_composition_ids: tuple[str, ...]
    reason: str


def _trusted_macros(
    macros: Sequence[ProbeMacro],
    macro_states: Mapping[str, MacroCompetitionState] | None,
) -> tuple[ProbeMacro, ...]:
    unique: dict[str, ProbeMacro] = {}
    seen_ids: set[str] = set()
    for macro in macros:
        mid = str(macro.macro_id)
        if mid in seen_ids:
            raise ValueError('macro ids must be unique')
        seen_ids.add(mid)
        if macro.template.output_type is not ProbeType.BOOL:
            continue
        state = None if macro_states is None else macro_states.get(mid)
        if state is not None and state.quarantined:
            continue
        unique[mid] = macro
    return tuple(unique[mid] for mid in sorted(unique))


def _applications_for_macro(
    macro: ProbeMacro,
    pools: Mapping[ProbeType, Sequence[str]],
    posterior: Mapping[str, float],
    values_by_hypothesis: Mapping[str, Mapping[str, int | bool]],
    hypothesis_ids: Sequence[str],
    *,
    max_applications: int,
) -> tuple[MacroApplication, ...]:
    by_semantics: dict[tuple[bool, ...], MacroApplication] = {}
    for args in _argument_candidates(macro, pools):
        program = instantiate_macro(macro, args)
        if program.output_type is not ProbeType.BOOL:
            continue
        row = typed_prediction_row(program, values_by_hypothesis)
        semantic_key = _semantic_key(row, hypothesis_ids)
        info = _row_information(row, posterior)
        app = MacroApplication(macro.macro_id, program, info, semantic_key, float(macro.compression_gain))
        prior = by_semantics.get(semantic_key)
        if prior is None or (program.execution_cost, program.probe_id) < (prior.program.execution_cost, prior.program.probe_id):
            by_semantics[semantic_key] = app
    ranked = sorted(
        by_semantics.values(),
        key=lambda app: (-app.information_gain, app.program.execution_cost, app.program.probe_id),
    )
    return tuple(ranked[: max(1, int(max_applications))])


def discover_composed_macro_probe(
    macros: Sequence[ProbeMacro],
    atom_pools: Mapping[ProbeType, Sequence[str]],
    posterior: Mapping[str, float],
    atom_values_by_hypothesis: Mapping[str, Mapping[str, int | bool]],
    *,
    argument_pools_by_macro: Mapping[str, Mapping[ProbeType, Sequence[str]]] | None = None,
    macro_states: Mapping[str, MacroCompetitionState] | None = None,
    observed_probe_ids: Sequence[str] = (),
    connectives: Sequence[str] = ('and', 'or', 'xor', 'equiv'),
    max_applications_per_macro: int = 12,
    max_composition_candidates: int = 256,
    min_synergy: float = 0.02,
    counterexample_check: Callable[[TypedProbe], bool] | None = None,
) -> CompositionDiscoveryDecision:
    """Synthesize a cross-macro probe and reject it if a counterexample falsifies it.

    This is deliberately a bounded search layer. It composes *different* learned
    macros, requires a semantic partition improvement over either parent, keeps
    R2.41 quarantine boundaries, and uses a held-out callback as a CEGIS filter.
    """
    if int(max_applications_per_macro) <= 0 or int(max_composition_candidates) <= 0:
        raise ValueError('candidate budgets must be positive')
    min_synergy = float(min_synergy)
    if not 0.0 <= min_synergy <= 1.0:
        raise ValueError('min_synergy must be in [0,1]')

    hypothesis_ids = tuple(sorted(map(str, atom_values_by_hypothesis)))
    if not hypothesis_ids:
        raise ValueError('hypotheses must be non-empty')
    post = _normalize_posterior(posterior, hypothesis_ids)
    trusted = _trusted_macros(macros, macro_states)
    if len(trusted) < 2:
        return CompositionDiscoveryDecision('abstain', None, (), None, None, 0.0, 0.0, 0.0, 0, 0, (), 'need_two_trusted_macros')

    applications: dict[str, tuple[MacroApplication, ...]] = {}
    for macro in trusted:
        pools = atom_pools
        if argument_pools_by_macro is not None and macro.macro_id in argument_pools_by_macro:
            pools = argument_pools_by_macro[macro.macro_id]
        applications[macro.macro_id] = _applications_for_macro(
            macro, pools, post, atom_values_by_hypothesis, hypothesis_ids,
            max_applications=int(max_applications_per_macro),
        )

    connective_names = tuple(sorted({str(name).strip().lower() for name in connectives}))
    unknown = [name for name in connective_names if name not in _CONNECTIVES]
    if unknown:
        raise ValueError('unsupported connective: ' + ','.join(unknown))
    observed = frozenset(map(str, observed_probe_ids))
    candidates: list[ComposedMacroCandidate] = []
    seen_programs: set[str] = set()
    seen_semantics: set[tuple[bool, ...]] = set()
    evaluated = 0

    for left_index, left_macro in enumerate(trusted):
        for right_macro in trusted[left_index + 1:]:
            for left in applications[left_macro.macro_id]:
                for right in applications[right_macro.macro_id]:
                    for connective in connective_names:
                        if evaluated >= int(max_composition_candidates):
                            break
                        program = _CONNECTIVES[connective](left.program, right.program)
                        if program.probe_id in observed or program.probe_id in seen_programs:
                            continue
                        seen_programs.add(program.probe_id)
                        evaluated += 1
                        row = typed_prediction_row(program, atom_values_by_hypothesis)
                        semantic_key = _semantic_key(row, hypothesis_ids)
                        if semantic_key in seen_semantics:
                            continue
                        seen_semantics.add(semantic_key)
                        info = _row_information(row, post)
                        parent_info = max(left.information_gain, right.information_gain)
                        synergy = info - parent_info
                        if synergy + 1e-12 < min_synergy:
                            continue
                        macro_ids = tuple(sorted((left.macro_id, right.macro_id)))
                        compression = max(0.0, left.compression_gain) + max(0.0, right.compression_gain)
                        # Information dominates. Reuse is a small tie-breaker and
                        # execution cost prevents pathological giant compositions.
                        score = info + 0.35 * max(0.0, synergy) + 0.02 * math.log1p(compression) - 0.01 * program.execution_cost
                        payload = '|'.join((connective, *macro_ids, program.probe_id))
                        candidates.append(ComposedMacroCandidate(
                            'cm:' + _digest(payload), macro_ids, connective, program,
                            info, parent_info, synergy, score, semantic_key,
                        ))
                    if evaluated >= int(max_composition_candidates):
                        break
                if evaluated >= int(max_composition_candidates):
                    break
            if evaluated >= int(max_composition_candidates):
                break
        if evaluated >= int(max_composition_candidates):
            break

    candidates.sort(key=lambda c: (-c.score, -c.synergy, c.program.execution_cost, c.composition_id))
    if not candidates:
        return CompositionDiscoveryDecision('abstain', None, (), None, None, 0.0, 0.0, 0.0, evaluated, 0, (), 'no_positive_synergy_composition')

    check = counterexample_check or (lambda program: True)
    rejected: list[str] = []
    checked = 0
    for candidate in candidates:
        checked += 1
        if not bool(check(candidate.program)):
            rejected.append(candidate.composition_id)
            continue
        return CompositionDiscoveryDecision(
            'accept', candidate.composition_id, candidate.macro_ids, candidate.connective,
            candidate.program, candidate.information_gain, candidate.best_parent_information_gain,
            candidate.synergy, evaluated, checked, tuple(rejected), 'counterexample_surviving_composition',
        )
    return CompositionDiscoveryDecision(
        'abstain', None, (), None, None, 0.0, 0.0, 0.0, evaluated, checked,
        tuple(rejected), 'all_compositions_falsified',
    )
