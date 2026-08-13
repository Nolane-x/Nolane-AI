from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIGHT = ROOT / 'checkpoints/Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt'


def _models():
    from cogcoder.r20i_standalone import load_r20i_standalone
    return load_r20i_standalone(WEIGHT)[:3]


def _demos(fn, xs=(-4, -1, 2, 7)):
    from cogcoder.skill_synthesis import Demonstration
    return tuple(Demonstration(x, fn(x)) for x in xs)


def test_runtime_learns_skill_from_demos_and_applies_to_unseen_input():
    from cogcoder.continual_skills import ContinualSkillLayer
    p, r, e = _models()
    runtime = ContinualSkillLayer(p, r, e)
    artifact = runtime.learn_skill('opaque', '1', _demos(lambda x: 3 * x + 2), source_uri='curriculum://1')
    assert artifact.version == '1'
    assert runtime.apply_skill('opaque', 11) == 35
    assert runtime.new_neural_parameters == 0
    assert runtime.effective_neural_parameters == 78_779_253


def test_runtime_composes_previously_learned_skills_without_new_demonstrations():
    from cogcoder.continual_skills import ContinualSkillLayer
    p, r, e = _models()
    runtime = ContinualSkillLayer(p, r, e)
    runtime.learn_skill('double_add', '1', _demos(lambda x: x * 2 + 1), source_uri='curriculum://a')
    runtime.learn_skill('xor_shift', '1', _demos(lambda x: (x ^ 5) + 3, xs=(0, 2, 9, 14)), source_uri='curriculum://b')
    value = 8
    expected = ((value * 2 + 1) ^ 5) + 3
    assert runtime.apply_composition(('double_add', 'xor_shift'), value) == expected


def test_new_version_revises_one_skill_without_forgetting_another():
    from cogcoder.continual_skills import ContinualSkillLayer
    p, r, e = _models()
    runtime = ContinualSkillLayer(p, r, e)
    runtime.learn_skill('changing', '1', _demos(lambda x: x * 2), source_uri='curriculum://v1')
    runtime.learn_skill('stable', '1', _demos(lambda x: x + 4), source_uri='curriculum://stable')
    runtime.learn_skill('changing', '2', _demos(lambda x: x * 4 + 1), source_uri='curriculum://v2')
    assert runtime.apply_skill('changing', 5) == 21
    assert runtime.apply_skill('stable', 5) == 9
    assert tuple(a.version for a in runtime.skills.history('changing')) == ('1', '2')


def test_r23_without_skill_use_preserves_r20i_episode_behavior():
    from cogcoder.r18_benchmark import make_r18_task
    from cogcoder.r20i_causal_discovery import run_r20i_episode
    from cogcoder.continual_skills import ContinualSkillLayer
    p, r, e = _models()
    runtime = ContinualSkillLayer(p, r, e)
    for family, index in [('conditional_regimes', 2401), ('causal_prerequisites', 2402)]:
        direct = run_r20i_episode(p, r, e, make_r18_task(family, 'train', index), mode='hybrid_active_causal')
        wrapped = runtime.run_episode(make_r18_task(family, 'train', index), mode='hybrid_active_causal')
        assert wrapped['actions'] == direct['actions']
        assert wrapped['solved'] == direct['solved']
