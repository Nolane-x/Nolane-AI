from __future__ import annotations

import importlib

from nolane.metadata.component_versions import component_version


REASONING_FAMILY_MODULES = (
    "nolane.external_core.reasoning_invention",
    "nolane.external_core.reasoning_evaluation",
    "nolane.external_core.reasoning_frontier",
    "nolane.external_core.reasoning_metacontrol",
    "nolane.external_core.reasoning_review",
    "nolane.external_core.reasoning_meta_learning",
    "nolane.external_core.reasoning_episode",
    "nolane.external_core.reasoning_policy_evolution",
)


def test_c10_family_participates_in_c11_atomic_v005_cutover() -> None:
    rows = tuple(importlib.import_module(name) for name in REASONING_FAMILY_MODULES)
    assert {row.COMPONENT_ID for row in rows} == {"external.reasoning_invention"}
    assert {row.COMPONENT_VERSION for row in rows} == {"0.0.5"}
    assert str(component_version("external.reasoning_invention")) == "0.0.5"
