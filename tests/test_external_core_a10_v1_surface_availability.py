from __future__ import annotations

import pytest

from nolane.external_core.integration_admission_bundle import build_canonical_observation


FRONTIER_ARGUMENTS = (
    "current_source_state_digests",
    "current_evidence_digests",
    "current_artifact_digests",
    "current_freshness_fences",
    "known_handoff_digests",
    "current_work_trace_digests",
)


def _explicit_empty_frontiers() -> dict[str, dict[str, str] | None]:
    return {name: {} for name in FRONTIER_ARGUMENTS}


@pytest.mark.parametrize("missing_argument", FRONTIER_ARGUMENTS)
def test_current_observation_builder_rejects_each_unavailable_frontier(
    missing_argument: str,
) -> None:
    frontiers = _explicit_empty_frontiers()
    frontiers[missing_argument] = None

    with pytest.raises(ValueError, match="current observation.*unavailable"):
        build_canonical_observation(
            observed_epoch=7,
            **frontiers,
        )


def test_current_observation_builder_rejects_all_implicit_none_defaults() -> None:
    with pytest.raises(ValueError, match="current observation.*unavailable"):
        build_canonical_observation(observed_epoch=7)


def test_current_observation_builder_preserves_explicit_empty_as_observed_empty() -> None:
    envelope = build_canonical_observation(
        observed_epoch=7,
        **_explicit_empty_frontiers(),
    )
    assert envelope.surface_receipts
    assert all(row.enumeration_complete is True for row in envelope.surface_receipts)
