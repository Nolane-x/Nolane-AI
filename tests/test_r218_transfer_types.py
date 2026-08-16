import hashlib

import pytest

from cogcoder.r218_transfer_types import (
    DomainDescriptor,
    DomainEvidence,
    GovernedSkillRecord,
    OpenEndedLibraryVersion,
    TransferObservation,
    TransferSkill,
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_domain_and_skill_identity_are_canonicalized_by_mechanism_not_label_order():
    a = DomainDescriptor(' AES-128 ', ('Periodic', ' Guarded ', 'periodic'))
    b = DomainDescriptor('aes-128', ('guarded', 'periodic'))
    assert a.domain_id == 'aes-128'
    assert a.mechanism_tags == ('guarded', 'periodic')
    assert a == b

    s1 = TransferSkill(
        ' recurrence ',
        ('periodic', 'guarded', 'periodic'),
        digest('behavior-v1'),
        ('payload:b', 'payload:a'),
        ('nist', 'synthetic', 'nist'),
        ('source-b', 'source-a'),
        capacity_cost=2,
    )
    s2 = TransferSkill(
        'recurrence',
        ('guarded', 'periodic'),
        digest('behavior-v1'),
        ('different-payload',),
        ('different-lineage',),
        ('different-domain',),
        capacity_cost=2,
    )
    assert s1.kind == 'recurrence'
    assert s1.mechanism_tags == ('guarded', 'periodic')
    assert s1.payload_refs == ('payload:a', 'payload:b')
    assert s1.provenance_lineages == ('nist', 'synthetic')
    assert s1.source_domains == ('source-a', 'source-b')
    assert s1.skill_id == s2.skill_id


def test_transfer_types_reject_invalid_cost_digest_and_observation_costs():
    with pytest.raises(ValueError, match='64-character lowercase hex'):
        TransferSkill('x', ('tag',), 'bad', (), (), ('d',))
    with pytest.raises(ValueError, match='capacity_cost'):
        TransferSkill('x', ('tag',), digest('x'), (), (), ('d',), capacity_cost=0)
    with pytest.raises(ValueError, match='costs'):
        TransferObservation('t', 'd', 'skill:x', True, True, -1, 1)


def test_library_capacity_counts_nonretired_skill_once():
    skill = TransferSkill('x', ('tag',), digest('x'), (), ('source',), ('d',), capacity_cost=3)
    active = GovernedSkillRecord(skill, 'active', (DomainEvidence('d', 'active', ('t',), 1, 0, 0, 10, 5),))
    retired = GovernedSkillRecord(skill, 'retired', ())
    assert OpenEndedLibraryVersion(1, (active,)).capacity_used == 3
    assert OpenEndedLibraryVersion(2, (retired,), parent_version=1).capacity_used == 0
