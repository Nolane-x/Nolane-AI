import pytest

from cogcoder.organization.central_resources import CentralResourceArbiter


def test_resource_allocation_is_exact_and_overallocation_has_no_partial_mutation():
    arbiter = CentralResourceArbiter({'compute': 100, 'agent_slots': 8})
    receipt = arbiter.allocate(
        beneficiary='coding.backend.01',
        resource='compute',
        amount=30,
        reason='compile repair candidate',
        evidence_refs=('evidence-r1',),
    )
    assert receipt.allocation_id == 'alloc-00000001'
    assert receipt.before_available == 100
    assert receipt.after_available == 70
    assert arbiter.available('compute') == 70
    assert arbiter.leased_to('coding.backend.01', 'compute') == 30

    before = arbiter.to_state()
    with pytest.raises(ValueError):
        arbiter.allocate(
            beneficiary='coding.backend.01',
            resource='compute',
            amount=71,
            reason='over budget',
            evidence_refs=('evidence-r2',),
        )
    assert arbiter.to_state() == before


def test_resource_release_is_bounded_and_replayable():
    arbiter = CentralResourceArbiter({'compute': 100})
    allocation = arbiter.allocate(
        beneficiary='debug.chief',
        resource='compute',
        amount=40,
        reason='trace investigation',
        evidence_refs=('evidence-r3',),
    )
    release = arbiter.release(
        allocation.allocation_id,
        amount=15,
        reason='trace phase complete',
        evidence_refs=('evidence-r4',),
    )
    assert release.release_id == 'release-00000001'
    assert release.before_leased == 40
    assert release.after_leased == 25
    assert arbiter.available('compute') == 75

    with pytest.raises(ValueError):
        arbiter.release(
            allocation.allocation_id,
            amount=26,
            reason='invalid over-release',
            evidence_refs=('evidence-r5',),
        )

    restored = CentralResourceArbiter.from_state(arbiter.to_state())
    assert restored.to_state() == arbiter.to_state()


def test_resource_mutations_require_reason_and_evidence():
    arbiter = CentralResourceArbiter({'compute': 10})
    with pytest.raises(ValueError):
        arbiter.allocate(
            beneficiary='coding.chief', resource='compute', amount=1,
            reason='', evidence_refs=('evidence-r6',),
        )
    with pytest.raises(ValueError):
        arbiter.allocate(
            beneficiary='coding.chief', resource='compute', amount=1,
            reason='missing evidence', evidence_refs=(),
        )
