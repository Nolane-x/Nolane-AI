from cogcoder.organization.architecture import ArchitectureComponent, ArchitectureEdge, ComponentKind, EdgeKind
from cogcoder.organization.architecture_reconciliation import ArchitectureDriftClass, ArchitectureObservation, ArchitectureReconciler
from cogcoder.organization.runtime import OrganizationRuntime


def test_architecture_reconciler_reports_drift_without_mutation():
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief', reason='seed', evidence_refs=('EV-R-1',),
        upsert_components=(
            ArchitectureComponent('A','A',ComponentKind.MODULE,'core-coding','internal'),
            ArchitectureComponent('B','B',ComponentKind.MODULE,'core-coding','internal'),
        ),
        upsert_edges=(ArchitectureEdge('E-B-A','B','A',EdgeKind.DEPENDS_ON),),
    )
    before = runtime.architecture.to_state()
    observation = ArchitectureObservation(
        observed_component_ids=('A','B','C'),
        observed_dependency_pairs=(('A','B'),),
        interface_signature_digests=(),
        source_refs=('REPO-SNAPSHOT-1',),
    )
    findings = ArchitectureReconciler(runtime.architecture.graph).scan(observation)
    kinds = {row.drift_class for row in findings}
    assert ArchitectureDriftClass.UNDECLARED_COMPONENT in kinds
    assert ArchitectureDriftClass.UNDECLARED_DEPENDENCY in kinds
    assert runtime.architecture.to_state() == before


def test_architecture_and_integration_chiefs_remain_direct_workers():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-ARCH', title='Repair module boundary', plan_node_id='P-ARCH')
    runtime.tasks.lease('T-ARCH', 'architecture.chief')
    arch_artifact = runtime.artifacts.put(
        kind='architecture-analysis', producer_agent_id='architecture.chief',
        content='boundary repair with ADR', evidence_refs=('EV-DW-A',),
    )
    arch_receipt = runtime.chief_direct_work(
        'architecture.chief', 'T-ARCH', output_artifact_ids=(arch_artifact.artifact_id,),
    )
    assert arch_receipt['chief_agent_id'] == 'architecture.chief'

    runtime.tasks.add_task('T-INT', title='Adjudicate integration conflict', plan_node_id='P-INT')
    runtime.tasks.lease('T-INT', 'integration.chief')
    int_artifact = runtime.artifacts.put(
        kind='integration-analysis', producer_agent_id='integration.chief',
        content='compatibility conflict resolution', evidence_refs=('EV-DW-I',),
    )
    int_receipt = runtime.chief_direct_work(
        'integration.chief', 'T-INT', output_artifact_ids=(int_artifact.artifact_id,),
    )
    assert int_receipt['chief_agent_id'] == 'integration.chief'
