from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmarks.codeworld.r211_multifile_cases import build_r211_cases
from cogcoder.r211_counterfactual_localizer import CounterfactualLocalizer
from cogcoder.r211_multifile_runtime import run_multifile_repair
from scripts.train_r210_copy_edit_proposer import load_r210_proposer

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / 'research' / 'R2_11_PRE_MEASURE_LOCK.json'


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_r211(checkpoint: Path) -> dict[str, object]:
    lock = json.loads(LOCK_PATH.read_text())
    for relative, expected in lock['source_freeze'].items():
        actual = _sha(ROOT / relative)
        if actual != expected:
            raise RuntimeError(f'R2.11 frozen source drift: {relative}: {actual} != {expected}')
    protocol = lock['protocol']
    cases = build_r211_cases(
        seed=int(protocol['heldout_seed']),
        count=int(protocol['cases']),
        providers=int(protocol['providers_per_repo']),
        offpath=int(protocol['offpath_symbols']),
        identity_variant='base',
    )
    renamed = build_r211_cases(
        seed=int(protocol['heldout_seed']),
        count=int(protocol['cases']),
        providers=int(protocol['providers_per_repo']),
        offpath=int(protocol['offpath_symbols']),
        identity_variant='renamed',
    )
    proposer = load_r210_proposer(checkpoint)
    hybrid = CounterfactualLocalizer(
        proposer,
        coverage_weight=2.0,
        behavior_weight=float(protocol['behavior_weight']),
        edit_gain_weight=float(protocol['edit_gain_weight']),
    )
    spectrum = CounterfactualLocalizer(
        proposer,
        coverage_weight=2.0,
        behavior_weight=0.0,
        edit_gain_weight=0.0,
    )

    hit1 = hit3 = baseline_hit1 = 0
    reciprocal = 0.0
    hybrid_solves = baseline_solves = 0
    invariant = false_accepts = 0
    max_patch_evals = 0
    rows: list[dict[str, object]] = []

    for case, renamed_case in zip(cases, renamed):
        ranked = hybrid.rank(
            case.symbols,
            graph=case.graph,
            failing_test_node=case.failing_test_node,
            language='javascript',
            probes=case.probes,
            probes_by_node=case.probes_by_node,
            coverage=case.coverage,
        )
        baseline_ranked = spectrum.rank(
            case.symbols,
            graph=case.graph,
            failing_test_node=case.failing_test_node,
            language='javascript',
            probes=case.probes,
            probes_by_node=case.probes_by_node,
            coverage=case.coverage,
        )
        renamed_ranked = hybrid.rank(
            renamed_case.symbols,
            graph=renamed_case.graph,
            failing_test_node=renamed_case.failing_test_node,
            language='javascript',
            probes=renamed_case.probes,
            probes_by_node=renamed_case.probes_by_node,
            coverage=renamed_case.coverage,
        )
        ids = [item.node_id for item in ranked]
        baseline_ids = [item.node_id for item in baseline_ranked]
        position = ids.index(case.gold_node_id) + 1
        baseline_position = baseline_ids.index(case.gold_node_id) + 1
        hit1 += int(position == 1)
        hit3 += int(position <= 3)
        baseline_hit1 += int(baseline_position == 1)
        reciprocal += 1.0 / position

        base_fp_order = [item.canonical_fingerprint for item in ranked]
        renamed_fp_order = [item.canonical_fingerprint for item in renamed_ranked]
        same = base_fp_order == renamed_fp_order
        invariant += int(same)

        h_outcome = run_multifile_repair(
            case,
            proposer,
            localizer=hybrid,
            patch_budget=int(protocol['patch_evaluation_budget']),
        )
        b_outcome = run_multifile_repair(
            case,
            proposer,
            localizer=spectrum,
            patch_budget=int(protocol['patch_evaluation_budget']),
        )
        hybrid_solves += int(h_outcome.success)
        baseline_solves += int(b_outcome.success)
        for outcome in (h_outcome, b_outcome):
            if outcome.patch_outcome is not None:
                max_patch_evals = max(max_patch_evals, outcome.patch_outcome.evaluations)
                false_accepts += int(outcome.patch_outcome.success and not outcome.patch_outcome.best_result.success)
        rows.append({
            'case': case.name,
            'family': case.family,
            'gold_position': position,
            'baseline_gold_position': baseline_position,
            'hybrid_success': h_outcome.success,
            'baseline_success': b_outcome.success,
            'identity_invariant': same,
        })

    count = len(cases)
    hit1_rate = hit1 / count
    hit3_rate = hit3 / count
    mrr = reciprocal / count
    baseline_hit1_rate = baseline_hit1 / count
    hybrid_rate = hybrid_solves / count
    baseline_rate = baseline_solves / count
    hit1_gain_pp = (hit1_rate - baseline_hit1_rate) * 100.0
    solve_gain_pp = (hybrid_rate - baseline_rate) * 100.0
    invariance_rate = invariant / count
    acceptance = lock['acceptance']
    gate = all((
        hit1_rate >= float(acceptance['localization_hit1_min']),
        mrr >= float(acceptance['localization_mrr_min']),
        hit3_rate >= float(acceptance['localization_hit3_min']),
        hit1_gain_pp >= float(acceptance['hit1_improvement_over_spectrum_pp_min']),
        hybrid_rate >= float(acceptance['integrated_verified_solve_rate_min']),
        solve_gain_pp >= float(acceptance['solve_improvement_over_spectrum_pp_min']),
        invariance_rate >= float(acceptance['identity_permutation_invariance_min']),
        false_accepts <= int(acceptance['false_terminal_accepts_max']),
        max_patch_evals <= int(acceptance['max_patch_evaluations_per_case']),
    ))
    return {
        'milestone': 'R2.11 Differential Multi-File Localization',
        'phase': 'A',
        'cases': count,
        'localization_hit1': hit1_rate,
        'localization_hit3': hit3_rate,
        'localization_mrr': mrr,
        'spectrum_baseline_hit1': baseline_hit1_rate,
        'hit1_improvement_over_spectrum_pp': hit1_gain_pp,
        'integrated_verified_solve_rate': hybrid_rate,
        'spectrum_baseline_verified_solve_rate': baseline_rate,
        'solve_improvement_over_spectrum_pp': solve_gain_pp,
        'identity_permutation_invariance': invariance_rate,
        'false_terminal_accepts': false_accepts,
        'max_patch_evaluations_observed': max_patch_evals,
        'new_r211_neural_parameters': 0,
        'candidate_effective_parameters': 79_450_489,
        'external_coding_claim_allowed': False,
        'agi_claim_allowed': False,
        'phase_a_gate_pass': gate,
        'rows': rows,
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(measure_r211(args.checkpoint), indent=2, sort_keys=True))
