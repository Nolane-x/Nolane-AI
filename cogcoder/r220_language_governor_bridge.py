from __future__ import annotations

import hashlib

from .r218_library_governor import admit_skill, route_skills
from .r218_transfer_types import DomainDescriptor, OpenEndedLibraryVersion, TransferSkill
from .r219_representation_types import LibraryAction
from .r220_operator_discovery import OperatorDiscoveryDecision


def decide_operator_library_action(decision: OperatorDiscoveryDecision, library: OpenEndedLibraryVersion, domain: DomainDescriptor) -> LibraryAction:
    if decision.status != 'accept' or decision.operator_id is None:
        return LibraryAction('abstain', None, None, 'operator_not_accepted')
    routes = route_skills(library, domain, max_capacity=1, min_overlap=.5, max_trials=1)
    if routes:
        best=routes[0]
        return LibraryAction('reuse', decision.operator_id, best.skill_id, f'r218_{best.mode}_route')
    return LibraryAction('create', decision.operator_id, None, 'no_reusable_representation_language_skill')


def _skill(decision: OperatorDiscoveryDecision, domain: DomainDescriptor, payload_ref: str, lineage: str) -> TransferSkill:
    assert decision.operator_id is not None
    tags=tuple(sorted(set(domain.mechanism_tags)|{'representation-language','operator-synthesis'}))
    behavior='|'.join(('r220-operator-language-v1',decision.operator_id,','.join(tags)))
    return TransferSkill(
        'representation-language-operator', tags, hashlib.sha256(behavior.encode()).hexdigest(),
        (payload_ref,), (lineage,), (domain.domain_id,), 1,
    )


def apply_verified_operator(decision: OperatorDiscoveryDecision, library: OpenEndedLibraryVersion, domain: DomainDescriptor, payload_ref: str, lineage: str) -> OpenEndedLibraryVersion:
    action=decide_operator_library_action(decision,library,domain)
    if action.action in {'abstain','reuse'}:
        return library
    return admit_skill(library,_skill(decision,domain,payload_ref,lineage))
