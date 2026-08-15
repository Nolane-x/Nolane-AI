import pytest


def _signature(space):
    return tuple((row.signature, tuple((i.op, i.arg) for i in row.representative)) for row in space.classes)


def test_sparse_demos_retain_semantically_distinct_programs_instead_of_shortest_only():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(
        probe_domain=tuple(range(0, 8)), max_depth=2, add_limit=2, mul_limit=2, xor_limit=3, mod_limit=5,
        max_candidates=50_000,
    )
    demos = (Demonstration(0, 1), Demonstration(2, 3))
    space = identifier.build_version_space(demos)
    assert len(space.classes) >= 2
    assert len({row.signature for row in space.classes}) == len(space.classes)


def test_observationally_equivalent_programs_collapse_to_one_semantic_class():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(
        probe_domain=(-2, -1, 0, 1, 2), max_depth=2, add_limit=1, mul_limit=2, xor_limit=1, mod_limit=3,
        max_candidates=50_000,
    )
    space = identifier.build_version_space((Demonstration(0, 0), Demonstration(1, 1)))
    assert len({c.signature for c in space.classes}) == len(space.classes)
    for c in space.classes:
        assert c.representative


def test_conflicting_demonstrations_are_rejected_before_enumeration():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(probe_domain=(0, 1, 2))
    with pytest.raises(ValueError, match='conflicting demonstrations'):
        identifier.build_version_space((Demonstration(1, 2), Demonstration(1, 3)))


def test_minimax_discriminator_chooses_smallest_worst_case_partition():
    from cogcoder.epistemic_program import Instruction
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier, SemanticClass, VersionSpace

    classes = (
        SemanticClass((0, 0, 0, 0), (Instruction('ADD', 1),)),
        SemanticClass((0, 0, 1, 0), (Instruction('ADD', 2),)),
        SemanticClass((0, 1, 0, 1), (Instruction('ADD', 3),)),
        SemanticClass((0, 1, 1, 1), (Instruction('ADD', 4),)),
    )
    space = VersionSpace((0, 1, 2, 3), classes, ((0, 0),), 4)
    # x=1 and x=2 both split 2/2; deterministic tie-break selects x=1.
    assert ActiveProgramIdentifier.select_discriminator(space) == 1


def test_active_identification_resolves_true_semantics_under_hard_budget():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(
        probe_domain=tuple(range(0, 16)), max_depth=2, add_limit=3, mul_limit=3, xor_limit=7, mod_limit=7,
        max_candidates=100_000,
    )
    target = lambda x: (x ^ 5) + 2
    demos = tuple(Demonstration(x, target(x)) for x in (0, 4))
    result = identifier.identify(demos, target, max_oracle_calls=3)
    assert result.resolved
    assert result.oracle_calls <= 3
    assert result.signature == tuple(target(x) for x in identifier.probe_domain)
    assert result.observations[:2] == ((0, target(0)), (4, target(4)))


def test_budget_exhaustion_abstains_instead_of_shortest_guess():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(
        probe_domain=tuple(range(0, 16)), max_depth=2, add_limit=3, mul_limit=3, xor_limit=7, mod_limit=7,
        max_candidates=100_000,
    )
    target = lambda x: (x ^ 5) + 2
    demos = (Demonstration(0, target(0)),)
    result = identifier.identify(demos, target, max_oracle_calls=0)
    assert not result.resolved
    assert result.reason == 'oracle_budget_exhausted'
    assert result.oracle_calls == 0


def test_out_of_class_oracle_eliminates_space_and_never_false_resolves():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(
        probe_domain=tuple(range(0, 10)), max_depth=1, add_limit=2, mul_limit=2, xor_limit=2, mod_limit=3,
        max_candidates=10_000,
    )
    target = lambda x: x * x + 7
    demos = (Demonstration(0, target(0)),)
    result = identifier.identify(demos, target, max_oracle_calls=3)
    assert not result.resolved
    assert result.reason in {'no_consistent_program', 'oracle_budget_exhausted'}


def test_query_trace_and_result_are_invariant_to_semantic_class_order():
    from cogcoder.epistemic_program import Instruction
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier, SemanticClass, VersionSpace

    classes = (
        SemanticClass((0, 0, 1), (Instruction('ADD', 1),)),
        SemanticClass((0, 1, 0), (Instruction('XOR', 1),)),
        SemanticClass((0, 1, 1), (Instruction('MOD', 2),)),
    )
    a = VersionSpace((0, 1, 2), classes, ((0, 0),), 3)
    b = VersionSpace((0, 1, 2), tuple(reversed(classes)), ((0, 0),), 3)
    assert ActiveProgramIdentifier.select_discriminator(a) == ActiveProgramIdentifier.select_discriminator(b)


def test_inconsistent_external_space_with_no_legal_discriminator_abstains_not_certifies():
    from cogcoder.epistemic_program import Instruction
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier, SemanticClass, VersionSpace

    # Both points are already observed, so no legal query remains; resolving would be unsafe.
    classes = (
        SemanticClass((0, 0), (Instruction('ADD', 1),)),
        SemanticClass((0, 1), (Instruction('XOR', 1),)),
    )
    space = VersionSpace((0, 1), classes, ((0, 0), (1, 0)), 2)
    assert ActiveProgramIdentifier.select_discriminator(space) is None
    assert not ActiveProgramIdentifier.resolve_space_without_oracle(space).resolved


def test_truncated_enumeration_fails_closed_instead_of_resolving_partial_space():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(
        probe_domain=tuple(range(8)), max_depth=2, max_candidates=1,
        add_limit=2, mul_limit=2, xor_limit=2, mod_limit=3,
    )
    target = lambda x: x + 1
    result = identifier.identify(
        (Demonstration(0, 1), Demonstration(1, 2)), target, max_oracle_calls=3
    )
    assert not result.resolved
    assert result.reason == 'candidate_budget_exhausted'


def test_identify_from_prebuilt_space_matches_identify_without_reenumeration_semantics():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(
        probe_domain=tuple(range(16)), max_depth=2, add_limit=3, mul_limit=3, xor_limit=7, mod_limit=7,
    )
    target = lambda x: (x ^ 4) + 1
    demos = (Demonstration(0, target(0)), Demonstration(1, target(1)))
    space = identifier.build_version_space(demos)
    direct = identifier.identify(demos, target, max_oracle_calls=3)
    reused = identifier.identify_from_space(space, target, max_oracle_calls=3)
    assert reused == direct


def test_unique_initial_candidate_requires_one_falsification_probe_before_resolve():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(
        probe_domain=tuple(range(8)), max_depth=1, add_limit=2, mul_limit=2, xor_limit=2, mod_limit=3,
    )
    expected = lambda x: x + 1
    demos = tuple(Demonstration(x, expected(x)) for x in (0, 1, 2, 3, 4, 5, 6))
    space = identifier.build_version_space(demos)
    assert len(space.classes) == 1

    # The unseen point contradicts the apparently unique candidate.
    oracle = lambda x: expected(x) if x != 7 else 999
    result = identifier.identify_from_space(space, oracle, max_oracle_calls=1)
    assert not result.resolved
    assert result.reason == 'no_consistent_program'
    assert result.oracle_calls == 1


def test_unique_initial_candidate_abstains_if_confirmation_budget_is_zero():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(
        probe_domain=tuple(range(8)), max_depth=1, add_limit=2, mul_limit=2, xor_limit=2, mod_limit=3,
    )
    target = lambda x: x + 1
    demos = tuple(Demonstration(x, target(x)) for x in (0, 1, 2, 3, 4, 5, 6))
    space = identifier.build_version_space(demos)
    assert len(space.classes) == 1
    result = identifier.identify_from_space(space, target, max_oracle_calls=0)
    assert not result.resolved
    assert result.reason == 'confirmation_budget_exhausted'


def test_full_active_trace_is_invariant_to_surviving_class_permutation():
    from cogcoder.r214_active_synthesis import ActiveProgramIdentifier, VersionSpace
    from cogcoder.skill_synthesis import Demonstration

    identifier = ActiveProgramIdentifier(
        probe_domain=tuple(range(16)), max_depth=2, add_limit=3, mul_limit=3, xor_limit=7, mod_limit=7,
    )
    target = lambda x: (x ^ 4) + 2
    demos = (Demonstration(0, target(0)), Demonstration(1, target(1)))
    space = identifier.build_version_space(demos)
    reversed_space = VersionSpace(
        space.probe_domain, tuple(reversed(space.classes)), space.observations,
        space.candidates_evaluated, space.enumeration_complete,
    )
    a = identifier.identify_from_space(space, target, max_oracle_calls=3)
    b = identifier.identify_from_space(reversed_space, target, max_oracle_calls=3)
    assert a == b
