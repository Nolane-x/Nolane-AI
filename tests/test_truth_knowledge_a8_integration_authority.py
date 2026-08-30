from __future__ import annotations

from nolane.external_core import assurance_truth, epistemic_truth, evidence_truth, knowledge_truth, verification_truth


def test_a8_integrated_tree_preserves_exact_truth_parent_authorities():
    bindings = {
        evidence_truth.PARENT_COMPONENT_ID,
        knowledge_truth.PARENT_COMPONENT_ID,
        epistemic_truth.PARENT_COMPONENT_ID,
        verification_truth.PARENT_COMPONENT_ID,
        assurance_truth.PARENT_COMPONENT_ID,
    }
    assert bindings == {
        "external.evidence",
        "external.knowledge",
        "external.epistemic",
        "external.verification",
        "external.assurance",
    }


def test_a8_truth_helpers_do_not_seize_component_authority_after_integration():
    for module in (
        evidence_truth,
        knowledge_truth,
        epistemic_truth,
        verification_truth,
        assurance_truth,
    ):
        assert not hasattr(module, "COMPONENT_ID")
