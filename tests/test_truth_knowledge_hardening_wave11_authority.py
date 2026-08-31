from __future__ import annotations

import importlib


def test_a11_provenance_v5_sidecars_cannot_mint_canonical_family_a_authority():
    expected = {
        "nolane.external_core.evidence_provenance_truth": (
            "external.evidence",
            "truth-source-provenance-v5",
        ),
        "nolane.external_core.epistemic_provenance_truth": (
            "external.epistemic",
            "truth-provenance-lineage-temporal-scope-v5",
        ),
        "nolane.external_core.verification_provenance_truth": (
            "external.verification",
            "truth-verification-provenance-lineage-temporal-v5",
        ),
        "nolane.external_core.assurance_provenance_truth": (
            "external.assurance",
            "truth-assurance-provenance-lineage-temporal-v5",
        ),
    }

    for module_name, (parent_component_id, protocol_id) in expected.items():
        module = importlib.import_module(module_name)
        assert module.PARENT_COMPONENT_ID == parent_component_id
        assert module.TRUTH_PROTOCOL == protocol_id
        assert not hasattr(module, "COMPONENT_ID")


def test_a11_v5_binding_mode_is_one_exact_protocol_generation():
    epistemic = importlib.import_module("nolane.external_core.epistemic_provenance_truth")
    verification = importlib.import_module("nolane.external_core.verification_provenance_truth")

    assert epistemic.PROVENANCE_BINDING_MODE == "provenance-lineage-temporal-v5"
    assert verification.PROVENANCE_BINDING_MODE == epistemic.PROVENANCE_BINDING_MODE
