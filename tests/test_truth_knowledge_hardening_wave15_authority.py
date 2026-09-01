from __future__ import annotations

import importlib

import pytest


_A15_SIDECARS = (
    ("nolane.external_core.evidence_context_truth", "external.evidence"),
    ("nolane.external_core.knowledge_context_truth", "external.knowledge"),
    ("nolane.external_core.epistemic_context_truth", "external.epistemic"),
    ("nolane.external_core.verification_context_truth", "external.verification"),
    ("nolane.external_core.assurance_context_truth", "external.assurance"),
)


@pytest.mark.parametrize(("module_name", "parent_id"), _A15_SIDECARS)
def test_a15_context_sidecars_bind_existing_parent_without_new_authority(
    module_name: str,
    parent_id: str,
):
    module = importlib.import_module(module_name)
    assert module.PARENT_COMPONENT_ID == parent_id
    assert not hasattr(module, "COMPONENT_ID")


def test_a15_context_sidecars_cover_exactly_the_five_family_a_parents():
    parents = {
        importlib.import_module(module_name).PARENT_COMPONENT_ID
        for module_name, _ in _A15_SIDECARS
    }
    assert parents == {
        "external.evidence",
        "external.knowledge",
        "external.epistemic",
        "external.verification",
        "external.assurance",
    }
