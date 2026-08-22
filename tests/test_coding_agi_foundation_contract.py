from cogcoder.organization.runtime import OrganizationRuntime


def test_every_permanent_identity_exposes_general_cognitive_contract_metadata():
    runtime = OrganizationRuntime.first_generation()
    required = {
        'goal_understanding',
        'task_decomposition',
        'local_planning',
        'causal_reasoning',
        'memory_use',
        'tool_use',
        'uncertainty',
        'evidence_handling',
        'communication',
        'self_evaluation',
        'skill_induction',
        'learning_from_feedback',
    }
    for identity in runtime.registry.identities():
        assert required <= set(identity.cognitive_capabilities)
