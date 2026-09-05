from __future__ import annotations

from pathlib import Path

import nolane.external_core as external_core
from nolane.external_core import compatibility, integration


SAFE_EVOLUTION_EXPORTS = {
    "ComponentEvolutionDelta",
    "EvolutionCompatibilityDisposition",
    "EvolutionCompatibilityQualification",
    "IntegrationImpactClosure",
    "IntegrationImpactReason",
    "build_integration_impact_closure",
    "qualify_component_evolution",
    "ComponentRevalidationRequirement",
    "RevalidationAssessment",
    "RevalidationDisposition",
    "RevalidationEvidenceBinding",
    "RevalidationPlan",
    "assess_revalidation",
    "build_revalidation_plan",
}

FORBIDDEN_CONTROL_EXPORT_FRAGMENTS = (
    "authorize",
    "promote",
    "assure",
    "execute",
    "invoke",
    "repair",
    "deploy",
    "auto_migrate",
    "register_runtime",
)


def test_integration_and_compatibility_semantic_surfaces_advance_together() -> None:
    assert integration.COMPONENT_ID == "external.integration"
    assert integration.COMPONENT_VERSION == "0.0.3"
    assert compatibility.SEMANTIC_SURFACE_ID == "external.integration.compatibility"
    assert compatibility.SEMANTIC_SURFACE_VERSION == "0.0.3"


def test_package_root_exports_only_read_only_integration_evolution_surfaces() -> None:
    exported = set(external_core.__all__)
    assert SAFE_EVOLUTION_EXPORTS <= exported
    for name in SAFE_EVOLUTION_EXPORTS:
        assert getattr(external_core, name) is not None
    lowered = {name.lower() for name in exported}
    assert not {
        name
        for name in lowered
        if any(fragment in name for fragment in FORBIDDEN_CONTROL_EXPORT_FRAGMENTS)
    }


def test_current_external_core_documents_component_local_version_law_without_global_version() -> None:
    text = Path("CURRENT/EXTERNAL_CORE.md").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "component-local version" in lowered
    assert "external.integration" in text
    assert "0.0.3" in text
    assert "no global external core version" in lowered
    assert "external core v0.0.3" not in lowered
    assert "post-epoch-0 a4" not in lowered
