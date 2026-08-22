from cogcoder.organization.code_claims import ClaimMode, CodeClaimLedger
from cogcoder.organization.coding_patches import CodingPatchLedger, CodingPatchStatus


def test_patch_records_base_versions_scope_artifact_and_claim_coverage():
    claims = CodeClaimLedger()
    claims.claim(
        agent_id='coding.backend.01', task_id='T-1',
        file_paths=('src/api/auth.py',), symbol_ids=('AuthService.refresh',),
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    patches = CodingPatchLedger(claims)
    patch = patches.register_patch(
        producer_agent_id='coding.backend.01',
        task_id='T-1', work_id='W-1',
        base_plan_version=4, base_architecture_version=2,
        touched_files=('src/api/auth.py',),
        touched_symbols=('AuthService.refresh',),
        patch_artifact_id='artifact-patch-1',
        compile_evidence_refs=('EV-COMPILE-1',),
        test_evidence_refs=('EV-TEST-1',),
        static_evidence_refs=('EV-TYPE-1',),
        known_risks=('token refresh compatibility',),
    )

    assert patch.status is CodingPatchStatus.EVIDENCE_READY
    assert patch.patch_artifact_id == 'artifact-patch-1'
    assert patches.claim_coverage(patch.patch_id) is True


def test_unclaimed_touched_scope_is_recorded_but_not_coverage_ready():
    claims = CodeClaimLedger()
    claims.claim(
        agent_id='coding.backend.01', task_id='T-1',
        file_paths=('src/api/auth.py',), mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    patches = CodingPatchLedger(claims)
    patch = patches.register_patch(
        producer_agent_id='coding.backend.01',
        task_id='T-1', work_id='W-1',
        base_plan_version=1, base_architecture_version=1,
        touched_files=('src/api/auth.py', 'src/api/session.py'),
        touched_symbols=(), patch_artifact_id='artifact-patch-2',
        compile_evidence_refs=('EV-COMPILE-2',),
        test_evidence_refs=('EV-TEST-2',),
    )
    assert patches.claim_coverage(patch.patch_id) is False


def test_tool_receipt_is_content_addressed_and_round_trips():
    claims = CodeClaimLedger()
    patches = CodingPatchLedger(claims)
    receipt = patches.record_tool_invocation(
        agent_id='coding.systems.01', task_id='T-SYS',
        tool_id='compiler',
        input_artifact_refs=('artifact-source-1',),
        output_artifact_refs=('artifact-build-1',),
        success=True,
        evidence_refs=('EV-TOOL-1',),
    )
    replay = CodingPatchLedger.from_state(claims=claims, state=patches.to_state())
    restored = replay.get_tool_receipt(receipt.receipt_id)
    assert restored == receipt
    assert restored.digest == receipt.digest
