from __future__ import annotations

from cogcoder.refoundation.component_versions import (
    component_revision_map,
    component_version,
    next_component_version,
)
from cogcoder.refoundation.manifests import build_component_manifests


# Independent revision slots are architectural state, not a snapshot of one
# migration wave. Keep the exact accepted local revision for every component
# that has moved beyond Epoch-0 bootstrap. Components absent here remain 0.
ACCEPTED_COMPONENT_REVISIONS = {
    "schemas.identity": 1,
    "core.canonical_digest": 1,
    "organization.identity": 1,
    "organization.authority": 1,
    "organization.events": 1,
    "organization.tasks": 2,
    "organization.lifecycle": 1,
    "organization.coordination.leases": 1,
    "organization.coordination.delivery": 1,
    "organization.coordination.conflicts": 1,
    "organization.coordination": 1,
    "organization.central": 1,
    "external.artifacts": 1,
    "external.verification": 1,
    "external.evidence": 1,
    "external.experience": 1,
    "external.self_model": 1,
    "external.skills": 1,
    "external.memory.fabric": 1,
    "external.memory.lifecycle": 1,
    "external.memory.retrieval": 1,
    "external.knowledge": 1,
    "external.epistemic": 1,
    "external.requirements": 1,
    "external.planning": 1,
    "external.architecture": 1,
    "external.integration": 1,
    "external.invokable_cores": 1,
}
ACCEPTED_REVISION_ONE_COMPONENTS = {
    component_id for component_id, revision in ACCEPTED_COMPONENT_REVISIONS.items() if revision == 1
}


def test_every_component_has_an_independent_revision_slot() -> None:
    manifests = build_component_manifests()
    revisions = component_revision_map()
    assert set(revisions) == {row.component_id for row in manifests}

    expected = {
        component_id: ACCEPTED_COMPONENT_REVISIONS.get(component_id, 0)
        for component_id in revisions
    }
    assert revisions == expected

    for row in manifests:
        assert str(row.version) == str(component_version(row.component_id))
        assert row.version.revision == revisions[row.component_id]


def test_component_version_lookup_is_local_not_global() -> None:
    for component_id, revision in ACCEPTED_COMPONENT_REVISIONS.items():
        assert str(component_version(component_id)) == f"0.0.{revision}"

    assert str(component_version("external.context")) == "0.0.0"
    assert str(next_component_version("external.context")) == "0.0.1"
    assert str(component_version("external.architecture")) == "0.0.1"
    assert str(next_component_version("external.architecture")) == "0.0.2"
    assert str(component_version("external.integration")) == "0.0.1"
    assert str(next_component_version("external.integration")) == "0.0.2"
    assert str(component_version("external.invokable_cores")) == "0.0.1"
    assert str(next_component_version("external.invokable_cores")) == "0.0.2"
    assert str(component_version("organization.tasks")) == "0.0.2"
    assert str(next_component_version("organization.tasks")) == "0.0.3"


def test_unknown_component_revision_fails_closed() -> None:
    try:
        component_version("unknown.component")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown component must not inherit a global version")
