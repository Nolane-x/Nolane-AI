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
        "organization.events": 2,
        "organization.tasks": 2,
        "organization.lifecycle": 1,
        "organization.coordination.leases": 1,
        "organization.coordination.delivery": 1,
        "organization.coordination.conflicts": 1,
        "organization.coordination": 1,
        "organization.central": 1,
        "external.artifacts": 1,
        "external.assurance": 1,
        "external.individual_evolution": 3,
        "external.operations": 1,
        "external.research": 1,
        "external.cognitive_library": 1,
        "external.causal": 1,
        "external.capability_acquisition": 1,
        "external.candidate_synthesis": 4,
        "external.transfer_meta": 1,
        "external.experimentation": 1,
        "external.verification": 1,
        "external.evidence": 1,
        "external.experience": 2,
        "external.self_model": 2,
        "external.skills": 3,
        "external.memory.fabric": 2,
        "external.memory.lifecycle": 5,
        "external.memory.retrieval": 4,
        "external.knowledge": 2,
        "external.epistemic": 1,
        "external.requirements": 1,
        "external.planning": 1,
        "external.architecture": 1,
        "external.integration": 1,
        "external.context": 1,
        "external.invokable_cores": 2,
        "external.execution.workspace": 3,
        "external.execution.executor": 1,
        "external.execution.control": 3,
        "external.coding.claims": 1,
        "external.coding.patches": 1,
        "external.coding.control": 1,
        "external.debugging": 1,
        "external.ui_ux": 1,
        "evaluation.regimes": 1,
        "evaluation.evidence": 1,
        "evaluation.stress": 1,
        "evaluation.claims": 1,
        "evaluation.parameters": 1,
        "evaluation.release": 1,
        "evaluation.scaling": 1,
        "evaluation.campaign": 1,
        "neural.inference_bridge": 1,
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
