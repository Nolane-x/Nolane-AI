from __future__ import annotations

from pathlib import Path

import nolane.external_core as external_core
from nolane.external_core import integration
from nolane.external_core.integration_admission import (
    CanonicalAdmissionContext as AdmissionContextImplementation,
    ProtocolAdmissionReceipt as AdmissionReceiptImplementation,
)
from nolane.external_core.integration_admission_bundle import (
    CanonicalAdmissionBundle as AdmissionBundleImplementation,
    run_canonical_admission_audit as audit_implementation,
)
from nolane.metadata.component_versions import component_revision_map


A5_GOVERNING_LAW = (
    "Historical compatibility may preserve prior serialization semantics; current admission "
    "must never silently coerce type or identity before canonical integrity is proved."
)


def test_current_integration_owner_contract_preserves_v008_surface_at_revision_twelve() -> None:
    assert integration.COMPONENT_ID == "external.integration"
    assert integration.COMPONENT_VERSION == "0.0.8"
    assert component_revision_map()["external.integration"] == 12


def test_a5_canonical_root_reexports_exact_current_admission_surfaces() -> None:
    assert integration.CanonicalAdmissionContext is AdmissionContextImplementation
    assert integration.ProtocolAdmissionReceipt is AdmissionReceiptImplementation
    assert integration.CanonicalAdmissionBundle is AdmissionBundleImplementation
    assert integration.run_canonical_admission_audit is audit_implementation


def test_a5_package_contract_exposes_structural_and_read_only_admission_surfaces() -> None:
    assert external_core.CanonicalAdmissionContext is AdmissionContextImplementation
    assert external_core.ProtocolAdmissionReceipt is AdmissionReceiptImplementation
    assert external_core.CanonicalAdmissionBundle is AdmissionBundleImplementation
    assert external_core.run_canonical_admission_audit is audit_implementation
    assert callable(external_core.build_canonical_admission_context)
    assert callable(external_core.build_canonical_admission_bundle)
    assert callable(external_core.admit_manifest_state)
    assert callable(external_core.admit_authority_graph_state)
    assert callable(external_core.admit_handoff_state)
    assert callable(external_core.admit_work_trace_state)


def test_current_external_core_records_a5_law_version_and_non_authority_boundary() -> None:
    text = Path("CURRENT/EXTERNAL_CORE.md").read_text(encoding="utf-8")
    assert "A5" in text
    assert A5_GOVERNING_LAW in text
    assert "external.integration" in text
    assert "0.0.3" in text and "0.0.4" in text
    assert "ADMITTED" in text
    for forbidden_authority in (
        "Verification",
        "Assurance",
        "authorization",
        "promotion",
        "execution",
        "learning",
        "release",
        "deployment",
        "repair",
        "migration",
    ):
        assert forbidden_authority in text
