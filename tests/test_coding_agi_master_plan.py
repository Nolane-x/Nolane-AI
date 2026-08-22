import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.requirements import AcceptanceCriterion, RequirementKind, RequirementNode
from cogcoder.organization.planning import Milestone, PlanNode, PlanNodeStatus, PlanRisk


def _seed_requirement(runtime):
    runtime.requirements.apply_revision(
        actor_agent_id='requirements.chief', reason='seed requirement', evidence_refs=('EV-P-REQ',),
        upserts=(RequirementNode(
            requirement_id='REQ-1', title='Persistent jobs', kind=RequirementKind.FUNCTIONAL,
            description='Jobs survive restart',
            acceptance_criteria=(AcceptanceCriterion('AC-1', 'restart preserves pending job'),),
        ),),
    )


def _node(node_id, *, deps=(), reqs=('REQ-1',), status=PlanNodeStatus.PLANNED):
    return PlanNode(
        node_id=node_id, title=f'Plan {node_id}', dependencies=tuple(deps),
        requirement_refs=tuple(reqs), status=status,
    )


def test_master_plan_revision_requires_owner_and_known_requirement_refs():
    runtime = OrganizationRuntime.first_generation()
    _seed_requirement(runtime)
    rev = runtime.planning.apply_revision(
        actor_agent_id='planning.chief', reason='initial plan', evidence_refs=('EV-P-1',),
        upsert_nodes=(_node('P-1'),),
        milestones=(Milestone('M-1', 'Persistence ready', ('P-1',)),),
        risks=(PlanRisk('RISK-1', 'migration rollback', 70, ('P-1',)),),
    )
    assert rev.version == 1
    assert runtime.planning.graph.topological_order() == ('P-1',)
    assert runtime.planning.graph.ready_nodes() == ('P-1',)
    before = runtime.planning.to_state()

    with pytest.raises(PermissionError):
        runtime.planning.apply_revision(
            actor_agent_id='coding.backend.01', reason='silent plan edit', evidence_refs=('EV-P-2',),
            upsert_nodes=(_node('P-2'),),
        )
    assert runtime.planning.to_state() == before

    with pytest.raises(ValueError, match='requirement'):
        runtime.planning.apply_revision(
            actor_agent_id='planning.chief', reason='unknown requirement', evidence_refs=('EV-P-3',),
            upsert_nodes=(_node('P-X', reqs=('REQ-MISSING',)),),
        )
    assert runtime.planning.to_state() == before


def test_master_plan_cycle_rejection_is_atomic_and_depth_is_deterministic():
    runtime = OrganizationRuntime.first_generation()
    _seed_requirement(runtime)
    runtime.planning.apply_revision(
        actor_agent_id='planning.chief', reason='chain', evidence_refs=('EV-P-4',),
        upsert_nodes=(_node('P-A'), _node('P-B', deps=('P-A',))),
    )
    assert runtime.planning.graph.longest_dependency_depth() == 2
    before = runtime.planning.to_state()
    with pytest.raises(ValueError, match='cycle'):
        runtime.planning.apply_revision(
            actor_agent_id='planning.chief', reason='bad cycle', evidence_refs=('EV-P-5',),
            upsert_nodes=(_node('P-A', deps=('P-B',)),),
        )
    assert runtime.planning.to_state() == before


def test_rollback_creates_new_revision_instead_of_deleting_history():
    runtime = OrganizationRuntime.first_generation()
    _seed_requirement(runtime)
    first = runtime.planning.apply_revision(
        actor_agent_id='planning.chief', reason='v1', evidence_refs=('EV-P-6',),
        upsert_nodes=(_node('P-1'),),
    )
    runtime.planning.apply_revision(
        actor_agent_id='planning.chief', reason='v2', evidence_refs=('EV-P-7',),
        upsert_nodes=(_node('P-2', deps=('P-1',)),),
    )
    rolled = runtime.planning.rollback(
        actor_agent_id='planning.chief', source_revision=first.version,
        reason='rollback bad expansion', evidence_refs=('EV-P-8',),
    )
    assert rolled.version == 3
    assert rolled.source_revision == 1
    assert tuple(x.node_id for x in runtime.planning.graph.nodes()) == ('P-1',)
    assert len(runtime.planning.revisions()) == 3
