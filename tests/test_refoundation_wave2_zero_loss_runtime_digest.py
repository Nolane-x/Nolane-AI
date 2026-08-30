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

# Memory/Learning v0.0.5 intentionally advances persisted runtime authority:
# self-model revisions and individual-evolution lineage are now restored with
# fail-closed integrity semantics. Keep the Wave-5N digest above as historical
# provenance and name the new accepted fingerprint instead of rewriting it.
MEMORY_LEARNING_V005_RUNTIME_STATE_DIGEST = (
    "fba03e77c6513e7361382813b691ce468ac6006f5822b5096c3d334efe040d01"
)

# Governed persistent skill promotion adds only the validation ledger needed to
# re-authorize promotion after restart. The previous v0.0.5 fingerprint remains
# historical provenance; this cutover records the authority-bearing runtime
# state after LearningSubstrate is wired to the canonical Memory/Skills objects.
MEMORY_LEARNING_V005_GOVERNED_PROMOTION_RUNTIME_STATE_DIGEST = (
    "76ff067244a54029961d4096a2af23bf37f4194b255c663cb15554970c745749"
)


def test_runtime_state_fingerprint_tracks_the_memory_learning_v005_persistence_cutover() -> None:
    first = CanonicalOrganization.first_generation()
    second = CanonicalOrganization.first_generation()
    first_state = first.to_state()
    second_state = second.to_state()

    assert canonical_digest(first_state) == MEMORY_LEARNING_V005_GOVERNED_PROMOTION_RUNTIME_STATE_DIGEST
    assert first.state_digest == MEMORY_LEARNING_V005_GOVERNED_PROMOTION_RUNTIME_STATE_DIGEST
    assert canonical_digest(second_state) == MEMORY_LEARNING_V005_GOVERNED_PROMOTION_RUNTIME_STATE_DIGEST
    assert second.state_digest == MEMORY_LEARNING_V005_GOVERNED_PROMOTION_RUNTIME_STATE_DIGEST
    assert first_state == second_state
    assert MEMORY_LEARNING_V005_GOVERNED_PROMOTION_RUNTIME_STATE_DIGEST != MEMORY_LEARNING_V005_RUNTIME_STATE_DIGEST
    assert MEMORY_LEARNING_V005_RUNTIME_STATE_DIGEST != WAVE5N_RUNTIME_STATE_DIGEST
    assert WAVE5N_RUNTIME_STATE_DIGEST != WAVE1_ACCEPTED_RUNTIME_STATE_DIGEST