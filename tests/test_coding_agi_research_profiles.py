from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.research_profiles import ResearchDomain, ResearchProfileRegistry, ResearchWorkRequest


def _request(work_id, domain, requester='coding.backend.01', *signals):
    return ResearchWorkRequest(
        work_id=work_id, question='bounded engineering research question', requested_domains=(domain,),
        scope_hints=tuple(signals), priority=80, requester_agent_id=requester,
        evidence_refs=(f'EV-{work_id}',),
    )


def test_exact_four_research_profiles_and_cross_region_requests():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = ResearchProfileRegistry(registry)
    rows = profiles.profiles()
    assert len(rows) == 4
    assert {row.agent_id for row in rows} == {
        'research.chief', 'research.repo-archaeology.01', 'research.docs-api.01', 'research.prior-art.01'
    }
    assert all(row.region == 'research-external' for row in rows)
    assert profiles.route(_request('R-1', ResearchDomain.REPOSITORY_ARCHAEOLOGY, 'planning.chief', 'history')).selected_agent_id == 'research.repo-archaeology.01'
    assert profiles.route(_request('R-2', ResearchDomain.DOCS_API, 'coding.backend.01', 'official-docs')).selected_agent_id == 'research.docs-api.01'
    assert profiles.route(_request('R-3', ResearchDomain.PRIOR_ART, 'architecture.chief', 'paper')).selected_agent_id == 'research.prior-art.01'
    assert profiles.route(_request('R-4', ResearchDomain.CROSS_RESEARCH, 'nolane.central', 'synthesis')).selected_agent_id == 'research.chief'


def test_research_profile_snapshot_tracks_current_neural_version():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = ResearchProfileRegistry(registry)
    registry.accept_neural_version('research.docs-api.01', 'docs-api-delta-0.2')
    state = profiles.to_state()
    row = next(x for x in state['profiles'] if x['agent_id'] == 'research.docs-api.01')
    assert row['accepted_neural_version'] == 'docs-api-delta-0.2'
    restored = ResearchProfileRegistry.from_state(registry, state)
    assert restored.get('research.docs-api.01').accepted_neural_version == 'docs-api-delta-0.2'
