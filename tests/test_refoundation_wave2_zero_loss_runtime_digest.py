from __future__ import annotations

from cogcoder.organization.types import canonical_digest
from cogcoder.refoundation.canonical_runtime import CanonicalOrganization


# Hosted-green Wave-1 evidence artifact from run 32633035442, Python 3.11 and
# Python 3.13, exact head 008da21c85b775f39da0b58177330a1317237af5.
WAVE1_ACCEPTED_RUNTIME_STATE_DIGEST = (
    "627f8483e1af908c48d6246006c9692cc4c291cac92b0953c13154b7bf137380"
)

# Wave 5N intentionally advances the persisted TaskGraph authority schema:
# plan_version becomes the read-only Planning projection, fresh state starts at
# zero, and plan_revision_authority is explicit. The historical Wave-1 digest
# remains preserved above as provenance rather than being silently rewritten.
WAVE5N_RUNTIME_STATE_DIGEST = (
    "5af45189c960dc0dca4ebe7e00859708e162a6a06aa3d063910156d9e86076ae"
)

# E. Acting advances canonical persistence again by making the transactional
# executor ledger part of Execution Control state. Wave-1 and Wave-5N remain
# immutable provenance anchors; this is an append-only cutover authority.
E_ACTING_RUNTIME_STATE_DIGEST = (
    "eda96a54b833dee2a3eb2a3e697fb658f4ff73729fff76fa6746ba554a6d602e"
)


def test_runtime_state_fingerprint_tracks_the_explicit_e_acting_persistence_cutover() -> None:
    first = CanonicalOrganization.first_generation()
    second = CanonicalOrganization.first_generation()
    first_state = first.to_state()
    second_state = second.to_state()

    assert canonical_digest(first_state) == E_ACTING_RUNTIME_STATE_DIGEST
    assert first.state_digest == E_ACTING_RUNTIME_STATE_DIGEST
    assert canonical_digest(second_state) == E_ACTING_RUNTIME_STATE_DIGEST
    assert second.state_digest == E_ACTING_RUNTIME_STATE_DIGEST
    assert first_state == second_state
    assert E_ACTING_RUNTIME_STATE_DIGEST != WAVE5N_RUNTIME_STATE_DIGEST
    assert WAVE5N_RUNTIME_STATE_DIGEST != WAVE1_ACCEPTED_RUNTIME_STATE_DIGEST
