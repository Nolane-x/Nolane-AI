from __future__ import annotations

from nolane.external_core import verification_context_truth as context_verification
from nolane.external_core import verification_dependence_truth as dependence_verification


def test_a15_context_verification_is_a_verification_sidecar_with_distinct_protocol():
    assert context_verification.PARENT_COMPONENT_ID == "external.verification"
    assert not hasattr(context_verification, "COMPONENT_ID")
    assert context_verification.TRUTH_PROTOCOL != dependence_verification.TRUTH_PROTOCOL
