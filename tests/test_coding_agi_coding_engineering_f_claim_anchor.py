from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def _plane_with_bound_claim():
    patch = CodingPatchCandidate(
        patch_id='patch-anchor-1',
        producer_agent_id='coding.backend.01',
        task_id='task-anchor-1',
        work_id='work-anchor-1',
        base_plan_version=1,
        base_architecture_version=1,
        touched_files=('src/anchor.py',),
        touched_symbols=('Anchor.apply',),
        patch_artifact_id='artifact:anchor',
        compile_evidence_refs=('compile',),
        test_evidence_refs=('test',),
        static_evidence_refs=('static',),
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
    plane.begin_patch(
        patch=patch,
        source_revision='git:anchor',
        rollback_artifact_ref='artifact:rollback-anchor',
        claim_refs=(claim.claim_id,),
    )
    return claims, plane


def test_control_restore_rejects_fabricated_claim_identity_even_if_all_local_digests_are_recomputed():
    claims, plane = _plane_with_bound_claim()
    state = plane.to_state()
    fake_claim_id = 'claim-99999999'

    tx = state['transactions']['transactions'][0]
    tx['claim_refs'] = [fake_claim_id]

    binding = state['claim_bindings']['bindings'][0]
    claim_snapshot = binding['claims'][0]
    claim_snapshot['claim_id'] = fake_claim_id
    claim_payload = {key: value for key, value in claim_snapshot.items() if key != 'digest'}
    claim_snapshot['digest'] = canonical_digest(claim_payload)
    binding_payload = {
        'transaction_id': binding['transaction_id'],
        'claims': binding['claims'],
        'authority': binding['authority'],
    }
    binding_digest = canonical_digest(binding_payload)
    binding['digest'] = binding_digest
    binding['binding_id'] = f'eng-claim-binding-{binding_digest[:20]}'

    work = state['works'][0]
    work['claim_binding_id'] = binding['binding_id']
    work['claim_binding_digest'] = binding['digest']
    work_payload = {key: value for key, value in work.items() if key not in {'work_id', 'digest'}}
    work_digest = canonical_digest(work_payload)
    work['digest'] = work_digest
    work['work_id'] = f'eng-work-{work_digest[:20]}'

    state['digest'] = canonical_digest({key: value for key, value in state.items() if key != 'digest'})

    try:
        SoftwareEngineeringControlPlane.from_state(claims=claims, state=state)
    except KeyError as exc:
        assert fake_claim_id in str(exc)
    else:
        raise AssertionError('F snapshot fabricated a claim identity outside canonical CodeClaimLedger')
