from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .arc_grid import Grid
from .arc_local import fit_local_programs
from .arc_ops_view import Program, Step
from .arc_pair_v2 import fit_pair_programs
from .component_fit import programs as component_programs
from .r25_n2 import _program_set as frozen_program_set
from .r26_firewall import Evidence, validate_family
from .r26_legend import programs as legend_programs
from .r26_ops import apply_program
from .r26_structural import programs as structural_programs
from .span_fit import programs as span_programs

Pair = tuple[Grid, Grid]
Infer = Callable[[tuple[Pair, ...]], tuple[Program, ...]]


@dataclass(frozen=True)
class Candidate:
    program: Program
    evidence: Evidence
    legacy: bool
    family: str


def _local(pairs: tuple[Pair, ...]) -> tuple[Program, ...]:
    return tuple(fit_local_programs(pairs, max_rules=8))


def _pair(pairs: tuple[Pair, ...]) -> tuple[Program, ...]:
    return tuple(fit_pair_programs(pairs))


def _component(pairs: tuple[Pair, ...]) -> tuple[Program, ...]:
    return tuple(component_programs(pairs, max_items=4))


def _region(pairs: tuple[Pair, ...]) -> tuple[Program, ...]:
    pairs = tuple(pairs)
    if not pairs:
        return ()
    colors = sorted({color for _, target in pairs for color in target.colors})
    out: list[Program] = []
    for color in colors:
        program = Program((Step('region_project', (int(color),)),), 3)
        try:
            exact = all(apply_program(program, inp) == target for inp, target in pairs)
        except (ValueError, ArithmeticError, OverflowError, StopIteration, TypeError):
            exact = False
        if exact:
            out.append(program)
    return tuple(out)


def _span(pairs: tuple[Pair, ...]) -> tuple[Program, ...]:
    return tuple(span_programs(pairs))


_LEGACY_FAMILIES: tuple[tuple[str, str, Infer], ...] = (
    ('local', 'local_rewrite', _local),
    ('pair', 'view_combine', _pair),
    ('component', 'object_rewrite', _component),
    ('region', 'region_project', _region),
    ('span', 'span', _span),
)

_NEW_FAMILIES: tuple[tuple[str, Infer], ...] = (
    ('structural', structural_programs),
    ('legend', legend_programs),
)


def _fully_robust(evidence: Evidence) -> bool:
    applicable = evidence.loeo_total + evidence.meta_total
    return (
        applicable > 0
        and evidence.loeo_passed == evidence.loeo_total
        and evidence.meta_passed == evidence.meta_total
    )


def _evidence_key(evidence: Evidence) -> tuple[float, float, int]:
    loeo = evidence.loeo_ratio if evidence.loeo_total else 0.0
    meta = evidence.meta_ratio if evidence.meta_total else 0.0
    return loeo, meta, evidence.loeo_total + evidence.meta_total


def rank_candidates(candidates, *, limit: int = 64) -> tuple[Candidate, ...]:
    if limit < 1 or limit > 64:
        raise ValueError('R2.6 candidate limit must be in 1..64')
    unique: dict[tuple, Candidate] = {}
    for candidate in candidates:
        signature = candidate.program.signature
        current = unique.get(signature)
        if current is None:
            unique[signature] = candidate
            continue
        current_key = (not current.legacy, *_evidence_key(current.evidence))
        new_key = (not candidate.legacy, *_evidence_key(candidate.evidence))
        if new_key > current_key:
            unique[signature] = candidate
    return tuple(
        sorted(
            unique.values(),
            key=lambda candidate: (
                1 if candidate.legacy else 0,
                -candidate.evidence.loeo_ratio if candidate.evidence.loeo_total else 0.0,
                -candidate.evidence.meta_ratio if candidate.evidence.meta_total else 0.0,
                -(candidate.evidence.loeo_total + candidate.evidence.meta_total),
                candidate.program.cost,
                len(candidate.program.steps),
                candidate.family,
                repr(candidate.program.signature),
            ),
        )[:limit]
    )


def program_set(pairs, limit: int = 64) -> tuple[Candidate, ...]:
    pairs = tuple(pairs)
    if not pairs:
        return ()
    if limit < 1 or limit > 64:
        raise ValueError('R2.6 limit must be in 1..64')

    frozen = tuple(frozen_program_set(pairs, limit=limit))
    frozen_signatures = {program.signature for program in frozen}
    present_ops = {
        program.steps[0].op
        for program in frozen
        if program.steps
    }
    pool: list[Candidate] = [
        Candidate(program, Evidence(0, 0, 0, 0), True, 'legacy-r2.5')
        for program in frozen
    ]

    for family, op, infer in _LEGACY_FAMILIES:
        if op not in present_ops:
            continue
        programs = tuple(infer(pairs))
        if not programs:
            continue
        evidence = validate_family(infer, pairs)
        if not _fully_robust(evidence):
            continue
        for program in programs:
            if program.signature in frozen_signatures:
                pool.append(Candidate(program, evidence, False, family))

    for family, infer in _NEW_FAMILIES:
        programs = tuple(infer(pairs))
        if not programs:
            continue
        evidence = validate_family(infer, pairs)
        if not _fully_robust(evidence):
            continue
        pool.extend(Candidate(program, evidence, False, family) for program in programs)

    return rank_candidates(pool, limit=limit)
