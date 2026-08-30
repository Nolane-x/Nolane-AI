from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane
from nolane.external_core.software_engineering_impact import (
    EngineeringDependencyGraphLedger,
    EngineeringTestCoverageLedger,
)
from nolane.external_core.software_engineering_impact_execution_control import (
    ExecutionBoundDerivedImpactEngineeringControl,
)


def _setup():
    patch = CodingPatchCandidate(
        patch_id='patch-exec-retry-1',
        producer_agent_id='coding.backend.01',
        task_id='task-exec-retry-1',
        work_id='coding-work-exec-retry-1',
        base_plan_version=14,
        base_architecture_version=15,
        touched_files=('src/retry.py',),
        touched_symbols=('Retry.run',),
        patch_artifact_id='artifact:retry-patch',
        compile_evidence_refs=('compile:legacy',),
        test_evidence_refs=('test:legacy',),
        static_evidence_refs=('static:legacy',),
        status=CodingPatchStatus.VERIFIED,
    )
    claims = CodeClaimLedger()
    claim = claims.claim(
        agent_id=patch.producer_agent_id,
        task_id=patch.task_id,
        file_paths=patch.touched_files,
        symbol_ids=patch.touched_symbols,
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    plane = SoftwareEngineeringControlPlane(claims=claims)
    graphs = EngineeringDependencyGraphLedger()
    graph = graphs.register(
        source_revision='git:exec-retry',
        nodes=('symbol:Retry.run',),
        dependency_edges=(),
        component_membership={'symbol:Retry.run': 'component:retry'},
        provenance_refs=('static:exec-retry',),
    )
    coverages = EngineeringTestCoverageLedger()
    coverage = coverages.register(
        source_revision='git:exec-retry',
        graph_id=graph.graph_id,
        graph_digest=graph.digest,
        test_to_nodes={'tests/test_retry.py::test_run': ('symbol:Retry.run',)},
        provenance_refs=('coverage:exec-retry',),
    )
    strict = ExecutionBoundDerivedImpactEngineeringControl(
        plane=plane,
        dependency_graphs=graphs,
        test_coverage=coverages,
    )
    work = strict.begin_patch(
        patch=patch,
        source_revision='git:exec-retry',
        rollback_artifact_ref='artifact:rollback-retry',
        claim_refs=(claim.claim_id,),
        dependency_graph_id=graph.graph_id,
        test_coverage_id=coverage.coverage_id,
    )
    return patch, strict, work


def _coding_ready(patch_id):
    verification = PatchVerificationEvidence(
        evidence_id='verify:exec-retry',
        verifier_agent_id='verification.testing.01',
        passed=True,
    )
    payload = {
        'receipt_id': 'coding-ready-exec-retry',
        'patch_id': patch_id,
        'ready': True,
        'reasons': [],
        'verification': verification.to_state(),
    }
    return CodingReadinessReceipt(
        receipt_id=payload['receipt_id'], patch_id=patch_id, ready=True,
        reasons=(), verification=verification, digest=canonical_digest(payload),
    )


def test_failed_execution_attempt_can_be_superseded_without_rewriting_history():
    _, strict, work = _setup()
    selection = strict.selection(strict.binding_for_work(work.work_id).selection_id)
    failed = strict.record_test_execution(
        work.work_id,
        source_revision='git:exec-retry',
        environment_digest='env:py313',
        executed_tests=selection.selected_tests,
        failed_tests=selection.selected_tests,
        evidence_refs=('pytest:attempt-1',),
    )
    passed = strict.record_test_execution(
        work.work_id,
        source_revision='git:exec-retry',
        environment_digest='env:py313',
        executed_tests=selection.selected_tests,
        failed_tests=(),
        evidence_refs=('pytest:attempt-2',),
    )
    assert not failed.passed and passed.passed
    assert failed.execution_id != passed.execution_id
    assert strict.test_executions.get(failed.execution_id) == failed
    assert strict.test_execution_for_work(work.work_id) == passed


def test_candidate_requires_test_attestation_environment_to_match_execution():
    patch, strict, work = _setup()
    selection = strict.selection(strict.binding_for_work(work.work_id).selection_id)
    execution = strict.record_test_execution(
        work.work_id,
        source_revision='git:exec-retry',
        environment_digest='env:py313',
        executed_tests=selection.selected_tests,
        failed_tests=(),
        evidence_refs=('pytest:attempt-green',),
    )
    attestations = []
    for kind in (EngineeringEvidenceKind.COMPILE, EngineeringEvidenceKind.TEST, EngineeringEvidenceKind.STATIC):
        environment = 'env:different' if kind is EngineeringEvidenceKind.TEST else 'env:py313'
        dependencies = (f'execution:{execution.execution_id}',) if kind is EngineeringEvidenceKind.TEST else (f'artifact:{kind.value}',)
        attestations.append(strict.record_evidence(
            patch=patch,
            source_revision='git:exec-retry',
            environment_digest=environment,
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}',),
            dependencies=dependencies,
        ))
    strict.verify_preconditions(work.transaction_id, attestation_ids=(attestations[0].attestation_id,))
    mutation = strict.assess_mutation_authority(work.work_id, patch=patch)
    strict.mark_applied(
        work.transaction_id,
        application_ref='workspace:retry-apply',
        mutation_authority_receipt_id=mutation.receipt_id,
    )
    strict.observe_outcome(work.transaction_id, evidence_refs=('runtime:retry',))
    strict.verify_postconditions(
        work.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    receipt = strict.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:exec-retry',
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert not receipt.ready
    assert 'test_attestation_environment_mismatch' in receipt.reasons
    assert receipt.inner_gate_receipt_id is None
