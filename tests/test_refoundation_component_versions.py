from __future__ import annotations

from cogcoder.refoundation.component_versions import (
    component_revision_map,
    component_version,
    next_component_version,
)
from cogcoder.refoundation.manifests import build_component_manifests


WAVE2_NATIVE_REVISIONS = {
    "organization.identity": 1,
    "organization.authority": 1,
    "organization.events": 1,
    "organization.tasks": 1,
    "organization.lifecycle": 1,
    "organization.coordination.leases": 1,
    "organization.coordination.delivery": 1,
    "organization.coordination.conflicts": 1,
    "organization.coordination": 1,
    "organization.central": 1,
}


def test_every_component_has_an_independent_revision_slot() -> None:
    manifests = build_component_manifests()
    revisions = component_revision_map()
    assert set(revisions) == {row.component_id for row in manifests}
    for component_id, revision in revisions.items():
        assert revision == WAVE2_NATIVE_REVISIONS.get(component_id, 0)
    for row in manifests:
        assert str(row.version) == f"0.0.{WAVE2_NATIVE_REVISIONS.get(row.component_id, 0)}"


def test_component_version_lookup_is_local_not_global() -> None:
    for component_id in WAVE2_NATIVE_REVISIONS:
        assert str(component_version(component_id)) == "0.0.1"
    assert str(component_version("external.memory.fabric")) == "0.0.0"
    assert str(component_version("external.planning")) == "0.0.0"
    assert str(next_component_version("external.memory.fabric")) == "0.0.1"
    assert str(component_version("external.planning")) == "0.0.0"


def test_unknown_component_revision_fails_closed() -> None:
    try:
        component_version("unknown.component")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown component must not inherit a global version")
