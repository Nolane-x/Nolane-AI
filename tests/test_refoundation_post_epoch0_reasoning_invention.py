from __future__ import annotations

import importlib
import importlib.util


def test_reasoning_invention_canonical_module_exists() -> None:
    spec = importlib.util.find_spec("nolane.external_core.reasoning_invention")
    assert spec is not None, "canonical Reasoning/Invention protocol module is missing"


def test_reasoning_invention_declares_exact_component_revision() -> None:
    module = importlib.import_module("nolane.external_core.reasoning_invention")
    assert module.COMPONENT_ID == "external.reasoning_invention"
    assert module.COMPONENT_VERSION == "0.0.1"
