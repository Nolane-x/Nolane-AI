from __future__ import annotations

from dataclasses import replace

import nolane.external_core.integration_admission_bundle as admission_bundle


def _frontiers() -> dict[str, dict[str, str]]:
    return {
        "current_source_state_digests": {},
        "current_evidence_digests": {},
        "current_artifact_digests": {},
        "current_freshness_fences": {},
        "known_handoff_digests": {},
        "current_work_trace_digests": {},
    }


def test_well_shaped_but_forged_current_witness_is_never_rebound_into_v4_report() -> None:
    observation = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        **_frontiers(),
    )
    forged = replace(
        observation,
        digest="canonical-observation-v1-" + ("0" * 64),
    )
    assert forged.digest != observation.digest

    report = admission_bundle.run_canonical_admission_audit(
        bundle=admission_bundle.build_canonical_admission_bundle(
            observed_epoch=7,
            **_frontiers(),
        ),
        current_observed_epoch=7,
        current_observation=forged,
        observation_genesis=True,
        **_frontiers(),
    )

    assert "CURRENT_OBSERVATION_WITNESS_INVALID" in {
        row.code for row in report.findings
    }
    assert report.protocol == "external-integration-admission-audit-v4"
    assert report.observation_digest is None
