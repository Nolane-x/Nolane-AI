from __future__ import annotations

from cogcoder.organization.types import canonical_digest
from cogcoder.refoundation.canonical_runtime import CanonicalOrganization


# Hosted-green Wave-1 evidence artifact from run 32633035442, Python 3.11 and
# Python 3.13, exact head 008da21c85b775f39da0b58177330a1317237af5.
WAVE1_ACCEPTED_RUNTIME_STATE_DIGEST = (
    "627f8483e1af908c48d6246006c9692cc4c291cac92b0953c13154b7bf137380"
)


def test_wave2_native_extraction_preserves_exact_wave1_runtime_state_fingerprint() -> None:
    runtime = CanonicalOrganization.first_generation()
    state = runtime.to_state()

    assert canonical_digest(state) == WAVE1_ACCEPTED_RUNTIME_STATE_DIGEST
    assert runtime.state_digest == WAVE1_ACCEPTED_RUNTIME_STATE_DIGEST
