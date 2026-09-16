from __future__ import annotations

import pytest

from nolane.external_core.evidence import EvidenceRecord


@pytest.mark.parametrize("alias", ["false", 1])
def test_legacy_evidence_restore_requires_exact_boolean_passed(alias: object) -> None:
    state = EvidenceRecord(
        evidence_id="evidence-r237-negative",
        verifier_agent_id="verification.r237",
        passed=False,
    ).to_state()
    state["passed"] = alias

    with pytest.raises(ValueError, match="evidence passed must be an exact boolean"):
        EvidenceRecord.from_state(state)
