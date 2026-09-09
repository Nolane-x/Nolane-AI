import pytest

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
from nolane.external_core.software_engineering_impact_control import (
    DerivedImpactEngineeringControl,
    EngineeringImpactCandidateReceipt,
)


def _patch():
    return CodingPatchCandidate(
        patch_id='patch-impact-control-1',
        producer_agent_id='coding.backend.01',
        task_id='task-impact-control-1',
        work_id='coding-work-impact-1',
        base_plan_version=9,
        base_architecture_version=11,
        touched_files=('src/service.py',),
        touched_symbols=('Service.execute',),
        patch_artifact_id='artifact:impact-patch',
        compile_evidence_refs=('compile:legacy',),
        test_evidence_refs=('test:legacy',),
        static_evidence_refs=('static:legacy',),
        status=CodingPatchStatus.VERIFIED,
    )


def _coding_ready(patch_id):
    verification = PatchVerificationEvidence(
        evidence_id='verify:impact-canonical',
        verifier_agent_id='verification.testing.01',
        passed=True,
    )
    payload = {
        'receipt_id': 'coding-ready-impact-1',
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


def _strict_control(*, complete=True):
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
        source_revision='git:impact-control',
        nodes=(
            'symbol:Service.execute',
            'symbol:Repository.save',
            'symbol:Audit.emit',
        ),
        dependency_edges=(
            ('symbol:Service.execute', 'symbol:Repository.save'),
            ('symbol:Repository.save', 'symbol:Audit.emit'),
        ),
        component_membership={
            'symbol:Service.execute': 'component:service',
            'symbol:Repository.save': 'component:repository',
            'symbol:Audit.emit': 'component:audit',
        },
        provenance_refs=('static-analysis:impact-control',),
    )
    coverages = EngineeringTestCoverageLedger()
    test_to_nodes = {
        'tests/test_service.py::test_execute': ('symbol:Service.execute',),
        'tests/test_repo.py::test_save': ('symbol:Repository.save',),
    }
    if complete:
        test_to_nodes['tests/test_audit.py::test_emit'] = ('symbol:Audit.emit',)
    coverage = coverages.register(
        source_revision='git:impact-control',
        graph_id=graph.graph_id,
        graph_digest=graph.digest,
        test_to_nodes=test_to_nodes,
        provenance_refs=('coverage:impact-control',),
    )
    strict = DerivedImpactEngineeringControl(
        plane=plane,
        dependency_graphs=graphs,
        test_coverage=coverages,
    )
    work = strict.begin_patch(
        patch=patch,
        source_revision='git:impact-control',
        rollback_artifact_ref='artifact:rollback-impact',
        claim_refs=(claim.claim_id,),
        dependency_graph_id=graph.graph_id,
        test_coverage_id=coverage.coverage_id,
    )
    return patch, claims, strict, work, graph, coverage


def _advance_to_postconditions(strict, patch, work):
    attestations = []
    for kind in (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    ):
        attestations.append(strict.record_evidence(
            patch=patch,
            source_revision='git:impact-control',
            environment_digest='env:ubuntu24-py313',
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}:impact',),
            dependencies=(f'artifact:{kind.value}:impact',),
        ))
    strict.verify_preconditions(
        work.transaction_id,
        attestation_ids=(attestations[0].attestation_id,),
    )
    mutation = strict.assess_mutation_authority(work.work_id, patch=patch)
    strict.mark_applied(
        work.transaction_id,
        application_ref='workspace:impact-apply',
        mutation_authority_receipt_id=mutation.receipt_id,
    )
    strict.observe_outcome(work.transaction_id, evidence_refs=('runtime:impact-outcome',))
    strict.verify_postconditions(
        work.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    return tuple(row.attestation_id for row in attestations)


def test_begin_patch_derives_manifest_blast_radius_from_graph():
    patch, _, strict, work, _, _ = _strict_control(complete=True)
    binding = strict.binding_for_work(work.work_id)
    impact = strict.impact(binding.impact_id)
    manifest = strict.plane.manifests.get(work.manifest_id)
    assert impact.patch_ref == patch.patch_id
    assert manifest.impacted_component_refs == (
        'component:audit',
        'component:repository',
        'component:service',
    )
    assert manifest.impacted_component_refs == impact.impacted_component_refs


def test_caller_cannot_underdeclare_derived_blast_radius():
    patch, claims, strict, _, graph, coverage = _strict_control(complete=True)
    second_claim = claims.claim(
        agent_id=patch.producer_agent_id,
        task_id='task-impact-control-2',
        file_paths=patch.touched_files,
        symbol_ids=patch.touched_symbols,
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    second_patch = CodingPatchCandidate(
        patch_id='patch-impact-control-2',
        producer_agent_id=patch.producer_agent_id,
        task_id='task-impact-control-2',
        work_id='coding-work-impact-2',
        base_plan_version=9,
        base_architecture_version=11,
        touched_files=patch.touched_files,
        touched_symbols=patch.touched_symbols,
        patch_artifact_id='artifact:impact-patch-2',
        compile_evidence_refs=('compile:legacy',),
        test_evidence_refs=('test:legacy',),
        static_evidence_refs=('static:legacy',),
        status=CodingPatchStatus.VERIFIED,
    )
    with pytest.raises(ValueError, match='declared impact'):
        strict.begin_patch(
            patch=second_patch,
            source_revision='git:impact-control',
            rollback_artifact_ref='artifact:rollback-impact-2',
            claim_refs=(second_claim.claim_id,),
            dependency_graph_id=graph.graph_id,
            test_coverage_id=coverage.coverage_id,
            claimed_impacted_component_refs=('component:service',),
        )


def test_incomplete_selection_blocks_before_inner_candidate_closure():
    patch, _, strict, work, _, _ = _strict_control(complete=False)
    attestations = _advance_to_postconditions(strict, patch, work)
    receipt = strict.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:impact-control',
        attestation_ids=attestations,
    )
    assert not receipt.ready
    assert receipt.inner_gate_receipt_id is None
    assert 'uncovered_impact_nodes' in receipt.reasons
    assert strict.plane.transactions.get(work.transaction_id).phase is EngineeringPhase.POSTCONDITIONS_VERIFIED


def test_complete_selection_binds_proof_and_allows_candidate_closure():
    patch, _, strict, work, _, _ = _strict_control(complete=True)
    attestations = _advance_to_postconditions(strict, patch, work)
    receipt = strict.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:impact-control',
        attestation_ids=attestations,
    )
    binding = strict.binding_for_work(work.work_id)
    assert receipt.ready
    assert receipt.authority == 'candidate_only'
    assert receipt.impact_binding_id == binding.binding_id
    assert receipt.inner_gate_receipt_id is not None
    assert strict.plane.transactions.get(work.transaction_id).phase is EngineeringPhase.CANDIDATE_READY
    current = strict.revalidate(
        receipt.receipt_id,
        patch=patch,
        current_source_revision='git:impact-control',
    )
    assert current.current


def test_strict_impact_control_snapshot_roundtrip_and_lineage_tamper_rejection():
    patch, claims, strict, work, _, _ = _strict_control(complete=True)
    attestations = _advance_to_postconditions(strict, patch, work)
    receipt = strict.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:impact-control',
        attestation_ids=attestations,
    )
    restored = DerivedImpactEngineeringControl.from_state(
        claims=claims,
        state=strict.to_state(),
    )
    assert restored.digest == strict.digest
    assert restored.get(receipt.receipt_id) == receipt
    assert restored.binding_for_work(work.work_id) == strict.binding_for_work(work.work_id)

    forged = strict.to_state()
    forged['bindings'][0]['selection_digest'] = 'forged-selection-digest'
    binding_payload = {
        key: value
        for key, value in forged['bindings'][0].items()
        if key not in {'binding_id', 'digest'}
    }
    digest = canonical_digest(binding_payload)
    forged['bindings'][0]['digest'] = digest
    forged['bindings'][0]['binding_id'] = f'eng-impact-binding-{digest[:20]}'
    forged['digest'] = canonical_digest({key: value for key, value in forged.items() if key != 'digest'})
    with pytest.raises(ValueError, match='selection'):
        DerivedImpactEngineeringControl.from_state(claims=claims, state=forged)


def test_impact_candidate_receipt_rejects_promotion_authority():
    patch, _, strict, work, _, _ = _strict_control(complete=False)
    attestations = _advance_to_postconditions(strict, patch, work)
    receipt = strict.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:impact-control',
        attestation_ids=attestations,
    )
    state = receipt.to_state()
    state['authority'] = 'release'
    state['digest'] = canonical_digest({key: value for key, value in state.items() if key not in {'receipt_id', 'digest'}})
    state['receipt_id'] = f'eng-impact-gate-{state["digest"][:20]}'
    with pytest.raises(ValueError, match='authority'):
        EngineeringImpactCandidateReceipt.from_state(state)
