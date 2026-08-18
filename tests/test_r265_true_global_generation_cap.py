from __future__ import annotations

from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
import cogcoder.r265_verified_patch_primitive_induction as r265


def _candidate(candidate_id: str, target_op: str) -> RepositoryPatchCandidate:
    symbol = {'Add': '+', 'Sub': '-', 'Mult': '*'}[target_op]
    files = {
        'a_target.py': f'def target(x, y):\n    return x {symbol} y\n',
        'entry.py': (
            'from a_target import target\n'
            'from z_aux import aux\n\n'
            'def solve(x, y):\n'
            '    aux(x, y)\n'
            '    return target(x, y)\n'
        ),
        'z_aux.py': 'def aux(x, y):\n    return x + y\n',
    }
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, 0)


def _oracle(x: int, y: int) -> int:
    return x * y


def _grammar() -> r265.PatchPrimitiveGrammar:
    return r265.PatchPrimitiveGrammar(
        allowed_slots=('binop',),
        allowed_operations=('replace',),
        allowed_target_values=('FloorDiv', 'Mod', 'Mult'),
        max_hypotheses=16,
    )


def _case(max_generated_candidates: int):
    source = _candidate('caller:source', 'Add')
    wrong = _candidate('caller:wrong', 'Sub')
    diagnostic = (RepositoryProbe((5, 2)),)
    challenges = tuple(RepositoryProbe(args) for args in ((4, 3), (7, 2), (9, 4), (-3, 5)))
    learning = {(5, 2), (4, 3), (7, 2), (9, 4), (-3, 5)}
    final = tuple(
        RepositoryProbe((x, y))
        for x in (-11, -7, -2, 1, 3, 6, 10)
        for y in (-5, -2, 1, 4, 8)
        if (x, y) not in learning
    )
    return r265.solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, _oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        grammar=_grammar(),
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=len(challenges),
        max_generated_candidates=max_generated_candidates,
        max_sites_per_hypothesis=16,
        min_independent_challenges=4,
    )


def test_true_global_generation_cap_preserves_hypothesis_fairness() -> None:
    source = _candidate('caller:source', 'Add')
    hypotheses = r265.enumerate_patch_macro_hypotheses((source,), _grammar())
    rows = r265._generate_hypothesis_fair_candidates(
        (source,), hypotheses,
        max_generated_candidates=3,
        max_sites_per_hypothesis=16,
    )
    assert len(rows) == 3
    assert [row.macro.target_value for row in rows] == ['FloorDiv', 'Mod', 'Mult']


def test_true_global_generation_cap_bounds_upstream_generation_work(monkeypatch) -> None:
    real_expand = r265.expand_repository_candidates
    upstream_returned = 0
    call_caps: list[int] = []

    def counted_expand(seeds, macros, *, max_generated_candidates, max_sites_per_macro):
        nonlocal upstream_returned
        call_caps.append(int(max_generated_candidates))
        rows = real_expand(
            seeds,
            macros,
            max_generated_candidates=max_generated_candidates,
            max_sites_per_macro=max_sites_per_macro,
        )
        upstream_returned += len(rows)
        return rows

    monkeypatch.setattr(r265, 'expand_repository_candidates', counted_expand)
    result = _case(3)

    assert result.status == 'accept'
    assert result.exact is True
    assert result.generated_candidates <= 3
    assert sum(call_caps) <= 3
    assert upstream_returned <= 3
