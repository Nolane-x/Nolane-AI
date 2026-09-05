from __future__ import annotations

from pathlib import Path

import nolane.external_core as external_core
from nolane.external_core import compatibility, evidence, integration
from nolane.metadata.component_versions import component_version


def test_scoped_revalidation_advances_only_its_two_semantic_owner_versions() -> None:
    assert evidence.COMPONENT_ID == "external.evidence"
    assert evidence.COMPONENT_VERSION == "0.0.2"
    assert integration.COMPONENT_ID == "external.integration"
    assert integration.COMPONENT_VERSION == "0.0.3"
    assert compatibility.SEMANTIC_SURFACE_VERSION == "0.0.3"
    assert str(component_version("external.evidence")) == "0.0.2"
    assert str(component_version("external.integration")) == "0.0.3"

    # Sentinel neighbors: this feature must not manufacture dependency bumps.
    assert str(component_version("external.planning")) == "0.0.1"
    assert str(component_version("external.assurance")) == "0.0.1"
    assert str(component_version("external.verification")) == "0.0.1"


def test_package_root_exports_only_safe_scoped_revalidation_surfaces() -> None:
    required = {
        "ScopedEvidenceRecord",
        "RevalidationScope",
        "RevalidationChallenge",
        "ScopedRevalidationEvidenceBinding",
        "ScopedRevalidationAssessment",
        "RevalidationCompletionReceipt",
        "build_revalidation_scope",
        "build_revalidation_challenges",
        "challenge_subject_digest",
        "assess_scoped_revalidation",
    }
    assert required.issubset(set(external_core.__all__))
    for name in required:
        assert getattr(external_core, name) is not None

    forbidden = {
        "authorize",
        "verify",
        "assure",
        "promote",
        "execute",
        "deploy",
        "repair",
        "auto_migrate",
        "register_runtime",
    }
    assert forbidden.isdisjoint(set(external_core.__all__))


def test_legacy_v1_revalidation_public_contract_remains_available() -> None:
    for name in (
        "RevalidationEvidenceBinding",
        "RevalidationAssessment",
        "RevalidationPlan",
        "assess_revalidation",
        "build_revalidation_plan",
    ):
        assert name in external_core.__all__
        assert getattr(external_core, name) is not None


def test_current_external_core_authority_documents_scoped_evidence_without_global_version() -> None:
    text = Path("CURRENT/EXTERNAL_CORE.md").read_text(encoding="utf-8")
    assert "external.evidence" in text and "0.0.2" in text
    assert "external.integration" in text and "0.0.3" in text
    assert "scoped-evidence-v2" in text
    assert "integration-revalidation-scope-v2" in text
    assert "Evidence may prove only the exact subject and context it was produced against" in text
    assert "no global External Core version" in text
    assert "not Verification" in text
    assert "not Assurance" in text
    assert "not authorization" in text
