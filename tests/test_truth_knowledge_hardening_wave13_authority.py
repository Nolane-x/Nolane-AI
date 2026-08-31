from __future__ import annotations

from nolane.external_core import assurance_defeasible_truth
from nolane.external_core import epistemic_defeasible_truth
from nolane.external_core import knowledge_undercutter_truth
from nolane.external_core import verification_defeasible_truth
from nolane.external_core.epistemic_defeasible_truth import DEFEASIBLE_BINDING_MODE
from nolane.external_core.epistemic_justification_truth import JUSTIFICATION_BINDING_MODE


def test_a13_sidecars_do_not_mint_a_sixth_family_a_authority():
    expected = {
        knowledge_undercutter_truth: "external.knowledge",
        epistemic_defeasible_truth: "external.epistemic",
        verification_defeasible_truth: "external.verification",
        assurance_defeasible_truth: "external.assurance",
    }
    for module, parent in expected.items():
        assert module.PARENT_COMPONENT_ID == parent
        assert not hasattr(module, "COMPONENT_ID")


def test_a13_v7_binding_and_protocols_are_domain_separated_from_v6():
    assert DEFEASIBLE_BINDING_MODE == "defeasible-justification-provenance-lineage-temporal-v7"
    assert DEFEASIBLE_BINDING_MODE != JUSTIFICATION_BINDING_MODE

    protocols = {
        knowledge_undercutter_truth.TRUTH_PROTOCOL,
        epistemic_defeasible_truth.TRUTH_PROTOCOL,
        verification_defeasible_truth.TRUTH_PROTOCOL,
        assurance_defeasible_truth.TRUTH_PROTOCOL,
    }
    assert len(protocols) == 4
    assert all("v7" in protocol for protocol in protocols)


def test_a13_projection_protocols_are_not_truth_protocol_aliases():
    assert knowledge_undercutter_truth.PROJECTION_PROTOCOL != knowledge_undercutter_truth.TRUTH_PROTOCOL
    assert verification_defeasible_truth.PROJECTION_PROTOCOL != verification_defeasible_truth.TRUTH_PROTOCOL
