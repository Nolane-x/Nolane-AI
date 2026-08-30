from __future__ import annotations

import importlib

from nolane.external_core import assurance, epistemic, evidence, verification
from nolane.memory import knowledge
from nolane.metadata.component_versions import component_version


PARENTS = {
    "external.evidence": (evidence, "nolane.external_core.evidence_truth", "truth-evidence-v1"),
    "external.knowledge": (knowledge, "nolane.external_core.knowledge_truth", "truth-knowledge-v1"),
    "external.epistemic": (epistemic, "nolane.external_core.epistemic_truth", "truth-epistemic-snapshot-v1"),
    "external.verification": (verification, "nolane.external_core.verification_truth", "truth-verification-ledger-v1"),
    "external.assurance": (assurance, "nolane.external_core.assurance_truth", "truth-assurance-v1"),
}


def test_canonical_a_parents_explicitly_acknowledge_their_truth_protocol_modules():
    for component_id, (parent, helper_name, protocol_id) in PARENTS.items():
        assert parent.COMPONENT_ID == component_id
        assert parent.TRUTH_PROTOCOL_MODULE == helper_name
        assert parent.TRUTH_PROTOCOL_ID == protocol_id
        helper = importlib.import_module(helper_name)
        assert helper.PARENT_COMPONENT_ID == component_id
        assert helper.TRUTH_PROTOCOL == protocol_id


def test_truth_semantic_acceptance_advances_all_five_parent_component_revisions():
    for component_id, (parent, _helper_name, _protocol_id) in PARENTS.items():
        assert str(component_version(component_id)) == "0.0.2"
        assert parent.COMPONENT_VERSION == "0.0.2"


def test_parent_truth_protocol_bindings_are_unique_and_total_for_family_a():
    modules = [parent.TRUTH_PROTOCOL_MODULE for parent, _, _ in PARENTS.values()]
    protocols = [parent.TRUTH_PROTOCOL_ID for parent, _, _ in PARENTS.values()]
    assert len(modules) == len(set(modules)) == 5
    assert len(protocols) == len(set(protocols)) == 5
