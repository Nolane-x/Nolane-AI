from __future__ import annotations

from cogcoder.organization.types import canonical_digest
from cogcoder.refoundation.canonical_runtime import CanonicalOrganization


# Hosted-green Wave-1 evidence artifact from run 32633035442, Python 3.11 and
# Python 3.13, exact head 008da21c85b775f39da0b58177330a1317237af5.
WAVE1_ACCEPTED_RUNTIME_STATE_DIGEST = (
    "627f8483e1af908c48d6246006c9692cc4c291cac92b0953c13154b7bf137380"
)

# Wave 5N intentionally advances the persisted TaskGraph authority schema.
WAVE5N_RUNTIME_STATE_DIGEST = (
    "5af45189c960dc0dca4ebe7e00859708e162a6a06aa3d063910156d9e86076ae"
)

# Memory/Learning v0.0.5 persistence cutover.
MEMORY_LEARNING_V005_RUNTIME_STATE_DIGEST = (
    "fba03e77c6513e7361382813b691ce468ac6006f5822b5096c3d334efe040d01"
)

# Governed persistent skill promotion cutover.
MEMORY_LEARNING_V005_GOVERNED_PROMOTION_RUNTIME_STATE_DIGEST = (
    "76ff067244a54029961d4096a2af23bf37f4194b255c663cb15554970c745749"
)

# Final B runtime unification before E Acting is integrated.
MEMORY_LEARNING_V005_UNIFIED_B_RUNTIME_STATE_DIGEST = (
    "d64f2009f928ba4c7dd759ffed604e3e3a9418b7918953b7dca093990c2211fd"
)

# Historical E Acting cutover measured before the later Memory/Learning and B
# persistence changes landed on main. It remains provenance, not current state.
E_ACTING_PRE_B_RUNTIME_STATE_DIGEST = (
    "eda96a54b833dee2a3eb2a3e697fb658f4ff73729fff76fa6746ba554a6d602e"
)

# E Acting integrated on top of the accepted unified-B runtime. This exact
# fingerprint was independently observed on CPython 3.11.16 and 3.13.15 by the
# intentional RED integration run before this authority literal was accepted.
E_ACTING_UNIFIED_B_RUNTIME_STATE_DIGEST = (
    "530054ed6d094c5ea000e38002346746ca63ddfb4d1c58b1d9f772263218415d"
)

# Memory/Learning v0.0.7 adds content-addressed historical retrieval replay
# snapshots to the canonical Memory Retrieval owner section.  The empty
# snapshot registry is intentionally part of the deterministic runtime schema.
MEMORY_LEARNING_V007_REPLAY_RUNTIME_STATE_DIGEST = (
    "e94dad6dcfc2c4c6d4f51b85c95a344e5fb95174cc47d575735e1974d31ba0b0"
)


def test_runtime_state_fingerprint_tracks_e_acting_on_unified_b_cutover() -> None:
    first = CanonicalOrganization.first_generation()
    second = CanonicalOrganization.first_generation()
    first_state = first.to_state()
    second_state = second.to_state()

    assert canonical_digest(first_state) == MEMORY_LEARNING_V007_REPLAY_RUNTIME_STATE_DIGEST
    assert first.state_digest == MEMORY_LEARNING_V007_REPLAY_RUNTIME_STATE_DIGEST
    assert canonical_digest(second_state) == MEMORY_LEARNING_V007_REPLAY_RUNTIME_STATE_DIGEST
    assert second.state_digest == MEMORY_LEARNING_V007_REPLAY_RUNTIME_STATE_DIGEST
    assert first_state == second_state
    assert MEMORY_LEARNING_V007_REPLAY_RUNTIME_STATE_DIGEST != E_ACTING_UNIFIED_B_RUNTIME_STATE_DIGEST
    assert E_ACTING_UNIFIED_B_RUNTIME_STATE_DIGEST != MEMORY_LEARNING_V005_UNIFIED_B_RUNTIME_STATE_DIGEST
    assert MEMORY_LEARNING_V005_UNIFIED_B_RUNTIME_STATE_DIGEST != MEMORY_LEARNING_V005_GOVERNED_PROMOTION_RUNTIME_STATE_DIGEST
    assert MEMORY_LEARNING_V005_GOVERNED_PROMOTION_RUNTIME_STATE_DIGEST != MEMORY_LEARNING_V005_RUNTIME_STATE_DIGEST
    assert MEMORY_LEARNING_V005_RUNTIME_STATE_DIGEST != WAVE5N_RUNTIME_STATE_DIGEST
    assert E_ACTING_PRE_B_RUNTIME_STATE_DIGEST != WAVE5N_RUNTIME_STATE_DIGEST
    assert WAVE5N_RUNTIME_STATE_DIGEST != WAVE1_ACCEPTED_RUNTIME_STATE_DIGEST
