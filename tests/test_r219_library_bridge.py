from cogcoder.r218_library_governor import admit_skill, initial_library, record_domain_evidence
from cogcoder.r218_transfer_types import DomainDescriptor, TransferSkill
from cogcoder.r219_library_bridge import apply_verified_representation, decide_library_action
from cogcoder.r219_representation_types import DiscoveryDecision


def _accepted(representation_id='repr:0123456789abcdef'):
    return DiscoveryDecision('accept', representation_id, 0.95, 0.4, ('q1',), 'verified')


def _domain(name='new-domain'):
    return DomainDescriptor(name, ('transition-system', 'representation-discovery'), ('queryable',))


def _compatible_skill():
    return TransferSkill('representation-alignment', ('representation-discovery', 'transition-system'), 'behavior-digest-1', ('payload:source',), ('lineage:source',), ('source-domain',), 1)


def test_ambiguous_discovery_abstains_without_mutating_library():
    library = initial_library(3)
    decision = DiscoveryDecision('abstain', None, 0.5, 0.0, ('q1',), 'ambiguous')
    action = decide_library_action(decision, library, _domain())
    assert action.action == 'abstain'
    assert apply_verified_representation(decision, library, _domain(), 'payload:x', 'lineage:x') is library


def test_verified_representation_reuses_compatible_skill_as_trial_route():
    library = admit_skill(initial_library(3), _compatible_skill())
    action = decide_library_action(_accepted(), library, _domain())
    assert action.action == 'reuse'
    assert action.skill_id == library.records[0].skill.skill_id
    assert 'trial' in action.reason
    assert apply_verified_representation(_accepted(), library, _domain(), 'payload:x', 'lineage:x') is library


def test_verified_representation_creates_skill_when_no_reusable_match_exists():
    library = initial_library(3)
    updated = apply_verified_representation(_accepted(), library, _domain(), 'payload:new', 'lineage:new')
    assert len(updated.records) == 1
    assert updated.records[0].skill.kind == 'representation-alignment'
    assert 'representation-discovery' in updated.records[0].skill.mechanism_tags


def test_local_quarantine_causes_split_without_erasing_source_domain_evidence():
    skill = _compatible_skill()
    library = admit_skill(initial_library(4), skill)
    library = record_domain_evidence(library, skill.skill_id, 'source-domain', passed=True, false_accept=False, cost_ratio=0.8)
    library = record_domain_evidence(library, skill.skill_id, 'source-domain', passed=True, false_accept=False, cost_ratio=0.8)
    library = record_domain_evidence(library, skill.skill_id, 'source-domain', passed=True, false_accept=False, cost_ratio=0.8)
    library = record_domain_evidence(library, skill.skill_id, 'new-domain', passed=False, false_accept=True, cost_ratio=1.0)
    action = decide_library_action(_accepted(), library, _domain())
    assert action.action == 'split'
    updated = apply_verified_representation(_accepted(), library, _domain(), 'payload:split', 'lineage:split')
    assert len(updated.records) == 2
    original = next(r for r in updated.records if r.skill.skill_id == skill.skill_id)
    assert original.evidence_for('source-domain').state == 'active'
    assert original.evidence_for('new-domain').state == 'quarantined'
