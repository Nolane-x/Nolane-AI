from __future__ import annotations

from nolane.external_core import causal, causal_challenge
from nolane.metadata.component_versions import component_version


def test_causal_v002_surfaces_share_canonical_component_revision() -> None:
    expected = str(component_version("external.causal"))

    assert expected == "0.0.2"
    assert causal.COMPONENT_ID == causal_challenge.COMPONENT_ID == "external.causal"
    assert causal.COMPONENT_VERSION == expected
    assert causal_challenge.COMPONENT_VERSION == expected
