from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.r269_world_adjudication import build_receipt, verify_receipt


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def _fixture(tmp_path: Path):
    state = tmp_path / 'state.json'
    gate = tmp_path / 'gate.json'
    seq = tmp_path / 'seq.json'
    ext = tmp_path / 'ext.json'
    promo = tmp_path / 'promo.json'
    receipt = tmp_path / 'receipt.json'

    _write(state, {
        'id': 'world_012345abcdef',
        'depth': 'W5',
        'events': [
            {'type': 'world.enter', 'depth': 'W5', 'dev_fast': False, 'at': '2026-08-20T00:00:00+00:00'},
        ],
        'evidence': [
            {'id': 'ev1', 'independent': True, 'source': 'hosted-red-green'},
            {'id': 'ev2', 'independent': True, 'source': 'hosted-external'},
            {'id': 'ev3', 'independent': True, 'source': 'hosted-promotion'},
        ],
        'unknowns': [
            {'id': 'u1', 'critical': True, 'bounded': True, 'resolution': 'resolved by hosted evidence'},
        ],
    })
    _write(gate, {'pass_gate': False, 'reason_codes': ['MIN_RESIDENCY_NOT_MET', 'W5_CONVERGENCE_NOT_CLAIMED']})
    _write(seq, {
        'milestone': 'R2.69',
        'complete_authored_r269_green': True,
        'false_accepts': 0,
        'trainable_parameter_count': 0,
    })
    _write(ext, {
        'milestone': 'R2.69',
        'all_gates_pass': True,
        'source_exposure': 'io_only',
        'target_exposure': 'io_only',
        'source_from_authored_generator': False,
        'false_accepts': 0,
        'trainable_parameter_count': 0,
    })
    _write(promo, {
        'milestone': 'R2.69',
        'promotion_gate_pass': True,
        'promotion_accepted': True,
        'governed_reuse_passed': True,
        'rollback_revoked': True,
        'source_adapter_type': 'verified_meta_episode_v1',
        'champion_accepted_targets': 8,
        'challenger_accepted_targets': 2,
        'oracle_call_advantage': 1,
        'search_work_advantage': 20,
        'false_accepts': 0,
        'trainable_parameter_count': 0,
    })
    return state, gate, seq, ext, promo, receipt


def test_world_bounded_receipt_is_exactly_bound_to_world_and_hosted_evidence(tmp_path: Path):
    state, gate, seq, ext, promo, receipt = _fixture(tmp_path)
    value = build_receipt(
        world_state_path=state,
        world_gate_path=gate,
        sequential_path=seq,
        external_path=ext,
        promotion_path=promo,
    )
    _write(receipt, value)
    verified = verify_receipt(
        world_receipt_path=receipt,
        world_state_path=state,
        world_gate_path=gate,
        sequential_path=seq,
        external_path=ext,
        promotion_path=promo,
    )
    assert verified['final_bounded_release'] == 'ACCEPT'
    assert verified['full_w5_gate_pass'] is False
    assert verified['w5_convergence_claimed'] is False
    assert verified['world_session_id'] == 'world_012345abcdef'
    assert verified['receipt_digest'].startswith('r269.world-bounded.')


def test_world_bounded_receipt_rejects_non_native_session_id(tmp_path: Path):
    state, gate, seq, ext, promo, _receipt = _fixture(tmp_path)
    value = json.loads(state.read_text())
    value['id'] = 'world5_test_r269'
    _write(state, value)
    with pytest.raises(ValueError, match='native Nolane World 0.8.0 session id format'):
        build_receipt(
            world_state_path=state, world_gate_path=gate, sequential_path=seq,
            external_path=ext, promotion_path=promo,
        )


def test_world_bounded_receipt_rejects_missing_native_enter_event(tmp_path: Path):
    state, gate, seq, ext, promo, _receipt = _fixture(tmp_path)
    value = json.loads(state.read_text())
    value['events'] = []
    _write(state, value)
    with pytest.raises(ValueError, match='world.enter provenance event'):
        build_receipt(
            world_state_path=state, world_gate_path=gate, sequential_path=seq,
            external_path=ext, promotion_path=promo,
        )


def test_world_bounded_receipt_rejects_non_w5_enter_provenance(tmp_path: Path):
    state, gate, seq, ext, promo, _receipt = _fixture(tmp_path)
    value = json.loads(state.read_text())
    value['events'][0]['depth'] = 'W4'
    _write(state, value)
    with pytest.raises(ValueError, match='W5 world.enter provenance event'):
        build_receipt(
            world_state_path=state, world_gate_path=gate, sequential_path=seq,
            external_path=ext, promotion_path=promo,
        )


def test_world_bounded_receipt_rejects_dev_fast_session(tmp_path: Path):
    state, gate, seq, ext, promo, _receipt = _fixture(tmp_path)
    value = json.loads(state.read_text())
    value['events'][0]['dev_fast'] = True
    _write(state, value)
    with pytest.raises(ValueError, match='non-dev-fast World session'):
        build_receipt(
            world_state_path=state, world_gate_path=gate, sequential_path=seq,
            external_path=ext, promotion_path=promo,
        )


def test_world_receipt_rejects_hosted_evidence_tampering(tmp_path: Path):
    state, gate, seq, ext, promo, receipt = _fixture(tmp_path)
    value = build_receipt(
        world_state_path=state, world_gate_path=gate, sequential_path=seq,
        external_path=ext, promotion_path=promo,
    )
    _write(receipt, value)
    changed = json.loads(promo.read_text())
    changed['search_work_advantage'] = 999
    _write(promo, changed)
    with pytest.raises(ValueError, match='does not match bound evidence'):
        verify_receipt(
            world_receipt_path=receipt, world_state_path=state, world_gate_path=gate,
            sequential_path=seq, external_path=ext, promotion_path=promo,
        )


def test_world_bounded_receipt_refuses_full_w5_convergence_claim(tmp_path: Path):
    state, gate, seq, ext, promo, _receipt = _fixture(tmp_path)
    value = json.loads(gate.read_text())
    value['pass_gate'] = True
    _write(gate, value)
    with pytest.raises(ValueError, match='must not claim full W5 convergence'):
        build_receipt(
            world_state_path=state, world_gate_path=gate, sequential_path=seq,
            external_path=ext, promotion_path=promo,
        )


def test_world_bounded_receipt_requires_release_critical_unknown_resolution(tmp_path: Path):
    state, gate, seq, ext, promo, _receipt = _fixture(tmp_path)
    value = json.loads(state.read_text())
    value['unknowns'][0]['bounded'] = False
    value['unknowns'][0]['resolution'] = None
    _write(state, value)
    with pytest.raises(ValueError, match='critical World unknowns remain unresolved'):
        build_receipt(
            world_state_path=state, world_gate_path=gate, sequential_path=seq,
            external_path=ext, promotion_path=promo,
        )


def test_world_bounded_receipt_requires_genuine_promotion_advantage(tmp_path: Path):
    state, gate, seq, ext, promo, _receipt = _fixture(tmp_path)
    value = json.loads(promo.read_text())
    value['challenger_accepted_targets'] = value['champion_accepted_targets']
    value['oracle_call_advantage'] = 0
    value['search_work_advantage'] = 0
    _write(promo, value)
    with pytest.raises(ValueError, match='genuine champion/challenger advantage'):
        build_receipt(
            world_state_path=state, world_gate_path=gate, sequential_path=seq,
            external_path=ext, promotion_path=promo,
        )
