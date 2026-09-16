from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence


def test_r234_patch_verification_rejects_truthy_string_for_passed() -> None:
    state = PatchVerificationEvidence(
        evidence_id="evidence-r234",
        verifier_agent_id="verification.testing.01",
        passed=True,
    ).to_state()
    state["passed"] = "false"

    with pytest.raises(ValueError, match="patch verification passed must be an exact boolean"):
        PatchVerificationEvidence.from_state(state)


def test_r234_coding_readiness_rejects_digest_preserving_truthy_string_for_ready() -> None:
    verification = PatchVerificationEvidence(
        evidence_id="evidence-r234-ready",
        verifier_agent_id="verification.testing.01",
        passed=True,
    )
    payload = {
        "receipt_id": "coding-ready-r234-00000001",
        "patch_id": "patch-r234",
        "ready": True,
        "reasons": [],
        "verification": verification.to_state(),
    }
    state = {**payload, "digest": canonical_digest(payload)}
    state["ready"] = "false"

    with pytest.raises(ValueError, match="coding readiness ready must be an exact boolean"):
        CodingReadinessReceipt.from_state(state)
