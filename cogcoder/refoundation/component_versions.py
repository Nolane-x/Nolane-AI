from __future__ import annotations

from ._component_specs import COMPONENT_SPECS
from .versioning import ComponentVersion


# Each component owns its own patch-level revision counter.  Epoch 0 resets all
# components to 0.0.0; later changes increment only the affected entries.
_COMPONENT_REVISIONS: dict[str, int] = {component_id: 0 for component_id, *_ in COMPONENT_SPECS}


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
