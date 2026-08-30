from __future__ import annotations

from nolane.external_core import capability_acquisition, capability_probation
from nolane.metadata.component_versions import component_version


def test_capability_acquisition_v002_surfaces_share_canonical_component_revision() -> None:
    expected = str(component_version("external.capability_acquisition"))

    assert expected == "0.0.2"
    assert (
        capability_acquisition.COMPONENT_ID
        == capability_probation.COMPONENT_ID
        == "external.capability_acquisition"
    )
    assert capability_acquisition.COMPONENT_VERSION == expected
    assert capability_probation.COMPONENT_VERSION == expected
