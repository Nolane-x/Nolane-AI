from __future__ import annotations

from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r264_unified_adaptive_repository_search import solve_unified_adaptive_repository_patch


def _candidate(candidate_id: str, source: str) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), (("main.py", source),), 0, 0)


def _macro() -> PatchMacro:
    return PatchMacro("r264:independent:floor-to-mod", "binop", "replace", "FloorDiv", "Mod", support=4)


def _starvation_case(generation_budget: int):
    eliminated = _candidate(
        "caller:A-eliminated",
        "a = 0\n\ndef solve(x):\n    return x // 2 + (1 if x == 0 else 0)\n",
    )
    viable = _candidate(
        "caller:B-viable",
        "def solve(x):\n    return x // 2\n",
    )
    decoy = _candidate(
        "caller:C-survivor-decoy",
        "z = 0\n\ndef solve(x):\n    return x // 4\n",
    )
    diagnostic = (RepositoryProbe((0,)), RepositoryProbe((6,)))
    refinement = (RepositoryProbe((2,)),)
    final = tuple(RepositoryProbe((x,)) for x in (3, 4, 7, 8, 11))

    def oracle(x: int) -> int:
        return x % 2

    return solve_unified_adaptive_repository_patch(
        (eliminated, viable, decoy), (), diagnostic, oracle,
        refinement_inputs=refinement,
        final_verification_inputs=final,
        expansion_seeds=(eliminated, viable, decoy),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=1,
        max_composition_depth=1,
        max_generated_candidates_per_round=generation_budget,
        max_sites_per_macro=1,
    )


def test_live_survivor_gets_tight_generation_slot() -> None:
    control = _starvation_case(3)
    assert control.status == "accept" and control.exact is True
    tight = _starvation_case(1)
    assert tight.status == "accept"
    assert tight.exact is True
    assert tight.candidate is not None
    assert "x % 2" in dict(tight.candidate.files)["main.py"]
    assert tight.generated_candidates == 1
    assert tight.admitted_generated_candidates == 1
    assert tight.false_terminal_accepts == 0
    assert tight.verification_failures == 0


def test_repairable_contradicted_ancestor_is_bounded_fallback() -> None:
    ancestor = _candidate(
        "caller:A-repairable-ancestor",
        "def solve(x):\n    return x // 2 + 10\n",
    )
    live_b = _candidate(
        "caller:B-live-no-site",
        "def solve(x):\n    return 10 if x == 4 else 12\n",
    )
    live_c = _candidate(
        "caller:C-live-no-site",
        "def solve(x):\n    return 10 if x == 4 else 18\n",
    )
    diagnostic = (RepositoryProbe((4,)), RepositoryProbe((17,)))
    refinement = (RepositoryProbe((2,)),)
    final = tuple(RepositoryProbe((x,)) for x in (3, 6, 7, 8, 11, 12))

    def oracle(x: int) -> int:
        return x % 2 + 10

    result = solve_unified_adaptive_repository_patch(
        (ancestor, live_b, live_c), (), diagnostic, oracle,
        refinement_inputs=refinement,
        final_verification_inputs=final,
        expansion_seeds=(ancestor, live_b, live_c),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=1,
        max_composition_depth=1,
        max_generated_candidates_per_round=1,
        max_sites_per_macro=1,
    )
    assert result.status == "accept"
    assert result.exact is True
    assert result.candidate is not None
    assert "x % 2 + 10" in dict(result.candidate.files)["main.py"]
    assert result.generated_candidates == 1
    assert result.admitted_generated_candidates == 1
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0


def test_generation_remains_target_output_free_and_bounded() -> None:
    result = _starvation_case(1)
    assert result.generation_used_target_outputs is False
    assert result.generated_candidates <= 1
    assert result.expansion_round_count <= 1
