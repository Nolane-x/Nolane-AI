from __future__ import annotations

from pathlib import Path

import nolane.external_core.integration_admission_bundle as admission_bundle
import nolane.external_core.observation_integration as observation_integration


ROOT = Path(__file__).resolve().parents[1]


def test_current_external_core_a8_a10_seal_matches_runtime_literals() -> None:
    text = (ROOT / "CURRENT" / "EXTERNAL_CORE.md").read_text(encoding="utf-8")

    required_sentences = (
        "an expected contract may never manufacture missing observed state",
        "The observation protocol is `external-canonical-observation-v1`",
        "Canonical registry evidence must come from provider `external-core:canonical-registry`, provider version `1`, source locator `nolane.external_core.audit:build_canonical_registry`",
        "canonical authority-graph evidence must come from `external-core:canonical-authority-graph`, provider version `1`, source locator `nolane.external_core.audit:build_canonical_fabric_profile`",
        "External Core owns no mutable chain head",
        "The current admission audit is `external-integration-admission-audit-v4`",
        "Historical call shapes remain historical v3 evidence",
        "The current `external.integration` owner, compatibility semantic surface and admission-audit owner projection are `0.0.7`; metadata revision is `7`",
        "The A10 architecture production freeze was verified on `main@99de2ff334d5a0cafa25e4f76f02e974fa391f0f`",
    )
    for sentence in required_sentences:
        assert sentence in text

    assert "production freeze declaration is withheld until Task 10 verifies" not in text

    expectations = observation_integration.canonical_observation_provider_expectations()
    assert expectations["registry"].provider_id == "external-core:canonical-registry"
    assert expectations["registry"].source_locator == "nolane.external_core.audit:build_canonical_registry"
    assert expectations["authority-graph"].provider_id == "external-core:canonical-authority-graph"
    assert expectations["authority-graph"].source_locator == "nolane.external_core.audit:build_canonical_fabric_profile"

    assert admission_bundle.COMPONENT_VERSION == "0.0.7"
    assert admission_bundle.ADMISSION_AUDIT_PROTOCOL == "external-integration-admission-audit-v4"
    assert admission_bundle.HISTORICAL_ADMISSION_AUDIT_PROTOCOL == "external-integration-admission-audit-v3"
