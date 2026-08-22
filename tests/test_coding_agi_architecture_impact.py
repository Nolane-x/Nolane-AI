from cogcoder.organization.architecture import (
    ArchitectureComponent,
    ArchitectureEdge,
    ComponentKind,
    EdgeKind,
    InterfaceClass,
    InterfaceContract,
    InterfaceStability,
)
from cogcoder.organization.change_impact import ChangeImpactEngine
from cogcoder.organization.compatibility import CompatibilityClass, CompatibilityEngine
from cogcoder.organization.runtime import OrganizationRuntime


def test_change_impact_finds_transitive_dependents_and_is_deterministic():
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief', reason='seed', evidence_refs=('EV-I-1',),
        upsert_components=(
            ArchitectureComponent('A', 'A', ComponentKind.MODULE, 'core-coding', 'internal', requirement_refs=('REQ-A',), plan_refs=('P-A',)),
            ArchitectureComponent('B', 'B', ComponentKind.MODULE, 'core-coding', 'internal', requirement_refs=('REQ-B',), plan_refs=('P-B',)),
            ArchitectureComponent('C', 'C', ComponentKind.MODULE, 'frontend-ui', 'internal', requirement_refs=('REQ-C',), plan_refs=('P-C',)),
        ),
        upsert_interfaces=(InterfaceContract('IF-A','A',InterfaceClass.API,'1.0.0','sig-1',InterfaceStability.PUBLIC),),
        upsert_edges=(
            ArchitectureEdge('E-B-A','B','A',EdgeKind.DEPENDS_ON),
            ArchitectureEdge('E-C-B','C','B',EdgeKind.DEPENDS_ON),
        ),
    )
    engine = ChangeImpactEngine(runtime.architecture.graph)
    first = engine.compute(changed_components=('A',), changed_interfaces=('IF-A',))
    second = engine.compute(changed_interfaces=('IF-A',), changed_components=('A',))
    assert first.digest == second.digest
    assert first.transitive_dependents == ('B', 'C')
    assert {'REQ-A','REQ-B','REQ-C'} <= set(first.requirement_refs)
    assert {'P-A','P-B','P-C'} <= set(first.plan_refs)
    assert 'integration' in first.required_verification_classes


def test_compatibility_is_fail_closed_for_changed_public_interface():
    unchanged = CompatibilityEngine.assess(
        old_signature_digest='sig-1', new_signature_digest='sig-1',
        old_semantic_version='1.0.0', new_semantic_version='1.0.1',
        stability=InterfaceStability.PUBLIC, adapter_evidence_refs=(), migration_evidence_refs=(),
    )
    assert unchanged.compatibility is CompatibilityClass.COMPATIBLE

    changed = CompatibilityEngine.assess(
        old_signature_digest='sig-1', new_signature_digest='sig-2',
        old_semantic_version='1.0.0', new_semantic_version='1.1.0',
        stability=InterfaceStability.PUBLIC, adapter_evidence_refs=(), migration_evidence_refs=(),
    )
    assert changed.compatibility in {CompatibilityClass.BREAKING, CompatibilityClass.UNKNOWN}
    assert not changed.integration_safe
