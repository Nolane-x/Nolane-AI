from __future__ import annotations

from cogcoder.refoundation.component_versions import (
    component_version,
    next_component_version,
)
from nolane.organization.authority import COMPONENT_VERSION as AUTHORITY_COMPONENT_VERSION


def test_temporal_override_authority_advances_public_semantic_version() -> None:
    assert AUTHORITY_COMPONENT_VERSION == "0.0.2"


def test_temporal_override_authority_advances_implementation_revision() -> None:
    assert str(component_version("organization.authority")) == "0.0.3"
    assert str(next_component_version("organization.authority")) == "0.0.4"
