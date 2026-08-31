from __future__ import annotations

from cogcoder.refoundation.component_versions import component_version


def test_memory_lifecycle_version_is_v005() -> None:
    import nolane.memory.lifecycle as lifecycle

    assert lifecycle.COMPONENT_VERSION == "0.0.5"
    assert str(component_version("external.memory.lifecycle")) == "0.0.5"
