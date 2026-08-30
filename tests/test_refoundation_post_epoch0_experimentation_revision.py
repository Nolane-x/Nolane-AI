from __future__ import annotations

from nolane.external_core import experiment_design, experimentation
from nolane.metadata.component_versions import component_version


def test_experimentation_v002_surfaces_share_canonical_component_revision() -> None:
    expected = str(component_version("external.experimentation"))

    assert expected == "0.0.2"
    assert experimentation.COMPONENT_ID == experiment_design.COMPONENT_ID == "external.experimentation"
    assert experimentation.COMPONENT_VERSION == expected
    assert experiment_design.COMPONENT_VERSION == expected
