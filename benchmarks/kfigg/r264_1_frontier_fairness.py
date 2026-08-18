from __future__ import annotations

from itertools import permutations

from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r264_unified_adaptive_repository_search import solve_unified_adaptive_repository_patch
from cogcoder.r264_unified_adaptive_repository_search_base import (
    solve_unified_adaptive_repository_patch as solve_accepted_r264,
)


HELDOUT_EPISODES = (6101, 6113, 6121, 6131, 6143, 6151)


def _candidate(candidate_id: str, source: str) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), (("main.py", source),), 0, 0)


def _macro() -> PatchMacro:
    return PatchMacro("r2641:floor-to-mod", "binop", "replace", "FloorDiv", "Mod", support=4)


def _starvation_candidates(seed: int, index: int) -> tuple[RepositoryPatchCandidate, ...]:
    rows = (
        _candidate(
            f"episode:{seed}:eliminated",
            f"a = {seed % 7}\n\ndef solve(x):\n    return x // 2 + (1 if x == 0 else 0)\n",
        ),
        _candidate(
            f"episode:{seed}:viable",
            "def solve(x):\n    return x // 2\n",
        ),
        _candidate(
            f"episode:{seed}:decoy",
            f"z = {seed % 5}\n\ndef solve(x):\n    return x // 4\n",
        ),
    )
    orderings = tuple(permutations(range(3)))
    order = orderings[index % len(orderings)]
    return tuple(rows[i] for i in order)


def _run_starvation(seed: int, index: int, solver, budget: int):
    candidates = _starvation_candidates(seed, index)
    diagnostics = (RepositoryProbe((0,)), RepositoryProbe((6,)))
    refinements = (RepositoryProbe((2,)),)
    finals = tuple(RepositoryProbe((x,)) for x in (3, 4, 7, 8, 11))
    return solver(
        candidates, (), diagnostics, lambda x: x % 2,
        refinement_inputs=refinements,
        final_verification_inputs=finals,
        expansion_seeds=candidates,
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=1,
        max_composition_depth=1,
        max_generated_candidates_per_round=budget,
        max_sites_per_macro=1,
    )


def _run_fallback(seed: int, index: int):
    rows = (
        _candidate(
            f"fallback:{seed}:repairable",
            "def solve(x):\n    return x // 2 + 10\n",
        ),
        _candidate(
            f"fallback:{seed}:live-b",
            "def solve(x):\n    return 10 if x == 4 else 12\n",
        ),
        _candidate(
            f"fallback:{seed}:live-c",
            "def solve(x):\n    return 10 if x == 4 else 18\n",
        ),
    )
    orderings = tuple(permutations(range(3)))
    order = orderings[(index + 2) % len(orderings)]
    candidates = tuple(rows[i] for i in order)
    diagnostics = (RepositoryProbe((4,)), RepositoryProbe((17,)))
    refinements = (RepositoryProbe((2,)),)
    finals = tuple(RepositoryProbe((x,)) for x in (3, 6, 7, 8, 11, 12))
    return solve_unified_adaptive_repository_patch(
        candidates, (), diagnostics, lambda x: x % 2 + 10,
        refinement_inputs=refinements,
        final_verification_inputs=finals,
        expansion_seeds=candidates,
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=1,
        max_composition_depth=1,
        max_generated_candidates_per_round=1,
        max_sites_per_macro=1,
    )


def run_benchmark() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for index, seed in enumerate(HELDOUT_EPISODES):
        base_tight = _run_starvation(seed, index, solve_accepted_r264, 1)
        hotfix_tight = _run_starvation(seed, index, solve_unified_adaptive_repository_patch, 1)
        hotfix_roomy = _run_starvation(seed, index, solve_unified_adaptive_repository_patch, 3)
        fallback = _run_fallback(seed, index)
        rows.append({
            "seed": seed,
            "accepted_r264_tight_status": base_tight.status,
            "accepted_r264_tight_exact": base_tight.exact,
            "hotfix_tight_status": hotfix_tight.status,
            "hotfix_tight_exact": hotfix_tight.exact,
            "hotfix_tight_generated": hotfix_tight.generated_candidates,
            "hotfix_tight_admitted": hotfix_tight.admitted_generated_candidates,
            "hotfix_roomy_status": hotfix_roomy.status,
            "hotfix_roomy_exact": hotfix_roomy.exact,
            "fallback_status": fallback.status,
            "fallback_exact": fallback.exact,
            "fallback_generated": fallback.generated_candidates,
            "fallback_admitted": fallback.admitted_generated_candidates,
            "target_output_leakage": (
                hotfix_tight.generation_used_target_outputs
                or hotfix_roomy.generation_used_target_outputs
                or fallback.generation_used_target_outputs
            ),
            "false_terminal_accepts": (
                hotfix_tight.false_terminal_accepts
                + hotfix_roomy.false_terminal_accepts
                + fallback.false_terminal_accepts
            ),
            "verification_failures": (
                hotfix_tight.verification_failures
                + hotfix_roomy.verification_failures
                + fallback.verification_failures
            ),
        })

    summary = {
        "episodes": len(rows),
        "accepted_r264_tight_abstains": sum(r["accepted_r264_tight_status"] == "abstain" for r in rows),
        "hotfix_tight_exact": sum(bool(r["hotfix_tight_exact"]) for r in rows),
        "hotfix_roomy_exact": sum(bool(r["hotfix_roomy_exact"]) for r in rows),
        "fallback_exact": sum(bool(r["fallback_exact"]) for r in rows),
        "tight_one_generated_each": sum(int(r["hotfix_tight_generated"]) == 1 for r in rows),
        "tight_one_admitted_each": sum(int(r["hotfix_tight_admitted"]) == 1 for r in rows),
        "fallback_one_generated_each": sum(int(r["fallback_generated"]) == 1 for r in rows),
        "fallback_one_admitted_each": sum(int(r["fallback_admitted"]) == 1 for r in rows),
        "target_output_leakage": any(bool(r["target_output_leakage"]) for r in rows),
        "false_terminal_accepts": sum(int(r["false_terminal_accepts"]) for r in rows),
        "verification_failures": sum(int(r["verification_failures"]) for r in rows),
        "trainable_parameter_count": 0,
    }
    gates = {
        "accepted_r264_reproduces_starvation": summary["accepted_r264_tight_abstains"] == len(rows),
        "hotfix_repairs_all_tight_cases": summary["hotfix_tight_exact"] == len(rows),
        "roomy_control_remains_exact": summary["hotfix_roomy_exact"] == len(rows),
        "repairable_ancestor_fallback_preserved": summary["fallback_exact"] == len(rows),
        "tight_budget_respected": (
            summary["tight_one_generated_each"] == len(rows)
            and summary["tight_one_admitted_each"] == len(rows)
        ),
        "fallback_budget_respected": (
            summary["fallback_one_generated_each"] == len(rows)
            and summary["fallback_one_admitted_each"] == len(rows)
        ),
        "target_output_free_generation": summary["target_output_leakage"] is False,
        "zero_false_terminal_accepts": summary["false_terminal_accepts"] == 0,
        "zero_verification_failures": summary["verification_failures"] == 0,
        "zero_trainable_parameters": True,
    }
    return {
        "schema_version": 1,
        "milestone": "R2.64.1 Frontier Fairness Hotfix",
        "capability": "evidence-aware-live-frontier-first-bounded-generation-with-repair-fallback",
        "claim_boundary": (
            "Correctness hardening of accepted R2.64 bounded trusted-PatchMacro scheduling. "
            "No new patch language, oracle channel, target-output generation channel, effectful autonomy, or AGI claim."
        ),
        "heldout_episodes": list(HELDOUT_EPISODES),
        "rows": rows,
        "summary": summary,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
        "trainable_parameter_count": 0,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
