#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmarks.kfigg.r218_cross_domain_transfer import run_r218
from cogcoder.r218_periodic_invariant import AES_CORE_DECOYS, NIST_AES128_KEY, NIST_AES128_WORDS

ROOT = Path('.')
LOCK_PATH = ROOT / 'research/R2_18_PRE_HELDOUT_LOCK.json'
HELDOUT_PATH = ROOT / 'research/R2_18_HELDOUT_RAW.json'
PREREG_PATH = ROOT / 'research/R2_18_WORLD_PREREGISTRATION.json'
POST_PATH = ROOT / 'research/R2_18_WORLD_POST_EXECUTION.json'
OUT_PATH = ROOT / 'research/R2_18_VERIFY_RESULT.json'


def sha256_path(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_payload_hash(payload: dict) -> str:
    body = dict(payload)
    body.pop('canonical_payload_sha256', None)
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def canonical_json_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main() -> int:
    lock = json.loads(LOCK_PATH.read_text())
    heldout = json.loads(HELDOUT_PATH.read_text())
    prereg = json.loads(PREREG_PATH.read_text())
    post = json.loads(POST_PATH.read_text())

    checks: dict[str, bool] = {}
    checks['lock_canonical_hash'] = canonical_payload_hash(lock) == lock['canonical_payload_sha256']
    checks['heldout_canonical_hash'] = canonical_payload_hash(heldout) == heldout['canonical_payload_sha256']
    checks['heldout_seeds_match_lock'] = heldout['seeds'] == lock['heldout_seeds']
    checks['heldout_not_executed_at_lock'] = lock['heldout_executed_at_lock_time'] is False

    frozen_mismatches: dict[str, dict[str, str]] = {}
    for path, expected in lock['frozen_files_sha256'].items():
        actual = sha256_path(path)
        if actual != expected:
            frozen_mismatches[path] = {'expected': expected, 'actual': actual}
    checks['frozen_decision_files_match'] = not frozen_mismatches

    replay_rows = []
    exact_replay = True
    for frozen in heldout['executions']:
        reproduced = run_r218(int(frozen['seed']))
        match = reproduced == frozen
        exact_replay &= match
        replay_rows.append({
            'seed': frozen['seed'],
            'exact_match': match,
            'frozen_sha256': canonical_json_hash(frozen),
            'reproduced_sha256': canonical_json_hash(reproduced),
        })
    checks['exact_heldout_replay'] = exact_replay
    checks['all_heldout_accepted'] = heldout['all_accepted'] and all(row['status'] == 'accepted' for row in heldout['executions'])
    checks['all_heldout_gates_pass'] = heldout['all_gates_pass'] and all(row['all_gates_pass'] for row in heldout['executions'])

    expected_predictions = {
        'r218-p1-external-transfer',
        'r218-p2-local-quarantine',
        'r218-p3-dedup-capacity',
        'r218-p4-rollback',
    }
    registered = {row['event']['prediction_id'] for row in prereg['prediction_events']}
    checks['world_preregistered_all_predictions'] = registered == expected_predictions
    checks['world_prereg_audit_valid'] = bool(prereg['audit']['valid'])
    checks['world_prereg_checkpoint_verified'] = bool(prereg['checkpoint']['verified'])
    checks['world_prereg_says_no_heldout'] = prereg['heldout_executed'] is False
    checks['world_experiment_accepted'] = bool(post['experiment']['accepted'])
    checks['world_prediction_precedes_experiment'] = bool(post['prediction_precedes_experiment']) and post['prediction_event_seq'] < post['experiment_accept_event_seq']
    checks['world_post_audit_valid'] = bool(post['audit']['valid'])
    checks['world_constitution_accepts_prediction_before_test'] = post['constitution_result'] == 'accepted_prediction_before_test'

    checks['nist_key_fixture_locked'] = NIST_AES128_KEY.hex() == '2b7e151628aed2a6abf7158809cf4f3c'
    checks['nist_word_fixture_locked'] = (
        len(NIST_AES128_WORDS) == 44
        and NIST_AES128_WORDS[:4] == (0x2B7E1516, 0x28AED2A6, 0xABF71588, 0x09CF4F3C)
        and NIST_AES128_WORDS[-4:] == (0xD014F9A8, 0xC9EE2589, 0xE13F0CC8, 0xB6630CA6)
    )
    checks['hard_decoy_count_locked'] = len(AES_CORE_DECOYS) == 4

    every_seed = heldout['executions']
    checks['external_unique_target_every_seed'] = all(
        row['external_transfer']['survivors'] == ['target_nist_fips197'] for row in every_seed
    )
    checks['core_ablation_falsifies_every_seed'] = all(
        row['external_transfer']['core_ablation_false_survivors'] >= 4 for row in every_seed
    )
    checks['local_quarantine_every_seed'] = all(
        row['negative_transfer']['alien_state'] == 'quarantined'
        and row['negative_transfer']['alien_route_after_failure'] == []
        and row['negative_transfer']['source_route_after_failure'] == 'active'
        for row in every_seed
    )
    checks['dedup_zero_capacity_delta_every_seed'] = all(
        row['deduplication']['capacity_before_duplicate'] == row['deduplication']['capacity_after_duplicate']
        and row['deduplication']['record_count_before_duplicate'] == row['deduplication']['record_count_after_duplicate']
        for row in every_seed
    )
    checks['bounded_capacity_every_seed'] = all(
        row['capacity_governance']['within_budget'] and row['capacity_governance']['target_skill_retained']
        for row in every_seed
    )
    checks['rollback_exact_every_seed'] = all(
        row['rollback']['records_exactly_restored'] and row['rollback']['new_audit_version']
        for row in every_seed
    )

    rubric = lock['readiness_rubric']
    credit_conditions = {
        'mechanism_level_cross_domain_transfer': checks['external_unique_target_every_seed'] and checks['exact_heldout_replay'],
        'safe_negative_transfer_isolation': checks['local_quarantine_every_seed'],
        'open_ended_capacity_merge_governance': checks['dedup_zero_capacity_delta_every_seed'] and checks['bounded_capacity_every_seed'],
        'reversible_rollback': checks['rollback_exact_every_seed'],
        'external_nist_grounded_execution': checks['nist_key_fixture_locked'] and checks['nist_word_fixture_locked'] and checks['core_ablation_falsifies_every_seed'],
        'world_preregistration_discipline': checks['world_preregistered_all_predictions'] and checks['world_prediction_precedes_experiment'] and checks['world_post_audit_valid'],
    }
    awarded = {
        name: (float(rubric[name]) if credit_conditions[name] else 0.0)
        for name in rubric
    }
    readiness_before = float(lock['agi_engineering_readiness_before'])
    readiness_after = readiness_before + sum(awarded.values())
    readiness_after = min(readiness_after, float(lock['agi_engineering_readiness_max_after']))

    accepted = all(checks.values()) and all(credit_conditions.values())
    result = {
        'schema_version': 1,
        'milestone': lock['milestone'],
        'decision': 'accepted' if accepted else 'rejected',
        'checks': checks,
        'check_count': len(checks),
        'checks_passed': sum(bool(v) for v in checks.values()),
        'frozen_mismatches': frozen_mismatches,
        'heldout_replay': replay_rows,
        'readiness': {
            'before': readiness_before,
            'awarded': awarded,
            'increment': sum(awarded.values()) if accepted else 0.0,
            'after': readiness_after if accepted else readiness_before,
            'scale': 'AGI engineering-readiness rubric, not literal probability of AGI',
        },
        'claim_boundary': 'Bounded cross-domain mechanism/governance evidence only; no unrestricted concept transfer, external coding parity, frontier-model parity or AGI claim.',
    }
    OUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'decision': result['decision'],
        'checks': f"{result['checks_passed']}/{result['check_count']}",
        'readiness': result['readiness'],
        'heldout_replay': replay_rows,
    }, indent=2, sort_keys=True))
    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
