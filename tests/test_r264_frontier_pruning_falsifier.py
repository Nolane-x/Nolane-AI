from __future__ import annotations

from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r264_unified_adaptive_repository_search import solve_unified_adaptive_repository_patch


def _candidate(candidate_id: str, source: str) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), (("main.py", source),), 0, 0)


def _macro() -> PatchMacro:
    return PatchMacro("r264:falsifier:floor-to-mod", "binop", "replace", "FloorDiv", "Mod", support=4)


def _oracle(x: int) -> int:
    return x % 2


def _run(generation_budget: int):
    # At diagnostic x=0, A is eliminated while B/C survive. At x=6 the oracle
    # lies outside the B/C version space, so expansion must be rooted only in
    # those still-live hypotheses. A is deliberately lexicographically first
    # after mutation; a stale pre-filter frontier lets A consume the first slot.
    eliminated = _candidate(
        "caller:A-eliminated",
        "a = 0\n\ndef solve(x):\n    return x // 2 + (1 if x == 0 else 0)\n",
    )
    viable = _candidate(
        "caller:B-viable",
        "def solve(x):\n    return x // 2\n",
    )
    survivor_decoy = _candidate(
        "caller:C-survivor-decoy",
        "z = 0\n\ndef solve(x):\n    return x // 4\n",
    )
    diagnostic = (RepositoryProbe((0,)), RepositoryProbe((6,)))
    refinement = (RepositoryProbe((2,)),)
    final = tuple(RepositoryProbe((x,)) for x in (3, 4, 7, 8, 11))
    return solve_unified_adaptive_repository_patch(
        (eliminated, viable, survivor_decoy),
        (),
        diagnostic,
        _oracle,
        refinement_inputs=refinement,
        final_verification_inputs=final,
        expansion_seeds=(eliminated, viable, survivor_decoy),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=1,
        max_composition_depth=1,
        max_generated_candidates_per_round=generation_budget,
        max_sites_per_macro=1,
    )


def test_target_is_expressible_when_stale_candidate_cannot_starve_the_budget() -> None:
    roomy = _run(3)
    assert roomy.status == "accept"
    assert roomy.exact is True
    assert roomy.candidate is not None
    assert "x % 2" in dict(roomy.candidate.files)["main.py"]
    assert roomy.diagnostic_counterexamples == 1
    assert roomy.false_terminal_accepts == 0
    assert roomy.verification_failures == 0


def test_eliminated_diagnostic_candidates_do_not_consume_later_expansion_budget() -> None:
    tight = _run(1)
    assert tight.status == "accept"
    assert tight.exact is True
    assert tight.candidate is not None
    assert "x % 2" in dict(tight.candidate.files)["main.py"]
    assert tight.diagnostic_counterexamples == 1
    assert tight.expansion_round_count == 1
    assert tight.generated_candidates == 1
    assert tight.admitted_generated_candidates == 1
    assert tight.false_terminal_accepts == 0
    assert tight.verification_failures == 0
