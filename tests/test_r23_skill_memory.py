import pytest


def _artifact(name, version, mul, add=0, source='demo://source'):
    from cogcoder.epistemic_program import EpistemicProgram, Instruction
    from cogcoder.skill_memory import SkillArtifact
    instructions = (Instruction('MUL', mul),) + ((Instruction('ADD', add),) if add else ())
    program = EpistemicProgram(name, instructions, (f'{name}:{version}',), (f'sha-{name}-{version}',), (source,), (str(version),))
    return SkillArtifact(
        name=name,
        version=str(version),
        program=program,
        demonstrations=((1, mul + add), (2, 2 * mul + add)),
        provenance_sha256=f'sha-{name}-{version}',
        source_uri=source,
        validation_score=1.0,
    )


def test_registry_retains_unrelated_skills_and_executes_current_versions():
    from cogcoder.skill_memory import SkillRegistry
    reg = SkillRegistry()
    reg.install(_artifact('a', '1', 2))
    reg.install(_artifact('b', '1', 3, 1))
    assert reg.execute('a', 5) == 10
    assert reg.execute('b', 5) == 16
    assert reg.current('a').version == '1'
    assert reg.current('b').version == '1'


def test_newer_version_supersedes_only_same_skill_and_rollback_restores_prior():
    from cogcoder.skill_memory import SkillRegistry
    reg = SkillRegistry()
    reg.install(_artifact('a', '1', 2))
    reg.install(_artifact('b', '1', 7))
    reg.install(_artifact('a', '2', 4, 1))
    assert reg.execute('a', 3) == 13
    assert reg.execute('b', 3) == 21
    assert reg.current('a').version == '2'
    restored = reg.rollback('a')
    assert restored.version == '1'
    assert reg.execute('a', 3) == 6
    assert reg.current('b').version == '1'


def test_same_name_version_with_different_provenance_is_rejected():
    from cogcoder.skill_memory import SkillArtifact, SkillRegistry
    a = _artifact('x', '4', 2, source='demo://one')
    reg = SkillRegistry([a])
    bad = SkillArtifact(
        name=a.name,
        version=a.version,
        program=a.program,
        demonstrations=a.demonstrations,
        provenance_sha256='different-sha',
        source_uri='demo://two',
        validation_score=1.0,
    )
    with pytest.raises(ValueError, match='version provenance collision'):
        reg.install(bad)


def test_feedback_updates_only_current_artifact_and_snapshot_is_deterministic():
    from cogcoder.skill_memory import SkillRegistry
    reg = SkillRegistry([_artifact('a', '1', 2), _artifact('b', '1', 3)])
    before_b = reg.current('b')
    reg.record_feedback('a', True)
    reg.record_feedback('a', False)
    after_a = reg.current('a')
    assert (after_a.successes, after_a.failures) == (1, 1)
    assert reg.current('b') == before_b
    first = reg.snapshot()
    second = reg.snapshot()
    assert first == second
    assert first['current'] == {'a': '1', 'b': '1'}


def test_older_version_can_be_audited_without_replacing_current():
    from cogcoder.skill_memory import SkillRegistry
    reg = SkillRegistry([_artifact('a', '2', 5)])
    reg.install(_artifact('a', '1', 2))
    assert reg.current('a').version == '2'
    assert tuple(x.version for x in reg.history('a')) == ('1', '2')
