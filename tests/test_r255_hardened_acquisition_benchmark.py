from benchmarks.kfigg.r255_hardened_cognitive_acquisition import run_benchmark


def test_r255_hardened_self_improving_acquisition_frozen_benchmark():
    result = run_benchmark()
    assert result['episodes'] == 10
    assert result['exact'] == 10
    assert result['false_accepts'] == 0
    assert result['r254_baseline_exact'] == 0
    assert result['episodes_with_poison_quarantine'] == 10
    assert result['episodes_with_echo_collapse'] == 10
    assert result['episodes_with_procedure_promotion'] == 10
    assert result['episodes_with_malicious_behavior_quarantine'] == 10
    assert result['episodes_with_transactional_rollback'] == 10
    assert result['episodes_with_skill_distillation'] == 10
    assert result['episodes_with_distilled_skill_repromotion'] == 10
    assert result['trainable_parameter_count'] == 0
