from __future__ import annotations

import hashlib

from .r218_library_governor import admit_skill, route_skills
from .r218_transfer_types import DomainDescriptor, OpenEndedLibraryVersion, TransferSkill
from .r219_representation_types import DiscoveryDecision, LibraryAction


def _overlap(tags: tuple[str, ...], domain: DomainDescriptor) -> float:
    left = set(tags)
    if not left:
        return 0.0
    return len(left & set(domain.mechanism_tags)) / len(left)


def decide_library_action(decision: DiscoveryDecision, library: OpenEndedLibraryVersion, domain: DomainDescriptor) -> LibraryAction:
    if decision.status != 'accept' or decision.representation_id is None:
        return LibraryAction('abstain', None, None, 'representation_not_accepted')
    routes = route_skills(library, domain, max_capacity=1, min_overlap=0.5, max_trials=1)
    if routes:
        best = routes[0]
        return LibraryAction('reuse', decision.representation_id, best.skill_id, f'r218_{best.mode}_route')
    quarantined = []
    for record in library.records:
        if record.state == 'retired':
            continue
        evidence = record.evidence_for(domain.domain_id)
        if evidence is None or evidence.state != 'quarantined':
            continue
        overlap = _overlap(record.skill.mechanism_tags, domain)
        if overlap + 1e-12 >= 0.5:
            quarantined.append((-overlap, record.skill.capacity_cost, record.skill.skill_id))
    if quarantined:
        quarantined.sort()
        return LibraryAction('split', decision.representation_id, quarantined[0][2], 'local_quarantine_requires_new_representation_branch')
    return LibraryAction('create', decision.representation_id, None, 'no_reusable_skill_matches_verified_representation')


def _representation_skill(decision: DiscoveryDecision, domain: DomainDescriptor, payload_ref: str, lineage: str, *, action: str) -> TransferSkill:
    assert decision.representation_id is not None
    tags = tuple(sorted(set(domain.mechanism_tags) | {'representation-discovery'}))
    behavior = '|'.join(('r219-representation-alignment-v1', action, decision.representation_id, ','.join(tags)))
    return TransferSkill('representation-alignment', tags, hashlib.sha256(behavior.encode()).hexdigest(), (str(payload_ref),), (str(lineage),), (domain.domain_id,), 1)


def apply_verified_representation(decision: DiscoveryDecision, library: OpenEndedLibraryVersion, domain: DomainDescriptor, payload_ref: str, lineage: str) -> OpenEndedLibraryVersion:
    action = decide_library_action(decision, library, domain)
    if action.action in {'abstain', 'reuse'}:
        return library
    skill = _representation_skill(decision, domain, payload_ref, lineage, action=action.action)
    return admit_skill(library, skill)
