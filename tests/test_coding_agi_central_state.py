import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.central_state import CentralCapabilityMap, build_world_state


def test_capability_observation_requires_evidence_and_roundtrips():
    runtime = OrganizationRuntime.first_generation()
    mapping = CentralCapabilityMap(runtime.registry)

    with pytest.raises(ValueError):
        mapping.observe(
            agent_id='coding.backend.01',
            readiness=70,
            health=80,
            evidence_refs=(),
        )

    row = mapping.observe(
        agent_id='coding.backend.01',
        readiness=73,
        health=91,
        evidence_refs=('evidence-cap-1',),
    )
    assert row.observation_id == 'capobs-00000001'
    assert row.readiness == 73
    assert row.health == 91
    assert row.agent_id == 'coding.backend.01'

    restored = CentralCapabilityMap.from_state(runtime.registry, mapping.to_state())
    assert restored.to_state() == mapping.to_state()


def test_capability_scores_are_bounded_and_unknown_agents_fail_closed():
    runtime = OrganizationRuntime.first_generation()
    mapping = CentralCapabilityMap(runtime.registry)

    with pytest.raises(ValueError):
        mapping.observe(
            agent_id='coding.backend.01',
            readiness=101,
            health=50,
            evidence_refs=('evidence-cap-2',),
        )
    with pytest.raises(KeyError):
        mapping.observe(
            agent_id='missing.agent',
            readiness=50,
            health=50,
            evidence_refs=('evidence-cap-3',),
        )


def test_world_state_digest_changes_with_authoritative_state_and_is_deterministic():
    runtime = OrganizationRuntime.first_generation()
    mapping = CentralCapabilityMap(runtime.registry)
    before = build_world_state(runtime, mapping)
    again = build_world_state(runtime, mapping)
    assert before.digest == again.digest

    mapping.observe(
        agent_id='debug.chief',
        readiness=88,
        health=77,
        evidence_refs=('evidence-cap-4',),
    )
    after_observation = build_world_state(runtime, mapping)
    assert after_observation.digest != before.digest

    runtime.tasks.add_task('central-state-task', title='world-state probe', plan_node_id='P-central-state')
    after_task = build_world_state(runtime, mapping)
    assert after_task.digest != after_observation.digest
