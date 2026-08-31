from __future__ import annotations


def test_memory_fabric_bridge_preserves_accepted_class_identity() -> None:
    from cogcoder.organization.memory import MemoryFabric as LegacyMemoryFabric
    from nolane.memory.fabric import MemoryFabric
    assert MemoryFabric is LegacyMemoryFabric


def test_memory_lifecycle_facade_preserves_accepted_class_identities() -> None:
    from cogcoder.organization.memory_lifecycle import (
        MemoryLifecycleLedger as LegacyLifecycle,
        MemoryRelationGraph as LegacyRelations,
    )
    from nolane.memory.lifecycle import MemoryLifecycleLedger, MemoryRelationGraph
    assert MemoryLifecycleLedger is LegacyLifecycle
    assert MemoryRelationGraph is LegacyRelations


def test_memory_retrieval_facade_preserves_accepted_class_identities() -> None:
    from cogcoder.organization.memory_retrieval import (
        MemoryRetrievalBudget as LegacyBudget,
        MemoryRetrievalEngine as LegacyEngine,
    )
    from nolane.memory.retrieval import MemoryRetrievalBudget, MemoryRetrievalEngine
    assert MemoryRetrievalBudget is LegacyBudget
    assert MemoryRetrievalEngine is LegacyEngine


def test_context_boundary_preserves_intelligence_and_control_plane_identity() -> None:
    from cogcoder.organization.context_intelligence import (
        ContextBudget as LegacyBudget,
        ContextIntelligenceCompiler as LegacyCompiler,
    )
    from cogcoder.organization.memory_context import MemoryContextControlPlane as LegacyControl
    from nolane.memory.context import ContextBudget, ContextIntelligenceCompiler, MemoryContextControlPlane
    assert ContextBudget is LegacyBudget
    assert ContextIntelligenceCompiler is LegacyCompiler
    assert MemoryContextControlPlane is LegacyControl


def test_experience_and_skill_boundaries_preserve_accepted_identity() -> None:
    from cogcoder.organization.evolution import SkillEvolutionEngine as LegacySkills
    from cogcoder.organization.experience import ExperienceLedger as LegacyExperience
    from nolane.memory.experience import ExperienceLedger
    from nolane.memory.skills import SkillEvolutionEngine
    assert ExperienceLedger is LegacyExperience
    assert SkillEvolutionEngine is LegacySkills


def test_memory_public_modules_have_independent_component_ownership() -> None:
    import nolane.memory.context as context
    import nolane.memory.experience as experience
    import nolane.memory.fabric as fabric
    import nolane.memory.lifecycle as lifecycle
    import nolane.memory.retrieval as retrieval
    import nolane.memory.skills as skills

    expected = {
        fabric: ("external.memory.fabric", "0.0.2"),
        lifecycle: ("external.memory.lifecycle", "0.0.4"),
        retrieval: ("external.memory.retrieval", "0.0.3"),
        context: ("external.context", "0.0.1"),
        experience: ("external.experience", "0.0.2"),
        skills: ("external.skills", "0.0.3"),
    }
    for module, (component_id, component_version) in expected.items():
        assert module.COMPONENT_ID == component_id
        assert module.COMPONENT_VERSION == component_version
        assert module.MIGRATED_FROM.startswith("cogcoder.organization.")
