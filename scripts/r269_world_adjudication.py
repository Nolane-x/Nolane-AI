from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

CLAIM_BOUNDARY = (
    'bounded zero-trainable-parameter verifier-backed causal-experience transfer and sequential meta-learning '
    'over declared finite numeric structural classes, with shared target evidence, bounded negative-transfer regret, '
    'host-attested scoped champion/challenger promotion, exact rollback, and governed learned-prior reuse; not unrestricted '
    'cross-domain learning, not arbitrary self-modification, not W5 convergence, not AGI, and not frontier-model equivalence'
)

DEFAULT_PATHS = {
    'world_receipt': Path('R2_69_WORLD_BOUNDED_ADJUDICATION.json'),
    'world_state': Path('R2_69_WORLD_STATE_SNAPSHOT.json'),
    'world_gate': Path('R2_69_WORLD_GATE_SNAPSHOT.json'),
    'sequential': Path('R2_69_SEQUENTIAL_INTEGRATION_EVIDENCE.json'),
    'external': Path('R2_69_EXTERNAL_TRANSFER.json'),
    'promotion': Path('R2_69_PROMOTION_AUTHORITY.json'),
}


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'{path} must contain a JSON object')
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt_digest(payload: Mapping[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    return 'r269.world-bounded.' + hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _assert_release_evidence(seq: Mapping[str, object], ext: Mapping[str, object], promo: Mapping[str, object]) -> None:
    if seq.get('milestone') != 'R2.69':
        raise ValueError('sequential evidence milestone mismatch')
    if seq.get('complete_authored_r269_green') is not True:
        raise ValueError('sequential authored R2.69 evidence is not green')
    if int(seq.get('false_accepts', 0)) != 0:
        raise ValueError('sequential evidence contains false accepts')
    if int(seq.get('trainable_parameter_count', 0)) != 0:
        raise ValueError('sequential evidence must add zero trainable parameters')

    if ext.get('milestone') != 'R2.69' or ext.get('all_gates_pass') is not True:
        raise ValueError('external evidence is not accepted')
    if ext.get('source_exposure') != 'io_only' or ext.get('target_exposure') != 'io_only':
        raise ValueError('external evidence must remain black-box I/O only')
    if ext.get('source_from_authored_generator') is not False:
        raise ValueError('external source must not come from the authored generator')
    if int(ext.get('false_accepts', -1)) != 0 or int(ext.get('trainable_parameter_count', -1)) != 0:
        raise ValueError('external evidence must preserve zero false accepts and zero trainable parameters')

    if promo.get('milestone') != 'R2.69' or promo.get('promotion_gate_pass') is not True:
        raise ValueError('promotion authority evidence is not accepted')
    if promo.get('promotion_accepted') is not True or promo.get('governed_reuse_passed') is not True:
        raise ValueError('promotion evidence must prove accepted governed learned-prior reuse')
    if promo.get('rollback_revoked') is not True:
        raise ValueError('promotion evidence must prove exact rollback revocation')
    if promo.get('source_adapter_type') != 'verified_meta_episode_v1':
        raise ValueError('promotion candidate must be learned verified_meta_episode_v1 experience')
    if not (
        int(promo.get('champion_accepted_targets', 0)) > int(promo.get('challenger_accepted_targets', 0))
        or int(promo.get('oracle_call_advantage', 0)) > 0
        or int(promo.get('search_work_advantage', 0)) > 0
    ):
        raise ValueError('promotion evidence does not contain genuine champion/challenger advantage')
    if int(promo.get('false_accepts', -1)) != 0 or int(promo.get('trainable_parameter_count', -1)) != 0:
        raise ValueError('promotion evidence must preserve zero false accepts and zero trainable parameters')


def build_receipt(
    *,
    world_state_path: Path = DEFAULT_PATHS['world_state'],
    world_gate_path: Path = DEFAULT_PATHS['world_gate'],
    sequential_path: Path = DEFAULT_PATHS['sequential'],
    external_path: Path = DEFAULT_PATHS['external'],
    promotion_path: Path = DEFAULT_PATHS['promotion'],
) -> dict[str, object]:
    state = _load(world_state_path)
    gate = _load(world_gate_path)
    seq = _load(sequential_path)
    ext = _load(external_path)
    promo = _load(promotion_path)
    _assert_release_evidence(seq, ext, promo)

    world_id = str(state.get('id', ''))
    if state.get('depth') != 'W5' or not world_id.startswith('world5_'):
        raise ValueError('World state must be an actual W5 Nolane World session snapshot')
    critical_unknowns = [row for row in state.get('unknowns', []) if isinstance(row, dict) and row.get('critical') is True]
    unresolved = [row for row in critical_unknowns if row.get('bounded') is not True or not str(row.get('resolution') or '').strip()]
    if unresolved:
        raise ValueError('release-scoped critical World unknowns remain unresolved')
    independent_evidence = [row for row in state.get('evidence', []) if isinstance(row, dict) and row.get('independent') is True]
    if len(independent_evidence) < 3:
        raise ValueError('World state requires at least three independent evidence records')

    if gate.get('pass_gate') is not False:
        raise ValueError('bounded R2.69 receipt must not claim full W5 convergence')
    reason_codes = gate.get('reason_codes')
    if not isinstance(reason_codes, list) or not reason_codes:
        raise ValueError('World gate snapshot must preserve fail-closed reason codes')

    payload: dict[str, object] = {
        'schema_version': 2,
        'milestone': 'R2.69',
        'world_version': '0.8.0',
        'world_session_id': world_id,
        'world_depth': 'W5',
        'world_state_sha256': file_sha256(world_state_path),
        'world_gate_sha256': file_sha256(world_gate_path),
        'full_w5_gate_pass': False,
        'world_gate_reason_codes': list(map(str, reason_codes)),
        'w5_convergence_claimed': False,
        'convergence_forced': False,
        'release_scope_unknowns_resolved': True,
        'independent_evidence_records': len(independent_evidence),
        'evidence_bindings': {
            'sequential_integration_sha256': file_sha256(sequential_path),
            'external_transfer_sha256': file_sha256(external_path),
            'promotion_authority_sha256': file_sha256(promotion_path),
        },
        'false_accepts': 0,
        'trainable_parameter_count': 0,
        'claim_boundary': CLAIM_BOUNDARY,
        'final_bounded_release': 'ACCEPT',
    }
    payload['receipt_digest'] = _receipt_digest(payload)
    return payload


def verify_receipt(
    *,
    world_receipt_path: Path = DEFAULT_PATHS['world_receipt'],
    world_state_path: Path = DEFAULT_PATHS['world_state'],
    world_gate_path: Path = DEFAULT_PATHS['world_gate'],
    sequential_path: Path = DEFAULT_PATHS['sequential'],
    external_path: Path = DEFAULT_PATHS['external'],
    promotion_path: Path = DEFAULT_PATHS['promotion'],
) -> dict[str, object]:
    actual = _load(world_receipt_path)
    expected = build_receipt(
        world_state_path=world_state_path,
        world_gate_path=world_gate_path,
        sequential_path=sequential_path,
        external_path=external_path,
        promotion_path=promotion_path,
    )
    if actual != expected:
        raise ValueError('World bounded adjudication receipt does not match bound evidence and World snapshots')
    return actual


if __name__ == '__main__':
    receipt = verify_receipt()
    print('R269_WORLD_BOUNDED_ADJUDICATION_OK=' + str(receipt['receipt_digest']))
