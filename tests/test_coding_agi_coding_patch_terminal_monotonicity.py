from __future__ import annotations

import pytest

from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchLedger, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringEvidenceLedger


@pytest.mark.parametrize("terminal_status", [CodingPatchStatus.REJECTED, CodingPatchStatus.SUPERSEDED])
def test_terminal_patch_cannot_be_resurrected_as_verified(terminal_status: CodingPatchStatus) -> None:
    evidence = EngineeringEvidenceLedger()
    ledger = CodingPatchLedger(CodeClaimLedger(), engineering_evidence=evidence)
    patch = ledger.register_patch(
        producer_agent_id="coding.agent",
        task_id="task-terminal-monotonicity",
        work_id="work-terminal-monotonicity",
        base_plan_version=1,
        base_architecture_version=1,
        touched_files=("nolane/example.py",),
        patch_artifact_id="artifact-terminal-001",
        patch_artifact_digest="sha256:terminal-001",
        base_source_revision="source-terminal-001",
        operation_ref=f"patch-terminal-{terminal_status.value}",
        compile_evidence_refs=("compile-green",),
        test_evidence_refs=("test-green",),
    )
    ledger.set_status(patch.patch_id, terminal_status)

    compile_attestation = evidence.record(
        subject_ref="artifact-terminal-001",
        subject_digest="sha256:terminal-001",
        producer_agent_id="coding.agent",
        verifier_agent_id="verifier.compile",
        verifier_region="verification-testing",
        kind=EngineeringEvidenceKind.COMPILE,
        passed=True,
        evidence_refs=("observed:compile",),
        source_revision="source-terminal-001",
        environment_digest="env:hosted-ci",
    )
    test_attestation = evidence.record(
        subject_ref="artifact-terminal-001",
        subject_digest="sha256:terminal-001",
        producer_agent_id="coding.agent",
        verifier_agent_id="verifier.test",
        verifier_region="verification-testing",
        kind=EngineeringEvidenceKind.TEST,
        passed=True,
        evidence_refs=("observed:test",),
        source_revision="source-terminal-001",
        environment_digest="env:hosted-ci",
    )

    with pytest.raises(PermissionError, match="terminal"):
        ledger.verify_patch(
            patch.patch_id,
            evidence_attestation_ids=(compile_attestation.attestation_id, test_attestation.attestation_id),
        )

    assert ledger.get_patch(patch.patch_id).status is terminal_status
    assert ledger.latest_transition(patch.patch_id).to_status is terminal_status
