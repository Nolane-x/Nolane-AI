import pytest


def test_synthesizes_shortest_multistep_skill_deterministically():
    from cogcoder.skill_synthesis import BoundedSkillSynthesizer, Demonstration
    demos = tuple(Demonstration(x, 3 * x + 2) for x in (-4, -1, 2, 7))
    synth = BoundedSkillSynthesizer(max_depth=3, max_candidates=20000)
    first = synth.synthesize('opaque_a', '1', demos)
    second = synth.synthesize('opaque_a', '1', demos)
    assert first.resolved and second.resolved
    assert first.instructions == second.instructions
    assert tuple((i.op, i.arg) for i in first.instructions) == (('MUL', 3), ('ADD', 2))
    assert first.program is not None


def test_synthesized_program_generalizes_to_unseen_values():
    from cogcoder.epistemic_program import ProgramRegistry
    from cogcoder.skill_synthesis import BoundedSkillSynthesizer, Demonstration
    demos = tuple(Demonstration(x, (x ^ 5) + 3) for x in (0, 2, 9, 14))
    result = BoundedSkillSynthesizer(max_depth=3).synthesize('opaque_b', '7', demos)
    assert result.resolved and result.program is not None
    reg = ProgramRegistry([result.program])
    for x in (1, 4, 11, 21):
        assert reg.execute('opaque_b', x) == (x ^ 5) + 3


def test_budget_exhaustion_returns_unresolved_instead_of_guessing():
    from cogcoder.skill_synthesis import BoundedSkillSynthesizer, Demonstration
    demos = (Demonstration(0, 1000), Demonstration(1, -777), Demonstration(2, 42))
    result = BoundedSkillSynthesizer(max_depth=2, max_candidates=3).synthesize('hard', '1', demos)
    assert not result.resolved
    assert result.reason in {'candidate_budget_exhausted', 'no_consistent_program'}
    assert result.program is None


def test_synthesizer_emits_only_restricted_instruction_set():
    from cogcoder.skill_synthesis import BoundedSkillSynthesizer, Demonstration, SAFE_SYNTHESIS_OPS
    demos = tuple(Demonstration(x, (x * 2) ^ 3) for x in (-2, 0, 3, 8))
    result = BoundedSkillSynthesizer(max_depth=3).synthesize('safe', '1', demos)
    assert result.resolved
    assert result.instructions
    assert all(i.op in SAFE_SYNTHESIS_OPS for i in result.instructions)


def test_conflicting_duplicate_input_is_rejected_before_search():
    from cogcoder.skill_synthesis import BoundedSkillSynthesizer, Demonstration
    with pytest.raises(ValueError, match='conflicting demonstrations'):
        BoundedSkillSynthesizer().synthesize('bad', '1', (Demonstration(2, 3), Demonstration(2, 4)))
