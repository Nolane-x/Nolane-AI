from cogcoder.r218_periodic_invariant import (
    AES_CORE_DECOYS,
    NIST_AES128_KEY,
    NIST_AES128_WORDS,
    aes128_nist_adapter,
    check_periodic_recurrence,
    filter_cohort,
    make_aes128_nist_cohort,
    make_source_recurrence_cohort,
    source_periodic_adapter,
)


def test_source_domain_periodic_guard_skill_separates_target_from_special_rule_decoys():
    adapter = source_periodic_adapter()
    cohort = make_source_recurrence_cohort()
    assert filter_cohort(cohort, adapter) == ('source_target',)
    for name in ('source_wrong_special', 'source_skipped_special'):
        check = check_periodic_recurrence(cohort[name], adapter)
        assert check.seed
        assert check.length
        assert check.normal_recurrence
        assert not check.special_recurrence


def test_nist_aes_appendix_a1_fixture_is_frozen_independently_of_filtering():
    assert NIST_AES128_KEY.hex() == '2b7e151628aed2a6abf7158809cf4f3c'
    assert len(NIST_AES128_WORDS) == 44
    assert NIST_AES128_WORDS[:8] == (
        0x2B7E1516, 0x28AED2A6, 0xABF71588, 0x09CF4F3C,
        0xA0FAFE17, 0x88542CB1, 0x23A33939, 0x2A6C7605,
    )
    assert NIST_AES128_WORDS[-4:] == (
        0xD014F9A8, 0xC9EE2589, 0xE13F0CC8, 0xB6630CA6,
    )


def test_same_generic_verifier_transfers_to_aes_and_uniquely_retains_nist_target():
    adapter = aes128_nist_adapter()
    cohort = make_aes128_nist_cohort()
    assert filter_cohort(cohort, adapter) == ('target_nist_fips197',)
    target = check_periodic_recurrence(cohort['target_nist_fips197'], adapter)
    assert target.passed


def test_aes_core_decoys_are_hard_decoys_not_seed_length_or_normal_rule_failures():
    adapter = aes128_nist_adapter()
    cohort = make_aes128_nist_cohort()
    assert set(AES_CORE_DECOYS) == {
        'core_no_rot', 'core_no_sub', 'core_wrong_rcon', 'core_rcon_low_byte'
    }
    for name in AES_CORE_DECOYS:
        check = check_periodic_recurrence(cohort[name], adapter)
        assert check.seed
        assert check.length
        assert check.normal_recurrence
        assert not check.special_recurrence


def test_special_rule_ablation_admits_all_aes_core_decoys():
    adapter = aes128_nist_adapter()
    cohort = make_aes128_nist_cohort()
    survivors = filter_cohort(cohort, adapter, enabled=('seed', 'length', 'normal_recurrence'))
    assert 'target_nist_fips197' in survivors
    assert set(AES_CORE_DECOYS).issubset(set(survivors))


def test_other_aes_decoys_fail_their_intended_non_special_gate():
    adapter = aes128_nist_adapter()
    cohort = make_aes128_nist_cohort()
    assert not check_periodic_recurrence(cohort['wrong_seed'], adapter).seed
    assert not check_periodic_recurrence(cohort['truncated'], adapter).length
    assert not check_periodic_recurrence(cohort['bad_normal'], adapter).normal_recurrence
