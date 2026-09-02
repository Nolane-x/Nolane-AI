from __future__ import annotations

import copy

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchLedger


def _register_patch(ledger: CodingPatchLedger, *, suffix: str):
    return ledger.register_patch(
        producer_agent_id="coding.agent",
        task_id=f"task-{suffix}",
        work_id=f"work-{suffix}",
        base_plan_version=1,
        base_architecture_version=1,
        touched_files=(f"nolane/{suffix}.py",),
        patch_artifact_id=f"artifact-{suffix}",
        patch_artifact_digest=f"sha256:{suffix}",
        base_source_revision=f"source-{suffix}",
        operation_ref=f"patch-op-{suffix}",
        compile_evidence_refs=(f"compile-{suffix}",),
        test_evidence_refs=(f"test-{suffix}",),
    )


def _recompute_transition_identity(transition: dict[str, object]) -> None:
    payload = {
        key: value
        for key, value in transition.items()
        if key not in {"receipt_id", "digest"}
    }
    digest = canonical_digest(payload)
    transition["digest"] = digest
    transition["receipt_id"] = "patch-transition-" + digest[:20]


def test_snapshot_rejects_cross_patch_provenance_transition_rebinding() -> None:
    ledger = CodingPatchLedger(CodeClaimLedger())
    first = _register_patch(ledger, suffix="first")
    second = _register_patch(ledger, suffix="second")
    forged = copy.deepcopy(ledger.to_state())

    second_provenance = next(
        row for row in forged["provenance"]
        if row["provenance_id"] == second.provenance_id
    )
    first_transition = next(
        row for row in forged["transitions"]
        if row["patch_id"] == first.patch_id
    )
    first_transition["provenance_id"] = second.provenance_id
    first_transition["provenance_digest"] = second_provenance["digest"]
    _recompute_transition_identity(first_transition)

    with pytest.raises(ValueError, match="transition.*provenance.*binding|provenance.*binding"):
        CodingPatchLedger.from_state(claims=CodeClaimLedger(), state=forged)


def test_snapshot_rejects_orphan_provenance_operation_binding() -> None:
    ledger = CodingPatchLedger(CodeClaimLedger())
    first = _register_patch(ledger, suffix="first")
    _register_patch(ledger, suffix="second")
    forged = copy.deepcopy(ledger.to_state())

    forged["patches"] = [
        row for row in forged["patches"]
        if row["patch_id"] == first.patch_id
    ]
    forged["transitions"] = [
        row for row in forged["transitions"]
        if row["patch_id"] == first.patch_id
    ]
    forged["patch_counter"] = 1

    with pytest.raises(ValueError, match="provenance.*owner|owner.*provenance"):
        CodingPatchLedger.from_state(claims=CodeClaimLedger(), state=forged)
