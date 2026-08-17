import inspect

from benchmarks.kfigg.r238_compositional_probe_language import (
    dry_run_transfer_family,
    run_dev_matrix,
    run_episode,
)
from cogcoder.r238_probe_synthesis import synthesize_compositional_probe


def test_r238_dev_matrix_meets_causal_language_expansion_gates():
    result = run_dev_matrix()
    assert result['all_gates_pass'], result
    assert result['summary']['compositional_correct'] == result['summary']['episodes_per_mode']
    assert result['summary']['composite_probe_count'] > 0


def test_transfer_family_dry_run_uses_same_generator_and_is_safe():
    result = dry_run_transfer_family()
    assert result['all_gates_pass'], result
    assert result['gates']['same_generator_code_path']
    assert result['gates']['zero_false_accepts']


def test_episode_budget_is_identical_across_modes():
    rows = [run_episode(3, 'nonlinear_local', 151, 'clean', mode) for mode in ('compositional','atomic_only','pool_only')]
    assert len({r['query_budget'] for r in rows}) == 1


def test_generator_signature_has_no_forbidden_inference_fields():
    names = set(inspect.signature(synthesize_compositional_probe).parameters)
    forbidden = {'seed','episode_key','domain','family','task_family','target','truth','heldout','actual_reliability','evaluator_reliability'}
    assert names.isdisjoint(forbidden)
