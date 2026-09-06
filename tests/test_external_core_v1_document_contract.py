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
        "registry provider `external-core:canonical-registry`",
        "source locator `nolane.external_core.audit:build_canonical_registry`",
        "canonical authority-graph evidence must come from `external-core:canonical-authority-graph`",
        "source locator `nolane.external_core.audit:build_canonical_fabric_profile`",
        "External Core owns no mutable chain head",
        "`external.integration` current component version is `0.0.7`",
        "current audit protocol is `external-integration-admission-audit-v4`",
        "historical audit-v3 evidence remains historical",
    )
    for sentence in required_sentences:
        assert sentence in text

    expectations = observation_integration.canonical_observation_provider_expectations()
    assert expectations["registry"].provider_id == "external-core:canonical-registry"
    assert expectations["registry"].source_locator == "nolane.external_core.audit:build_canonical_registry"
    assert expectations["authority-graph"].provider_id == "external-core:canonical-authority-graph"
    assert expectations["authority-graph"].source_locator == "nolane.external_core.audit:build_canonical_fabric_profile"

    assert admission_bundle.COMPONENT_VERSION == "0.0.7"
    assert admission_bundle.ADMISSION_AUDIT_PROTOCOL == "external-integration-admission-audit-v4"
    assert admission_bundle.HISTORICAL_ADMISSION_AUDIT_PROTOCOL == "external-integration-admission-audit-v3"
