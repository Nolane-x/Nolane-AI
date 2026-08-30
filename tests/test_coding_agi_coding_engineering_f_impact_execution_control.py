from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringPhase
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane
from nolane.external_core.software_engineering_impact import (
    EngineeringDependencyGraphLedger,
    EngineeringTestCoverageLedger,
)
from nolane.external_core.software_engineering_impact_control import DerivedImpactEngineeringControl


def _patch():
    return CodingPatchCandidate(
        patch_id='patch-exec-control-1',
        producer_agent_id='coding.backend.01',
        task_id='task-exec-control-1',
        work_id='coding-work-exec-control-1',
        base_plan_version=12,
        base_architecture_version=13,
        touched_files=('src/a.py',),
        touched_symbols=('A.run',),
        patch_artifact_id='artifact:exec-control-patch',
        compile_evidence_refs=('compile:legacy',),
        test_evidence_refs=('test:legacy',),
        static_evidence_refs=('static:legacy',),
        status=CodingPatchStatus.VERIFIED,
    )


def _coding_ready(patch_id):
    verification = PatchVerificationEvidence(
        evidence_id='verify:exec-control',
        verifier_agent_id='verification.testing.01',
        passed=True,
    )
    payload = {
        'receipt_id': 'coding-ready-exec-control',
        'patch_id': patch_id,
        'ready': True,
        'reasons': [],
        'verification': verification.to_state(),
    }
    return CodingReadinessReceipt(
        receipt_id=payload['receipt_id'],
        patch_id=patch_id,
        ready=True,
        reasons=(),
        verification=verification,
        digest=canonical_digest(payload),
    )


def _control():
    patch = _patch()
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
        source_revision='git:exec-control',
        nodes=('symbol:A.run', 'symbol:B.call'),
        dependency_edges=(('symbol:A.run', 'symbol:B.call'),),
        component_membership={
            'symbol:A.run': 'component:a',
            'symbol:B.call': 'component:b',
        },
        provenance_refs=('static:exec-control',),
    )
    coverages = EngineeringTestCoverageLedger()
    coverage = coverages.register(
        source_revision='git:exec-control',
        graph_id=graph.graph_id,
        graph_digest=graph.digest,
        test_to_nodes={
            'tests/test_a.py::test_run': ('symbol:A.run',),
            'tests/test_b.py::test_call': ('symbol:B.call',),
        },
        provenance_refs=('coverage:exec-control',),
    )
    strict = DerivedImpactEngineeringControl(
        plane=plane,
        dependency_graphs=graphs,
        test_coverage=coverages,
    )
    work = strict.begin_patch(
        patch=patch,
        source_revision='git:exec-control',
        rollback_artifact_ref='artifact:rollback-exec-control',
        claim_refs=(claim.claim_id,),
        dependency_graph_id=graph.graph_id,
        test_coverage_id=coverage.coverage_id,
    )
    return patch, claims, strict, work


def _postconditions(strict, patch, work, *, bind_execution, fail_selected=False):
    binding = strict.binding_for_work(work.work_id)
    selection = strict.selection(binding.selection_id)
    execution = None
    if bind_execution:
        execution = strict.record_test_execution(
            work.work_id,
            source_revision='git:exec-control',
            environment_digest='env:py313',
            executed_tests=selection.selected_tests,
            failed_tests=(selection.selected_tests[0],) if fail_selected else (),
            evidence_refs=('pytest:junit:exec-control',),
        )

    attestations = []
    for kind in (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    ):
        dependencies = [f'artifact:{kind.value}:exec-control']
        if kind is EngineeringEvidenceKind.TEST and execution is not None:
            dependencies.append(f'execution:{execution.execution_id}')
        attestations.append(strict.record_evidence(
            patch=patch,
            source_revision='git:exec-control',
            environment_digest='env:py313',
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}:exec-control',),
            dependencies=tuple(dependencies),
        ))

    strict.verify_preconditions(work.transaction_id, attestation_ids=(attestations[0].attestation_id,))
    mutation = strict.assess_mutation_authority(work.work_id, patch=patch)
    strict.mark_applied(
        work.transaction_id,
        application_ref='workspace:apply-exec-control',
        mutation_authority_receipt_id=mutation.receipt_id,
    )
    strict.observe_outcome(work.transaction_id, evidence_refs=('runtime:exec-control',))
    strict.verify_postconditions(
        work.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    return tuple(row.attestation_id for row in attestations), execution


def test_complete_selection_without_execution_receipt_blocks_candidate():
    patch, _, strict, work = _control()
    attestations, _ = _postconditions(strict, patch, work, bind_execution=False)
    receipt = strict.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:exec-control',
        attestation_ids=attestations,
    )
    assert not receipt.ready
    assert 'missing_differential_test_execution' in receipt.reasons
    assert receipt.inner_gate_receipt_id is None
    assert strict.plane.transactions.get(work.transaction_id).phase is EngineeringPhase.POSTCONDITIONS_VERIFIED


def test_failed_selected_test_execution_blocks_candidate():
    patch, _, strict, work = _control()
    attestations, execution = _postconditions(strict, patch, work, bind_execution=True, fail_selected=True)
    assert execution is not None and not execution.passed
    receipt = strict.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:exec-control',
        attestation_ids=attestations,
    )
    assert not receipt.ready
    assert 'differential_test_execution_failed' in receipt.reasons
    assert receipt.inner_gate_receipt_id is None


def test_green_execution_without_attestation_dependency_is_not_accepted():
    patch, _, strict, work = _control()
    binding = strict.binding_for_work(work.work_id)
    selection = strict.selection(binding.selection_id)
    execution = strict.record_test_execution(
        work.work_id,
        source_revision='git:exec-control',
        environment_digest='env:py313',
        executed_tests=selection.selected_tests,
        failed_tests=(),
        evidence_refs=('pytest:junit:exec-control',),
    )

    attestations = []
    for kind in (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    ):
        attestations.append(strict.record_evidence(
            patch=patch,
            source_revision='git:exec-control',
            environment_digest='env:py313',
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}:exec-control',),
            dependencies=(f'artifact:{kind.value}:exec-control',),
        ))
    assert execution.passed
    strict.verify_preconditions(work.transaction_id, attestation_ids=(attestations[0].attestation_id,))
    mutation = strict.assess_mutation_authority(work.work_id, patch=patch)
    strict.mark_applied(
        work.transaction_id,
        application_ref='workspace:apply-exec-control',
        mutation_authority_receipt_id=mutation.receipt_id,
    )
    strict.observe_outcome(work.transaction_id, evidence_refs=('runtime:exec-control',))
    strict.verify_postconditions(
        work.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    receipt = strict.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:exec-control',
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert not receipt.ready
    assert 'test_attestation_not_bound_to_execution' in receipt.reasons


def test_green_execution_bound_to_independent_test_attestation_allows_candidate():
    patch, claims, strict, work = _control()
    attestations, execution = _postconditions(strict, patch, work, bind_execution=True)
    assert execution is not None and execution.passed
    receipt = strict.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:exec-control',
        attestation_ids=attestations,
    )
    assert receipt.ready
    assert receipt.test_execution_id == execution.execution_id
    assert receipt.test_execution_digest == execution.digest

    restored = DerivedImpactEngineeringControl.from_state(claims=claims, state=strict.to_state())
    assert restored.test_execution_for_work(work.work_id) == execution
    assert restored.get(receipt.receipt_id) == receipt
