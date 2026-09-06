from __future__ import annotations

import pytest

from nolane.external_core.integration_admission_bundle import build_canonical_observation
from nolane.external_core.observation import validate_observation_transition


def _observation():
    return build_canonical_observation(
        observed_epoch=7,
        current_source_state_digests={},
        current_evidence_digests={},
        current_artifact_digests={},
        current_freshness_fences={},
        known_handoff_digests={},
        current_work_trace_digests={},
    )


@pytest.mark.parametrize("genesis", [1, 0, "true", [], object()])
def test_public_transition_validator_requires_exact_boolean_genesis(genesis: object) -> None:
    with pytest.raises(ValueError, match="genesis must be an exact boolean"):
        validate_observation_transition(
            None,
            _observation(),
            genesis=genesis,  # type: ignore[arg-type]
        )
