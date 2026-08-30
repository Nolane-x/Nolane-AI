from __future__ import annotations

from copy import deepcopy
import importlib

import pytest

from nolane.metadata.component_versions import component_version


EXPECTED = {
    "external.evidence": ("nolane.external_core.evidence", "nolane.external_core.evidence_truth", "truth-evidence-v1"),
    "external.knowledge": ("nolane.memory.knowledge", "nolane.external_core.knowledge_truth", "truth-knowledge-v1"),
    "external.epistemic": ("nolane.external_core.epistemic", "nolane.external_core.epistemic_truth", "truth-epistemic-snapshot-v1"),
    "external.verification": ("nolane.external_core.verification", "nolane.external_core.verification_truth", "truth-verification-ledger-v1"),
    "external.assurance": ("nolane.external_core.assurance", "nolane.external_core.assurance_truth", "truth-assurance-v1"),
}


def _subprotocols():
    return importlib.import_module("nolane.metadata.subprotocols")


def test_truth_protocol_binding_registry_is_canonical_metadata_not_a_sixth_runtime_component():
    module = _subprotocols()
    assert module.REGISTRY_ID == "metadata.subprotocol_bindings"
    assert module.REGISTRY_VERSION == "0.0.1"
    assert not hasattr(module, "COMPONENT_ID")

    registry = module.build_truth_knowledge_subprotocol_registry()
    assert registry.registry_id == module.REGISTRY_ID
    assert registry.registry_version == module.REGISTRY_VERSION
    assert len(registry.bindings) == 5
    assert {
        row.parent_component_id: (row.parent_canonical_module, row.protocol_module, row.protocol_id)
        for row in registry.bindings
    } == EXPECTED


def test_registry_validates_parent_and_helper_authority_bidirectionally_without_conflating_component_versions():
    module = _subprotocols()
    registry = module.build_truth_knowledge_subprotocol_registry()
    assert registry.validate_live()

    from nolane.metadata.implementation_status import ImplementationStatus, build_component_implementation_ledger

    ledger = build_component_implementation_ledger()
    for row in registry.bindings:
        parent = ledger[row.parent_component_id]
        helper = importlib.import_module(row.protocol_module)
        assert parent.status is ImplementationStatus.CANONICAL_NATIVE
        assert parent.canonical_write_authority
        assert parent.canonical_module == row.parent_canonical_module
        assert helper.PARENT_COMPONENT_ID == row.parent_component_id
        assert helper.TRUTH_PROTOCOL == row.protocol_id
        assert not hasattr(helper, "COMPONENT_ID")
        # Subprotocol binding metadata is orthogonal to parent component software revision.
        assert str(component_version(row.parent_component_id)) == "0.0.1"


def test_subprotocol_registry_is_content_addressed_total_unique_and_tamper_evident():
    module = _subprotocols()
    registry = module.build_truth_knowledge_subprotocol_registry()
    assert len({row.parent_component_id for row in registry.bindings}) == 5
    assert len({row.protocol_module for row in registry.bindings}) == 5
    assert len({row.protocol_id for row in registry.bindings}) == 5

    restored = type(registry).from_state(registry.to_state())
    assert restored == registry

    tampered = deepcopy(registry.to_state())
    tampered["bindings"][0]["protocol_module"] = "nolane.external_core.forged_truth"
    with pytest.raises(ValueError, match="subprotocol binding digest mismatch"):
        type(registry).from_state(tampered)
