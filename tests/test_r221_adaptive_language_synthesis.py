from benchmarks.kfigg.r220_language_synthesis import run_r220
from benchmarks.kfigg.r221_adaptive_language_synthesis import (
    BASE_BUDGET,
    MAX_BUDGET,
    run_r221,
)


def test_known_r220_diagnostic_is_recovered_additively():
    frozen = run_r220(73459, heldout=True)
    assert frozen['all_gates_pass'] is False
    assert frozen['gates']['partial_noisy_verifier_calibrated'] is False

    result = run_r221(73459)
    assert result['gates']['diagnostic_fixed15_failure_preserved'] is True
    assert result['gates']['adaptive_noisy_verifier_calibrated'] is True
    assert result['all_gates_pass'] is True
    assert result['adaptive_noisy_decision']['queries_used'] > 15
    assert result['adaptive_noisy_decision']['queries_used'] <= MAX_BUDGET


def test_easy_dev_matrix_stops_before_always_max_and_stays_correct():
    rows = [run_r221(seed) for seed in (74011, 74707, 75431, 76103)]
    assert all(row['all_gates_pass'] for row in rows)
    assert all(row['adaptive_noisy_decision']['queries_used'] < row['ablations']['always_max']['query_cost'] for row in rows)
    assert all(row['adaptive_noisy_decision']['correct'] for row in rows)
    assert sum(row['adaptive_noisy_decision']['queries_used'] for row in rows) / len(rows) < MAX_BUDGET


def test_policy_has_base_and_hard_max_budget_contract():
    row = run_r221(74011)
    assert row['thresholds']['base_budget'] == BASE_BUDGET == 12
    assert row['thresholds']['max_budget'] == MAX_BUDGET == 24
    assert row['adaptive_noisy_decision']['queries_used'] <= MAX_BUDGET
    assert row['gates']['nonidentifiable_case_abstains'] is True


def test_r220_language_synthesis_and_reuse_capabilities_remain_intact():
    row = run_r221(74707)
    assert row['gates']['r220_target_outside_fixed_grammar'] is True
    assert row['gates']['r220_operator_generated'] is True
    assert row['gates']['r220_main_discovery_intact'] is True
    assert row['gates']['r220_prospective_reuse_intact'] is True
