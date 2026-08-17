from __future__ import annotations

import itertools
import random
from dataclasses import asdict, dataclass

from cogcoder.r239_predicate_macros import ProbeMacro, instantiate_macro
from cogcoder.r239_typed_probe_dsl import (
    ProbeType,
    and_probe,
    bool_atom,
    equiv_probe,
    evaluate_typed_probe,
    or_probe,
    xor_probe,
)
from cogcoder.r243_macro_composition import discover_composed_macro_probe

DEV_SEEDS = (1201, 1213, 1223, 1231, 1249, 1259, 1277, 1283)
HELDOUT_SEEDS = (1301, 1303, 1307, 1319, 1321, 1327)
_BOOL_OPS = (and_probe, equiv_probe, or_probe, xor_probe)


def _macro(mid: str, op) -> ProbeMacro:
    template = op(bool_atom('$p0'), bool_atom('$p1'))
    return ProbeMacro(
        macro_id=mid,
        template=template,
        parameter_types=(ProbeType.BOOL, ProbeType.BOOL),
        support=6,
        compression_gain=5.0,
        raw_mdl_cost=template.mdl_cost,
        call_mdl_cost=2,
    )


def learned_macros() -> tuple[ProbeMacro, ProbeMacro]:
    # These abstractions originate in separate source families. The target family
    # never stores the combined structure as a learned macro.
    return (
        _macro('pm:source-left-and', and_probe),
        _macro('pm:source-right-or', or_probe),
    )


def _renamed_roles(seed: int) -> dict[str, str]:
    rng = random.Random(int(seed))
    names = [f'n{seed}_{i}' for i in range(4)]
    rng.shuffle(names)
    return dict(zip(('a', 'b', 'c', 'd'), names))


def _env(roles: dict[str, str], a: bool, b: bool, c: bool, d: bool) -> dict[str, bool]:
    return {roles['a']: a, roles['b']: b, roles['c']: c, roles['d']: d}


def _truth_table(roles: dict[str, str]):
    for bits in itertools.product((False, True), repeat=4):
        a, b, c, d = bits
        yield _env(roles, a, b, c, d), bool((a and b) and (c or d))


def _exact_target(program, roles: dict[str, str]) -> bool:
    return all(bool(evaluate_typed_probe(program, env)) == expected for env, expected in _truth_table(roles))


def _semantic_signature(program, roles: dict[str, str]) -> tuple[bool, ...]:
    return tuple(bool(evaluate_typed_probe(program, env)) for env, _ in _truth_table(roles))


def raw_recombination_semantic_space_size(roles: dict[str, str]) -> int:
    """Count unique depth-3 boolean recombinations without learned family scopes.

    Raw search must rediscover both inner relations and the outer relation. This
    grammar is intentionally the same boolean operator family available to the
    composer, but it receives no macro identity or family-specific argument scope.
    """
    atoms = tuple(bool_atom(roles[r]) for r in ('a', 'b', 'c', 'd'))
    inner = {}
    for left, right in itertools.combinations(atoms, 2):
        for op in _BOOL_OPS:
            program = op(left, right)
            inner.setdefault(_semantic_signature(program, roles), program)
    programs = list(inner.values())
    semantics = set()
    for left, right in itertools.combinations(programs, 2):
        for op in _BOOL_OPS:
            semantics.add(_semantic_signature(op(left, right), roles))
    return len(semantics)


@dataclass(frozen=True)
class EpisodeResult:
    seed: int
    accepted: bool
    exact_truth_table: bool
    false_accept: bool
    selected_macro_ids: tuple[str, ...]
    connective: str | None
    information_gain: float
    best_parent_information_gain: float
    synergy: float
    composition_candidates_evaluated: int
    counterexamples_checked: int
    raw_semantic_space_size: int
    left_parent_exact: bool
    right_parent_exact: bool


def run_episode(seed: int) -> EpisodeResult:
    seed = int(seed)
    roles = _renamed_roles(seed)
    macros = learned_macros()

    semantic_rows = {
        'h0': (True, True, True, False),
        'h1': (True, True, False, False),
        'h2': (True, False, False, True),
        'h3': (False, False, False, False),
    }
    values = {hid: _env(roles, *bits) for hid, bits in semantic_rows.items()}
    h0 = 0.54 + 0.01 * (seed % 5)
    h1 = 0.14
    h2 = 0.13
    posterior = {'h0': h0, 'h1': h1, 'h2': h2, 'h3': 1.0 - h0 - h1 - h2}
    scopes = {
        macros[0].macro_id: {ProbeType.BOOL: (roles['a'], roles['b'])},
        macros[1].macro_id: {ProbeType.BOOL: (roles['c'], roles['d'])},
    }

    result = discover_composed_macro_probe(
        macros,
        {ProbeType.BOOL: tuple(roles.values())},
        posterior,
        values,
        argument_pools_by_macro=scopes,
        max_applications_per_macro=4,
        max_composition_candidates=16,
        min_synergy=0.02,
        counterexample_check=lambda program: _exact_target(program, roles),
    )

    left = instantiate_macro(macros[0], (bool_atom(roles['a']), bool_atom(roles['b'])))
    right = instantiate_macro(macros[1], (bool_atom(roles['c']), bool_atom(roles['d'])))
    exact = result.program is not None and _exact_target(result.program, roles)
    return EpisodeResult(
        seed=seed,
        accepted=result.status == 'accept',
        exact_truth_table=bool(exact),
        false_accept=result.status == 'accept' and not bool(exact),
        selected_macro_ids=result.selected_macro_ids,
        connective=result.connective,
        information_gain=result.information_gain,
        best_parent_information_gain=result.best_parent_information_gain,
        synergy=result.synergy,
        composition_candidates_evaluated=result.candidates_evaluated,
        counterexamples_checked=result.counterexamples_checked,
        raw_semantic_space_size=raw_recombination_semantic_space_size(roles),
        left_parent_exact=_exact_target(left, roles),
        right_parent_exact=_exact_target(right, roles),
    )


def run_suite(seeds=HELDOUT_SEEDS) -> list[dict]:
    return [asdict(run_episode(seed)) for seed in tuple(seeds)]
