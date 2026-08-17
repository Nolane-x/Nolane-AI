from cogcoder.r253_operator_catalog import build_default_externalization_catalog


ORIGINAL_FAMILIES = {
    'factual_knowledge', 'episodic_memory', 'working_memory', 'planning', 'search',
    'verification', 'world_model', 'tool_knowledge', 'skill_library', 'representation',
    'uncertainty_tracking', 'information_acquisition', 'counterexample_memory',
    'credit_assignment', 'self_improvement', 'attention_routing', 'multi_agent_cognition',
    'temporal_reasoning', 'causal_reasoning', 'mathematical_reasoning',
    'code_reasoning', 'metacognition',
}

ADDITIONAL_FAMILIES = {
    'goal_utility', 'constraint_invariants', 'resource_management',
    'observation_normalization', 'action_control', 'communication_clarification',
    'analogical_transfer', 'abstraction_formation', 'hypothesis_generation',
    'counterfactual_reasoning', 'consolidation_forgetting', 'curiosity_exploration',
    'identity_provenance', 'recovery_rollback', 'stopping_termination',
    'capability_boundary',
}


def test_catalog_covers_original_and_additional_externalization_families():
    catalog = build_default_externalization_catalog()
    families = {family.family_id for family in catalog}
    assert ORIGINAL_FAMILIES <= families
    assert ADDITIONAL_FAMILIES <= families
    assert len(families) >= 38


def test_every_family_has_many_distinct_granular_suboperators_and_explicit_status():
    catalog = build_default_externalization_catalog()
    all_ids = []
    for family in catalog:
        assert len(family.suboperators) >= 6, family.family_id
        for sub in family.suboperators:
            assert sub.operator_id.startswith(family.family_id + '.')
            assert sub.status in {'implemented', 'host_required', 'knowledge_only', 'experimental'}
            assert sub.summary.strip()
            assert sub.tags
            all_ids.append(sub.operator_id)
    assert len(all_ids) == len(set(all_ids))
    assert len(all_ids) >= 250
