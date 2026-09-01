from __future__ import annotations

import importlib

import pytest


_A16_SIDECARS = (
    ("nolane.external_core.evidence_observation_truth", "external.evidence"),
    ("nolane.external_core.knowledge_observation_truth", "external.knowledge"),
    ("nolane.external_core.epistemic_observation_truth", "external.epistemic"),
    ("nolane.external_core.verification_observation_truth", "external.verification"),
    ("nolane.external_core.assurance_observation_truth", "external.assurance"),
)


@pytest.mark.parametrize(("module_name", "parent_id"), _A16_SIDECARS)
def test_a16_observation_sidecars_bind_existing_parent_without_new_authority(
    module_name: str,
    parent_id: str,
):
    module = importlib.import_module(module_name)
    assert module.PARENT_COMPONENT_ID == parent_id
    assert not hasattr(module, "COMPONENT_ID")


def test_a16_observation_sidecars_cover_exactly_the_five_family_a_parents():
    parents = {
        importlib.import_module(module_name).PARENT_COMPONENT_ID
        for module_name, _ in _A16_SIDECARS
    }
    assert parents == {
        "external.evidence",
        "external.knowledge",
        "external.epistemic",
        "external.verification",
        "external.assurance",
    }


def test_a16_v10_protocol_domains_are_distinct_from_v9():
    from nolane.external_core import assurance_context_truth, assurance_observation_truth
    from nolane.external_core import epistemic_context_truth, epistemic_observation_truth
    from nolane.external_core import verification_context_truth, verification_observation_truth

    assert epistemic_observation_truth.TRUTH_PROTOCOL != epistemic_context_truth.TRUTH_PROTOCOL
    assert verification_observation_truth.TRUTH_PROTOCOL != verification_context_truth.TRUTH_PROTOCOL
    assert assurance_observation_truth.TRUTH_PROTOCOL != assurance_context_truth.TRUTH_PROTOCOL
