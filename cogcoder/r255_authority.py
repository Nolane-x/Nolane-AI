from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping


def _nonempty(value: str, name: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f'{name} must be non-empty')
    return value


def _frozen_nonempty(values: Iterable[str], name: str) -> frozenset[str]:
    out = frozenset(str(value).strip() for value in values if str(value).strip())
    if not out:
        raise ValueError(f'{name} must be non-empty')
    return out


def _payload(*, objective: str, allowed_actions: frozenset[str], allowed_side_effect_classes: frozenset[str], issuer: str, parent_digest: str) -> str:
    return json.dumps({
        'objective': objective,
        'allowed_actions': sorted(allowed_actions),
        'allowed_side_effect_classes': sorted(allowed_side_effect_classes),
        'issuer': issuer,
        'parent_digest': parent_digest,
    }, sort_keys=True, separators=(',', ':'))


def _digest(**kwargs) -> str:
    return hashlib.sha256(_payload(**kwargs).encode('utf-8')).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthorityEnvelope:
    """Host-issued, content-addressed action authority.

    External retrieval may *inform* cognition but may not mint or widen this envelope.  A child
    envelope can only narrow its parent's action and side-effect sets.  This keeps data-plane
    content from silently becoming control-plane authority even if a model follows an injection.
    """

    objective: str
    allowed_actions: frozenset[str]
    allowed_side_effect_classes: frozenset[str]
    issuer: str
    parent_digest: str = ''
    digest: str = ''

    trainable_parameter_count = 0

    @classmethod
    def issue(
        cls,
        *,
        objective: str,
        allowed_actions: Iterable[str],
        allowed_side_effect_classes: Iterable[str],
        issuer: str,
    ) -> 'AuthorityEnvelope':
        objective = _nonempty(objective, 'objective')
        issuer = _nonempty(issuer, 'issuer')
        if not issuer.startswith('host:'):
            raise ValueError('host authority required to issue envelope')
        actions = _frozen_nonempty(allowed_actions, 'allowed_actions')
        effects = _frozen_nonempty(allowed_side_effect_classes, 'allowed_side_effect_classes')
        digest = _digest(
            objective=objective,
            allowed_actions=actions,
            allowed_side_effect_classes=effects,
            issuer=issuer,
            parent_digest='',
        )
        return cls(objective, actions, effects, issuer, '', digest)

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> 'AuthorityEnvelope':
        actions = frozenset(map(str, raw.get('allowed_actions', ())))
        effects = frozenset(map(str, raw.get('allowed_side_effect_classes', ())))
        return cls(
            str(raw.get('objective', '')),
            actions,
            effects,
            str(raw.get('issuer', '')),
            str(raw.get('parent_digest', '')),
            str(raw.get('digest', '')),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            'objective': self.objective,
            'allowed_actions': sorted(self.allowed_actions),
            'allowed_side_effect_classes': sorted(self.allowed_side_effect_classes),
            'issuer': self.issuer,
            'parent_digest': self.parent_digest,
            'digest': self.digest,
        }

    def verify(self) -> bool:
        if not self.objective.strip() or not self.issuer.startswith('host:') or not self.allowed_actions or not self.allowed_side_effect_classes:
            return False
        expected = _digest(
            objective=self.objective,
            allowed_actions=self.allowed_actions,
            allowed_side_effect_classes=self.allowed_side_effect_classes,
            issuer=self.issuer,
            parent_digest=self.parent_digest,
        )
        return bool(self.digest) and self.digest == expected

    def narrow(
        self,
        *,
        objective: str,
        allowed_actions: Iterable[str],
        allowed_side_effect_classes: Iterable[str],
    ) -> 'AuthorityEnvelope':
        if not self.verify():
            raise ValueError('cannot narrow invalid authority envelope')
        objective = _nonempty(objective, 'objective')
        actions = _frozen_nonempty(allowed_actions, 'allowed_actions')
        effects = _frozen_nonempty(allowed_side_effect_classes, 'allowed_side_effect_classes')
        if not actions <= self.allowed_actions or not effects <= self.allowed_side_effect_classes:
            raise ValueError('cannot widen authority in child scope')
        digest = _digest(
            objective=objective,
            allowed_actions=actions,
            allowed_side_effect_classes=effects,
            issuer=self.issuer,
            parent_digest=self.digest,
        )
        return AuthorityEnvelope(objective, actions, effects, self.issuer, self.digest, digest)


@dataclass(frozen=True, slots=True)
class ActionProposal:
    action_id: str
    side_effect_class: str
    proposed_by: str
    source_uri: str

    def __post_init__(self) -> None:
        _nonempty(self.action_id, 'action_id')
        _nonempty(self.side_effect_class, 'side_effect_class')
        _nonempty(self.proposed_by, 'proposed_by')
        _nonempty(self.source_uri, 'source_uri')


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    allowed: bool
    reason: str
    action_id: str
    side_effect_class: str
    envelope_digest: str
    proposed_by: str
    source_uri: str


class AuthorityBoundary:
    """Fail-closed data-plane/control-plane separation for tool and operator actions."""

    trainable_parameter_count = 0

    def authorize(self, envelope: AuthorityEnvelope, proposal: ActionProposal) -> AuthorityDecision:
        if not envelope.verify():
            reason = 'invalid_authority_envelope'
            allowed = False
        elif proposal.action_id not in envelope.allowed_actions:
            reason = 'action_not_pre_authorized'
            allowed = False
        elif proposal.side_effect_class not in envelope.allowed_side_effect_classes:
            reason = 'side_effect_not_pre_authorized'
            allowed = False
        else:
            reason = 'authorized'
            allowed = True
        return AuthorityDecision(
            allowed,
            reason,
            proposal.action_id,
            proposal.side_effect_class,
            envelope.digest,
            proposal.proposed_by,
            proposal.source_uri,
        )
