from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import torch

from benchmarks.codeworld.r210_copy_edit_curriculum import build_r210_heldout_cases
from cogcoder.r210_copy_edit_features import encode_evidence
from cogcoder.r210_copy_edit_model import rank_candidates
from cogcoder.r29_patch_model import patch_fingerprint
from cogcoder.r29_patch_search import VerifierGuidedPatchSearch
from scripts.train_r210_copy_edit_proposer import load_r210_proposer

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / 'research' / 'R2_10_PRETRAIN_LOCK.json'


def _ranked_candidates(model, case):
    scores = rank_candidates(
        model,
        case.source,
        language=case.language,
        target_path='app.js',
        candidates=case.candidates,
        evidence_features=encode_evidence(case.probes),
    )
    ranked = tuple(
        replace(candidate, proposal_score=float(scores[index].item()))
        for index, candidate in enumerate(case.candidates)
    )
    return scores, ranked


def _run_search(case, candidates):
    return VerifierGuidedPatchSearch(budget=case.budget).search(
        case.snapshot,
        candidates,
        case.evaluator,
    )


def measure_r210_copy_edit(checkpoint_path: Path, *, cases_per_family: int = 24) -> dict[str, object]:
    lock = json.loads(LOCK_PATH.read_text(encoding='utf-8'))
    model = load_r210_proposer(Path(checkpoint_path))
    base_cases = build_r210_heldout_cases(
        seed=int(lock['protocol']['heldout_seed']),
        cases_per_family=cases_per_family,
        identifier_variant='base',
    )
    renamed_cases = build_r210_heldout_cases(
        seed=int(lock['protocol']['heldout_seed']),
        cases_per_family=cases_per_family,
        identifier_variant='renamed',
    )

    top1 = 0
    integrated_solves = 0
    baseline_solves = 0
    false_terminal = 0
    rename_invariant = 0
    rows: list[dict[str, object]] = []

    for case, renamed in zip(base_cases, renamed_cases):
        scores, ranked = _ranked_candidates(model, case)
        renamed_scores, _renamed_ranked = _ranked_candidates(model, renamed)
        prediction = int(scores.argmax().item())
        top1 += int(prediction == case.gold_index)
        base_order = torch.argsort(scores, descending=True).tolist()
        renamed_order = torch.argsort(renamed_scores, descending=True).tolist()
        invariant = base_order == renamed_order
        rename_invariant += int(invariant)

        learned_outcome = _run_search(case, ranked)
        baseline_candidates = tuple(replace(candidate, proposal_score=0.0) for candidate in case.candidates)
        baseline_outcome = _run_search(case, baseline_candidates)
        integrated_solves += int(learned_outcome.success)
        baseline_solves += int(baseline_outcome.success)
        false_terminal += int(learned_outcome.success and not learned_outcome.best_result.success)

        rows.append(
            {
                'family': case.family,
                'template_seed': case.template_seed,
                'top1_correct': prediction == case.gold_index,
                'learned_success': learned_outcome.success,
                'baseline_success': baseline_outcome.success,
                'learned_evaluations': learned_outcome.evaluations,
                'baseline_evaluations': baseline_outcome.evaluations,
                'rename_invariant': invariant,
                'selected_fingerprint': patch_fingerprint(learned_outcome.candidate) if learned_outcome.candidate else None,
                'expected_fingerprint': case.expected_patch_fingerprint,
            }
        )

    count = len(base_cases)
    top1_accuracy = top1 / count
    integrated_rate = integrated_solves / count
    baseline_rate = baseline_solves / count
    improvement_pp = (integrated_rate - baseline_rate) * 100.0
    rename_rate = rename_invariant / count

    payload = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    new_params = int(payload['r210_copy_edit_delta']['proposer_parameters'])
    effective = int(payload['effective_parameters'])
    full_protocol = cases_per_family == int(lock['protocol']['heldout_cases_per_family'])
    acceptance = lock['acceptance']
    gate_pass = full_protocol and all(
        (
            top1_accuracy >= float(acceptance['top1_gold_candidate_accuracy_min']),
            integrated_rate >= float(acceptance['integrated_verified_solve_rate_min']),
            improvement_pp >= float(acceptance['improvement_over_unranked_baseline_pp_min']),
            rename_rate >= float(acceptance['rename_invariance_min']),
            false_terminal <= int(acceptance['false_terminal_accepts_max']),
            new_params <= int(lock['new_r210_parameter_ceiling']),
            effective < int(lock['candidate_total_parameter_ceiling']),
        )
    )

    return {
        'milestone': 'R2.10 Compact Copy-Edit Proposer',
        'phase': 'A',
        'cases': count,
        'top1_gold_candidate_accuracy': top1_accuracy,
        'integrated_verified_solve_rate': integrated_rate,
        'unranked_baseline_solve_rate': baseline_rate,
        'improvement_over_unranked_baseline_pp': improvement_pp,
        'rename_invariance': rename_rate,
        'false_terminal_accepts': false_terminal,
        'new_r210_neural_parameters': new_params,
        'candidate_effective_parameters': effective,
        'external_coding_claim_allowed': False,
        'agi_claim_allowed': False,
        'phase_a_gate_pass': gate_pass,
        'rows': rows,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--cases-per-family', type=int, default=24)
    args = parser.parse_args()
    print(json.dumps(measure_r210_copy_edit(args.checkpoint, cases_per_family=args.cases_per_family), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
