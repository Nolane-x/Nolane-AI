from __future__ import annotations

from ._component_specs import COMPONENT_SPECS
from .versioning import ComponentVersion


# Each component owns its own patch-level revision counter. Epoch 0 bootstraps
# every component at 0.0.0; accepted native extractions advance only the
# components whose implementation authority or accepted local semantics moved.
_COMPONENT_REVISIONS: dict[str, int] = {component_id: 0 for component_id, *_ in COMPONENT_SPECS}
_COMPONENT_REVISIONS.update(
    {
        "core.canonical_digest": 1,
        "schemas.identity": 1,
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
    }
)


def component_revision_map() -> dict[str, int]:
    return dict(_COMPONENT_REVISIONS)


def component_version(component_id: str) -> ComponentVersion:
    key = str(component_id)
    try:
        revision = _COMPONENT_REVISIONS[key]
    except KeyError as exc:
        raise KeyError(f"unknown canonical component version id: {key}") from exc
    return ComponentVersion(0, 0, int(revision))


def next_component_version(component_id: str) -> ComponentVersion:
    return component_version(component_id).next_revision()