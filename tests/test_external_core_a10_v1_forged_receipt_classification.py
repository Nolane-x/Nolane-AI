from __future__ import annotations

from dataclasses import replace

import nolane.external_core.integration_admission_bundle as admission_bundle
from nolane.external_core.observation import validate_observation_provenance
from nolane.external_core.observation_integration import (
    canonical_observation_provider_expectations,
    canonical_observation_scope_digests,
)


def _frontiers() -> dict[str, dict[str, str]]:
    return {
        "current_source_state_digests": {},
        "current_evidence_digests": {},
        "current_artifact_digests": {},
        "current_freshness_fences": {},
        "known_handoff_digests": {},
        "current_work_trace_digests": {},
    }


def test_forged_receipt_is_classified_instead_of_escaping_as_value_error() -> None:
    envelope = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        chain_id="external-core:test",
        previous_observation_digest=None,
        **_frontiers(),
    )
    target = envelope.surface_receipt("registry")
    forged_receipt = replace(
        target,
        digest="surface-observation-receipt-v1-forged",
    )
    forged_envelope = replace(
        envelope,
        surface_receipts=tuple(
            forged_receipt if row.surface_kind == "registry" else row
            for row in envelope.surface_receipts
        ),
    )

    findings = validate_observation_provenance(
        forged_envelope,
        provider_expectations=canonical_observation_provider_expectations(),
        expected_scope_digests=canonical_observation_scope_digests(
            envelope.surface_contract.required_component_ids
        ),
    )

    assert any(
        row.code == "OBSERVATION_RECEIPT_FORGED" and row.subject_id == "registry"
        for row in findings
    )
