import pytest
from benchmarks.kfigg.r240_macro_applicability import DEV_SEEDS, DEV_REGIMES, run_dev_matrix, run_episode


def test_dev_block_is_fresh_relative_to_r239_heldout():
    assert set(DEV_SEEDS).isdisjoint({601,607,613})
    assert set(DEV_REGIMES).isdisjoint({'held_clean','held_noisy'})


def test_calibrated_dev_matrix_passes_all_frozen_gates():
    out=run_dev_matrix()
    assert out['all_gates_pass'] is True
    assert out['summary']['calibrated_correct']==12
    assert out['summary']['false_accepts']==0
    assert out['summary']['calibrated_correct'] > out['summary']['unconditional_macro_correct']
    assert out['summary']['calibrated_correct'] >= out['summary']['no_macro_correct']


def test_route_diversity_is_real():
    out=run_dev_matrix()
    assert out['summary']['macro_route_count'] > 0
    assert out['summary']['defer_route_count'] > 0
    assert out['summary']['fully_deferred_episodes'] > 0


def test_episode_is_deterministic():
    a=run_episode(739,'cal_shift','calibrated'); b=run_episode(739,'cal_shift','calibrated')
    assert a==b
    assert a['correct'] is True
    assert 'defer_raw' in a['applicability_routes']


def test_unknown_mode_or_regime_rejected():
    with pytest.raises(ValueError): run_episode(701,'bogus','calibrated')
    with pytest.raises(ValueError): run_episode(701,'cal_clean','bogus')
