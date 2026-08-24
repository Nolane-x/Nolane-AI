from __future__ import annotations

from cogcoder.refoundation.component_versions import (
    component_revision_map,
    component_version,
    next_component_version,
)
from cogcoder.refoundation.manifests import build_component_manifests


# Independent revision slots are architectural state, not a snapshot of one
# migration wave. This set records components whose implementation authority
# has actually moved far enough to advance its local Epoch-0 revision.
ACCEPTED_REVISION_ONE_COMPONENTS = {
    "schemas.identity",
    "core.canonical_digest",
    "organization.identity",
    "organization.authority",
    "organization.events",
    "organization.tasks",
    "organization.lifecycle",
    "organization.coordination.leases",
    "organization.coordination.delivery",
    "organization.coordination.conflicts",
    "organization.coordination",
    "organization.central",
    "external.artifacts",
    "external.verification",
    "external.evidence",
    "external.experience",
    "external.self_model",
    "external.skills",
    "external.memory.fabric",
    "external.memory.lifecycle",
    "external.memory.retrieval",
    "external.knowledge",
    "external.epistemic",
    "external.requirements",
}


def test_every_component_has_an_independent_revision_slot() -> None:
    manifests = build_component_manifests()
    revisions = component_revision_map()
    assert set(revisions) == {row.component_id for row in manifests}

    expected = {
        component_id: 1 if component_id in ACCEPTED_REVISION_ONE_COMPONENTS else 0
        for component_id in revisions
    }
    assert revisions == expected

    for row in manifests:
        assert str(row.version) == str(component_version(row.component_id))
        assert row.version.revision == revisions[row.component_id]


def test_component_version_lookup_is_local_not_global() -> None:
    for component_id in ACCEPTED_REVISION_ONE_COMPONENTS:
        assert str(component_version(component_id)) == "0.0.1"

    # Independent components that have not yet migrated remain at their own
    # local Epoch-0 revision even as adjacent components advance.
    assert str(component_version("external.context")) == "0.0.0"
    assert str(component_version("external.planning")) == "0.0.0"
    assert str(next_component_version("external.context")) == "0.0.1"
    assert str(component_version("external.planning")) == "0.0.0"


def test_unknown_component_revision_fails_closed() -> None:
    try:
        component_version("unknown.component")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown component must not inherit a global version")
