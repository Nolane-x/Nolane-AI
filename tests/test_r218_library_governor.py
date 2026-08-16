import hashlib

import pytest

from cogcoder.r218_library_governor import (
    admit_skill,
    apply_transfer_observations,
    enforce_capacity,
    rollback_to_snapshot,
    route_skills,
)
from cogcoder.r218_transfer_types import (
    DomainDescriptor,
    OpenEndedLibraryVersion,
    TransferObservation,
    TransferSkill,
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def skill(name: str, tags=('guarded', 'periodic'), domains=('source',), cost=1) -> TransferSkill:
    return TransferSkill(
        'recurrence', tags, digest(name), (f'payload:{name}',), (f'lineage:{name}',), domains, capacity_cost=cost
    )


def test_duplicate_admission_merges_provenance_without_increasing_capacity():
    base = OpenEndedLibraryVersion(0, ())
    original = skill('same', domains=('source-a',), cost=2)
    v1 = admit_skill(base, original)
    duplicate = TransferSkill(
        original.kind,
        tuple(reversed(original.mechanism_tags)),
        original.behavior_digest,
        ('payload:extra',),
        ('lineage:extra',),
        ('source-b',),
        capacity_cost=2,
    )
    v2 = admit_skill(v1, duplicate)
    assert len(v2.records) == 1
    assert v2.capacity_used == 2
    merged = v2.records[0].skill
    assert merged.payload_refs == ('payload:extra', 'payload:same')
    assert merged.provenance_lineages == ('lineage:extra', 'lineage:same')
    assert merged.source_domains == ('source-a', 'source-b')
    assert v2.parent_version == v1.version


def test_unseen_domain_gets_only_bounded_trial_routes_and_unsupported_domain_abstains():
    lib = admit_skill(OpenEndedLibraryVersion(0, ()), skill('a'))
    lib = admit_skill(lib, skill('b', tags=('guarded', 'periodic', 'xor')))
    target = DomainDescriptor('aes', ('periodic', 'guarded', 'finite-field'))
    routes = route_skills(lib, target, max_capacity=3, min_overlap=.5, max_trials=1)
    assert len(routes) == 1
    assert routes[0].mode == 'trial'
    assert routes[0].overlap >= .5

    alien = DomainDescriptor('vision', ('spatial', 'reflection'))
    assert route_skills(lib, alien, max_capacity=3, min_overlap=.5, max_trials=2) == ()


def test_negative_transfer_quarantines_only_affected_domain_and_preserves_source_route():
    s = skill('shared', domains=('source',))
    lib = admit_skill(OpenEndedLibraryVersion(0, ()), s)
    bad = TransferObservation('bad-1', 'alien', s.skill_id, True, False, 100, 80, false_accept=True)
    q = apply_transfer_observations(lib, (bad,))

    alien = route_skills(q, DomainDescriptor('alien', ('guarded', 'periodic')), max_capacity=2)
    source = route_skills(q, DomainDescriptor('source', ('guarded', 'periodic')), max_capacity=2)
    assert alien == ()
    assert len(source) == 1
    assert source[0].mode == 'active'

    record = q.records[0]
    states = {row.domain_id: row.state for row in record.domain_evidence}
    assert states['alien'] == 'quarantined'
    assert states['source'] == 'active'


def test_clean_evidence_window_promotes_domain_and_conflicting_duplicate_is_rejected():
    s = skill('promote')
    lib = admit_skill(OpenEndedLibraryVersion(0, ()), s)
    rows = (
        TransferObservation('t1', 'target', s.skill_id, True, True, 100, 80),
        TransferObservation('t2', 'target', s.skill_id, True, True, 100, 70),
    )
    promoted = apply_transfer_observations(lib, rows, min_window=2, min_cost_reduction=.1)
    decision = route_skills(promoted, DomainDescriptor('target', ('periodic', 'guarded')), max_capacity=2)
    assert len(decision) == 1
    assert decision[0].mode == 'active'

    conflict = TransferObservation('t1', 'target', s.skill_id, True, False, 100, 80)
    with pytest.raises(ValueError, match='conflicting duplicate'):
        apply_transfer_observations(lib, (rows[0], conflict))


def test_capacity_is_deterministic_prefers_validated_multi_domain_value_and_rollback_restores_snapshot():
    low = skill('low', tags=('guarded', 'periodic'), domains=('source',), cost=2)
    high = skill('high', tags=('guarded', 'periodic'), domains=('source',), cost=2)
    lib = admit_skill(OpenEndedLibraryVersion(0, ()), low)
    lib = admit_skill(lib, high)

    high_rows = (
        TransferObservation('h1', 'd1', high.skill_id, True, True, 100, 50),
        TransferObservation('h2', 'd1', high.skill_id, True, True, 100, 50),
        TransferObservation('h3', 'd2', high.skill_id, True, True, 100, 60),
        TransferObservation('h4', 'd2', high.skill_id, True, True, 100, 60),
    )
    enriched = apply_transfer_observations(lib, high_rows, min_window=2, min_cost_reduction=.1)
    bounded_a = enforce_capacity(enriched, 2)
    bounded_b = enforce_capacity(enriched, 2)
    assert bounded_a == bounded_b
    kept = [r.skill.skill_id for r in bounded_a.records if r.state != 'retired']
    assert kept == [high.skill_id]
    assert bounded_a.capacity_used == 2

    rolled = rollback_to_snapshot(bounded_a, enriched)
    assert rolled.version == bounded_a.version + 1
    assert rolled.parent_version == bounded_a.version
    assert rolled.rollback_of == bounded_a.version
    assert rolled.records == enriched.records
    assert rolled.capacity_used == enriched.capacity_used
