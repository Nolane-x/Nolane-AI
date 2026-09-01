from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.coding import PatchVerificationEvidence
from cogcoder.organization.coding_profiles import CodingDomain, CodingWorkRequest
from cogcoder.organization.coding_patches import CodingPatchStatus
from cogcoder.organization.planning import PlanNode
from cogcoder.organization.requirements import AcceptanceCriterion, RequirementKind, RequirementNode
from cogcoder.organization.runtime import OrganizationRuntime


def _seed_authorities(runtime):
    runtime.requirements.apply_revision(
        actor_agent_id='requirements.chief',
        reason='seed coding requirement', evidence_refs=('EV-REQ-SEED',),
        upserts=(RequirementNode(
            'REQ-1', 'Auth refresh', RequirementKind.FUNCTIONAL, 'refresh tokens safely',
            acceptance_criteria=(AcceptanceCriterion('AC-1', 'refresh succeeds'),),
        ),),
    )
    runtime.planning.apply_revision(
        actor_agent_id='planning.chief',
        reason='seed coding plan', evidence_refs=('EV-PLAN-SEED',),
        upsert_nodes=(PlanNode('P-1', 'Implement auth refresh', requirement_refs=('REQ-1',)),),
    )
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief',
        reason='seed auth component', evidence_refs=('EV-ARCH-SEED',),
        upsert_components=(ArchitectureComponent(
            'COMP-AUTH', 'Auth Service', ComponentKind.SERVICE,
            'core-coding', 'internal', requirement_refs=('REQ-1',), plan_refs=('P-1',),
        ),),
    )


def _request(runtime, *, work_id='W-1'):
    return CodingWorkRequest(
        work_id=work_id,
        task_id='T-1',
        plan_node_id='P-1',
        requirement_refs=('REQ-1',),
        architecture_version=runtime.architecture.graph.version,
        plan_version=runtime.planning.graph.version,
        requested_domains=(CodingDomain.BACKEND,),
        scope_hints=('service', 'api'),
        acceptance_refs=('AC-1',),
        priority=50,
        requester_agent_id='coding.chief',
        evidence_refs=('EV-WORK-1',),
    )


def _prepared_runtime(*, compile_refs=('EV-COMPILE-1',), test_refs=('EV-TEST-1',)):
    runtime = OrganizationRuntime.first_generation()
    _seed_authorities(runtime)
    runtime.tasks.add_task('T-1', title='Implement auth refresh', plan_node_id='P-1')
    runtime.tasks.lease('T-1', 'coding.backend.01')
    assignment = runtime.coding.request_work(_request(runtime))
    assert assignment.selected_agent_id == 'coding.backend.01'
    runtime.coding.claim_sources(
        agent_id='coding.backend.01', task_id='T-1',
        file_paths=('src/api/auth.py',), symbol_ids=('AuthService.refresh',),
    )
    patch = runtime.coding.submit_patch(
        producer_agent_id='coding.backend.01', task_id='T-1', work_id='W-1',
        touched_files=('src/api/auth.py',), touched_symbols=('AuthService.refresh',),
        patch_artifact_id='artifact-patch-1',
        compile_evidence_refs=compile_refs,
        test_evidence_refs=test_refs,
        static_evidence_refs=('EV-TYPE-1',),
    )
    return runtime, patch


def _good_verifier(evidence_id='EV-VERIFY-GOOD'):
    return PatchVerificationEvidence(
        evidence_id=evidence_id,
        verifier_agent_id='verification.unit-property.01',
        passed=True, false_accepts=0, regressions=0,
    )


def test_readiness_requires_independent_clean_verifier_and_all_execution_evidence():
    runtime, patch = _prepared_runtime()

    self_verification = runtime.coding.assess_readiness(
        patch.patch_id,
        PatchVerificationEvidence(
            evidence_id='EV-VERIFY-SELF', verifier_agent_id='coding.backend.01',
            passed=True, false_accepts=0, regressions=0,
        ),
    )
    assert self_verification.ready is False
    assert 'self_verification_forbidden' in self_verification.reasons

    failed = runtime.coding.assess_readiness(
        patch.patch_id,
        PatchVerificationEvidence(
            evidence_id='EV-VERIFY-BAD', verifier_agent_id='verification.unit-property.01',
            passed=True, false_accepts=1, regressions=0,
        ),
    )
    assert failed.ready is False
    assert 'verification_false_accepts' in failed.reasons

    clean = runtime.coding.assess_readiness(patch.patch_id, _good_verifier())
    assert clean.ready is True
    assert clean.reasons == ()
    assert clean.patch_id == patch.patch_id
    assert runtime.coding.patches.get_patch(patch.patch_id).status is CodingPatchStatus.EVIDENCE_READY


def test_missing_compile_or_test_evidence_blocks_readiness():
    runtime, patch = _prepared_runtime(compile_refs=(), test_refs=())
    receipt = runtime.coding.assess_readiness(patch.patch_id, _good_verifier('EV-VERIFY-2'))
    assert receipt.ready is False
    assert 'missing_compile_evidence' in receipt.reasons
    assert 'missing_test_evidence' in receipt.reasons


def test_unclaimed_scope_and_stale_authoritative_versions_block_readiness():
    runtime, patch = _prepared_runtime()
    runtime.coding.claims.release(
        runtime.coding.claims.active_claims()[0].claim_id,
        actor_agent_id='coding.backend.01',
    )
    runtime.planning.apply_revision(
        actor_agent_id='planning.chief',
        reason='add rollback node', evidence_refs=('EV-PLAN-NEW',),
        upsert_nodes=(PlanNode('P-ROLLBACK', 'Rollback auth change', dependencies=('P-1',), requirement_refs=('REQ-1',)),),
    )
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief',
        reason='add session component', evidence_refs=('EV-ARCH-NEW',),
        upsert_components=(ArchitectureComponent(
            'COMP-SESSION', 'Session Service', ComponentKind.SERVICE,
            'core-coding', 'internal', requirement_refs=('REQ-1',), plan_refs=('P-ROLLBACK',),
        ),),
    )

    receipt = runtime.coding.assess_readiness(patch.patch_id, _good_verifier('EV-VERIFY-3'))
    assert receipt.ready is False
    assert 'unclaimed_source_scope' in receipt.reasons
    assert 'stale_plan_version' in receipt.reasons
    assert 'stale_architecture_version' in receipt.reasons
