from __future__ import annotations

from nolane.external_core import assurance_dependence_truth
from nolane.external_core import epistemic_dependence_truth
from nolane.external_core import evidence_dependence_truth
from nolane.external_core import verification_dependence_truth
from nolane.external_core.epistemic_defeasible_truth import DEFEASIBLE_BINDING_MODE
from nolane.external_core.epistemic_dependence_truth import DEPENDENCE_BINDING_MODE


def test_a14_sidecars_do_not_mint_a_sixth_family_a_authority():
    expected = {
        evidence_dependence_truth: "external.evidence",
        epistemic_dependence_truth: "external.epistemic",
        verification_dependence_truth: "external.verification",
        assurance_dependence_truth: "external.assurance",
    }
    for module, parent in expected.items():
        assert module.PARENT_COMPONENT_ID == parent
        assert not hasattr(module, "COMPONENT_ID")


def test_a14_v8_binding_and_protocols_are_domain_separated_from_v7():
    assert DEPENDENCE_BINDING_MODE == (
        "dependence-defeasible-justification-provenance-lineage-temporal-v8"
    )
    assert DEPENDENCE_BINDING_MODE != DEFEASIBLE_BINDING_MODE

    protocols = {
        evidence_dependence_truth.TRUTH_PROTOCOL,
        epistemic_dependence_truth.TRUTH_PROTOCOL,
        verification_dependence_truth.TRUTH_PROTOCOL,
        assurance_dependence_truth.TRUTH_PROTOCOL,
    }
    assert len(protocols) == 4
    assert all("v8" in protocol for protocol in protocols)


def test_a14_projection_protocols_are_not_truth_protocol_aliases():
    assert evidence_dependence_truth.PROJECTION_PROTOCOL != evidence_dependence_truth.TRUTH_PROTOCOL
    assert verification_dependence_truth.PROJECTION_PROTOCOL != verification_dependence_truth.TRUTH_PROTOCOL
