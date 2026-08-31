from __future__ import annotations

import importlib

from nolane.metadata.component_versions import component_version


def test_reasoning_invention_revision_is_coherent() -> None:
    core = importlib.import_module("nolane.external_core.reasoning_invention")
    evaluation = importlib.import_module("nolane.external_core.reasoning_evaluation")

    assert core.COMPONENT_ID == "external.reasoning_invention"
    assert evaluation.COMPONENT_ID == "external.reasoning_invention"
    assert core.COMPONENT_VERSION == "0.0.2"
    assert evaluation.COMPONENT_VERSION == "0.0.2"
    assert str(component_version("external.reasoning_invention")) == "0.0.2"
