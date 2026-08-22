import pytest

from cogcoder.organization.central_conflicts import CentralConflictRegistry, ConflictStatus


def test_conflict_requires_competing_claims_and_resolution_evidence():
    registry = CentralConflictRegistry()
    with pytest.raises(ValueError):
        registry.open(
            submitted_by=('coding.chief',),
            regions=('core-coding',),
            object_refs=('architecture-graph',),
            claims=(('coding.chief', 'single claim', ('ev-one',)),),
            severity=80,
        )

    packet = registry.open(
        submitted_by=('coding.chief', 'architecture.chief'),
        regions=('core-coding', 'architecture-system'),
        object_refs=('architecture-graph',),
        claims=(
            ('coding.chief', 'interface can remain mutable', ('ev-c1',)),
            ('architecture.chief', 'interface must freeze', ('ev-c2',)),
        ),
        severity=80,
        affected_refs=('task:T-1', 'plan:P-7'),
    )
    assert packet.conflict_id == 'conflict-00000001'
    assert packet.status is ConflictStatus.OPEN

    with pytest.raises(ValueError):
        registry.resolve(
            packet.conflict_id,
            resolver_agent_id='nolane.central',
            decision='freeze interface',
            rationale='missing evidence',
            evidence_refs=(),
        )

    resolved = registry.resolve(
        packet.conflict_id,
        resolver_agent_id='nolane.central',
        decision='freeze interface',
        rationale='cross-region compatibility evidence',
        evidence_refs=('ev-resolution',),
    )
    assert resolved.status is ConflictStatus.RESOLVED
    assert resolved.resolver_agent_id == 'nolane.central'


def test_conflict_state_roundtrip_and_severity_is_bounded():
    registry = CentralConflictRegistry()
    with pytest.raises(ValueError):
        registry.open(
            submitted_by=('coding.chief', 'architecture.chief'),
            regions=('core-coding', 'architecture-system'),
            object_refs=('architecture-graph',),
            claims=(
                ('coding.chief', 'a', ('ev-a',)),
                ('architecture.chief', 'b', ('ev-b',)),
            ),
            severity=101,
        )

    registry.open(
        submitted_by=('coding.chief', 'architecture.chief'),
        regions=('core-coding', 'architecture-system'),
        object_refs=('architecture-graph',),
        claims=(
            ('coding.chief', 'a', ('ev-a',)),
            ('architecture.chief', 'b', ('ev-b',)),
        ),
        severity=60,
    )
    restored = CentralConflictRegistry.from_state(registry.to_state())
    assert restored.to_state() == registry.to_state()
