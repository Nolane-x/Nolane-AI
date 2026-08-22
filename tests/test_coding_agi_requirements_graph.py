import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.requirements import (
    AcceptanceCriterion,
    RequirementKind,
    RequirementNode,
)
from cogcoder.organization.types import EventKind


def _req(req_id: str, *, deps=()):
    return RequirementNode(
        requirement_id=req_id,
        title=f'Requirement {req_id}',
        kind=RequirementKind.FUNCTIONAL,
        description='Durable bounded behavior',
        dependencies=tuple(deps),
        acceptance_criteria=(AcceptanceCriterion(f'AC-{req_id}', 'observable acceptance'),),
    )


def test_requirement_revision_is_owner_evidence_gated_and_atomic():
    runtime = OrganizationRuntime.first_generation()
    rev1 = runtime.requirements.apply_revision(
        actor_agent_id='requirements.chief', reason='establish intent',
        evidence_refs=('EV-RQ-1',), upserts=(_req('REQ-1'),),
    )
    assert rev1.version == 1
    before = runtime.requirements.to_state()

    with pytest.raises(PermissionError):
        runtime.requirements.apply_revision(
            actor_agent_id='coding.backend.01', reason='silent rewrite',
            evidence_refs=('EV-RQ-2',), upserts=(_req('REQ-2'),),
        )
    assert runtime.requirements.to_state() == before

    with pytest.raises(ValueError):
        runtime.requirements.apply_revision(
            actor_agent_id='requirements.chief', reason='bad dependency',
            evidence_refs=('EV-RQ-3',), upserts=(_req('REQ-2', deps=('MISSING',)),),
        )
    assert runtime.requirements.to_state() == before


def test_requirement_dependency_cycle_rejects_without_partial_mutation():
    runtime = OrganizationRuntime.first_generation()
    runtime.requirements.apply_revision(
        actor_agent_id='requirements.chief', reason='seed', evidence_refs=('EV-A',),
        upserts=(_req('REQ-A'), _req('REQ-B', deps=('REQ-A',))),
    )
    before = runtime.requirements.to_state()
    with pytest.raises(ValueError, match='cycle'):
        runtime.requirements.apply_revision(
            actor_agent_id='requirements.chief', reason='introduce cycle', evidence_refs=('EV-B',),
            upserts=(_req('REQ-A', deps=('REQ-B',)),),
        )
    assert runtime.requirements.to_state() == before


def test_worker_can_propose_ambiguity_without_mutating_requirements():
    runtime = OrganizationRuntime.first_generation()
    runtime.requirements.apply_revision(
        actor_agent_id='requirements.chief', reason='seed', evidence_refs=('EV-RQ-4',),
        upserts=(_req('REQ-1'),),
    )
    before = runtime.requirements.to_state()
    event = runtime.requirements.propose_ambiguity(
        source_agent_id='coding.backend.01', requirement_id='REQ-1',
        question='What latency is acceptable?', evidence_refs=('EV-RQ-5',),
    )
    assert event.kind is EventKind.REQUIREMENT_AMBIGUITY
    assert event.target_agent_id == 'requirements.chief'
    assert runtime.requirements.to_state() == before
