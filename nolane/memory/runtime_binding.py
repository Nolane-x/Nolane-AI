from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from nolane.memory.learning_authority import LearningEvidenceAuthority
from nolane.memory.learning_substrate import LearningSubstrate


_SKILL_KEYS = ("skill_validations", "learning_authority")
_LIFECYCLE_KEYS = (
    "metadata",
    "tombstones",
    "forget_receipts",
    "forget_counter",
    "compactions",
    "anchor_health",
)
_RETRIEVAL_KEYS = ("retrieval_policies", "retrieval_receipts", "retrieval_snapshots")
_OVERLAY_KEYS = _SKILL_KEYS + _LIFECYCLE_KEYS + _RETRIEVAL_KEYS


def _default_overlay_value(key: str):
    if key == "learning_authority":
        return {}
    if key == "forget_counter":
        return 0
    return []


def _section(state: Mapping[str, Any] | None, *, allowed: tuple[str, ...], label: str) -> dict[str, Any]:
    raw = {} if state is None else {str(key): value for key, value in state.items()}
    unknown = tuple(sorted(set(raw) - set(allowed)))
    if unknown:
        raise ValueError(f"unknown {label} state field(s): {unknown}")
    return {key: raw.get(key, _default_overlay_value(key)) for key in allowed}


def split_runtime_learning_state(
    substrate: LearningSubstrate,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Project the B overlay into sections owned by existing canonical authorities."""

    state = substrate.to_state()
    authority = getattr(substrate, "learning_authority", None)
    skills = {
        "skill_validations": state["skill_validations"],
        "learning_authority": {} if authority is None else authority.to_state(),
    }
    lifecycle = {key: state[key] for key in _LIFECYCLE_KEYS}
    retrieval = {key: state[key] for key in _RETRIEVAL_KEYS}
    return skills, lifecycle, retrieval


def _overlay_state(
    *,
    skill_state: Mapping[str, Any] | None,
    lifecycle_state: Mapping[str, Any] | None,
    retrieval_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    skills = _section(skill_state, allowed=_SKILL_KEYS, label="learning skill governance")
    lifecycle = _section(
        lifecycle_state,
        allowed=_LIFECYCLE_KEYS,
        label="memory learning lifecycle",
    )
    retrieval = _section(
        retrieval_state,
        allowed=_RETRIEVAL_KEYS,
        label="memory learning retrieval",
    )
    overlay = {**skills, **lifecycle, **retrieval}
    if set(overlay) != set(_OVERLAY_KEYS):
        raise AssertionError("runtime learning overlay partition is incomplete")
    return overlay


def _copy_validated_overlay(target: LearningSubstrate, validated: LearningSubstrate) -> None:
    # These are the only state containers owned by the orchestration overlay.
    # Canonical Memory/Lifecycle/Relations/Skills/Experience authorities remain
    # the objects injected into ``target`` and are never replaced here.
    target._metadata = dict(validated._metadata)
    target._tombstones = dict(validated._tombstones)
    target._forget_receipts = dict(validated._forget_receipts)
    target._forget_counter = int(validated._forget_counter)
    target._skill_validations = dict(validated._skill_validations)
    target._retrieval_policies = dict(validated._retrieval_policies)
    target._retrieval_receipts = dict(validated._retrieval_receipts)
    target._retrieval_snapshots = {
        digest: deepcopy(snapshot)
        for digest, snapshot in validated._retrieval_snapshots.items()
    }
    target._compactions = dict(validated._compactions)
    target._anchor_health = {
        memory_id: list(receipts)
        for memory_id, receipts in validated._anchor_health.items()
    }


def restore_runtime_learning_state(
    *,
    registry,
    events,
    memory,
    lifecycle,
    relations,
    skills,
    experiences,
    skill_state: Mapping[str, Any] | None = None,
    lifecycle_state: Mapping[str, Any] | None = None,
    retrieval_state: Mapping[str, Any] | None = None,
) -> LearningSubstrate:
    """Validate persisted B overlay, then bind it to one shared authority graph.

    Validation is deliberately delegated to ``LearningSubstrate.from_state`` so
    runtime restore cannot become a weaker deserialization path than direct
    substrate restore. Only validated overlay rows are copied back; authority
    objects are the exact instances supplied by the composition root. The
    v0.0.11 learning-evidence ledger is restored separately, then rebound to
    every B consumer rather than duplicated inside their serialized state.
    """

    overlay = _overlay_state(
        skill_state=skill_state,
        lifecycle_state=lifecycle_state,
        retrieval_state=retrieval_state,
    )
    authority_state = overlay.pop("learning_authority", {})
    authority = LearningEvidenceAuthority.from_state(authority_state)
    full_state = {
        "memory": memory.to_state(),
        "lifecycle": lifecycle.to_state(),
        "relations": relations.to_state(),
        "skills": skills.to_state(),
        "experiences": experiences.to_state(),
        **overlay,
    }
    validated = LearningSubstrate.from_state(
        registry=registry,
        events=events,
        state=full_state,
        learning_authority=authority,
    )
    target = LearningSubstrate(
        registry=registry,
        events=events,
        memory=memory,
        lifecycle=lifecycle,
        relations=relations,
        skills=skills,
        experiences=experiences,
        learning_authority=authority,
    )
    _copy_validated_overlay(target, validated)
    experiences.learning_authority = authority
    return target


def _is_empty_lifecycle_state(state: Mapping[str, Any]) -> bool:
    return not state.get("receipts") and int(state.get("counter", 0)) == 0


def _is_empty_relation_state(state: Mapping[str, Any]) -> bool:
    return not state.get("relations") and int(state.get("counter", 0)) == 0


def _is_empty_experience_state(state: Mapping[str, Any]) -> bool:
    return not state.get("experiences") and not state.get("attributions")


def _bind_downstream_authority(runtime, bound: LearningSubstrate) -> None:
    authority = bound.learning_authority
    individual = runtime.individual_evolution
    runtime.evolution.learning_authority = authority
    individual.learning_authority = authority
    individual.experiences.learning_authority = authority
    individual.self_models.learning_authority = authority
    bound.experiences.learning_authority = authority


def bind_runtime_learning_authorities(runtime) -> LearningSubstrate:
    """Collapse legacy B duplicates into one runtime authority graph.

    Memory Context owns the canonical lifecycle/relation objects because its
    retrieval/context compiler is already bound to them. Individual Evolution
    and LearningSubstrate must share one ExperienceLedger. Any non-empty
    divergent state fails closed rather than being silently discarded.
    """

    source = runtime.learning_substrate
    context = runtime.memory_context
    individual = runtime.individual_evolution

    if source.memory is not runtime.memory or source.skills is not runtime.evolution:
        raise ValueError("runtime learning substrate must share canonical memory and skill authority")
    if context.memory is not runtime.memory or context.evolution is not runtime.evolution:
        raise ValueError("memory context must share canonical memory and skill authority")

    source_lifecycle = source.lifecycle.to_state()
    context_lifecycle = context.lifecycle.to_state()
    if source_lifecycle != context_lifecycle and not _is_empty_lifecycle_state(source_lifecycle):
        raise ValueError("divergent runtime memory lifecycle authorities cannot be rebound")

    source_relations = source.relations.to_state()
    context_relations = context.relations.to_state()
    if source_relations != context_relations and not _is_empty_relation_state(source_relations):
        raise ValueError("divergent runtime memory relation authorities cannot be rebound")

    source_experiences = source.experiences.to_state()
    individual_experiences = individual.experiences.to_state()
    if source_experiences == individual_experiences:
        experiences = individual.experiences
    elif _is_empty_experience_state(source_experiences):
        experiences = individual.experiences
    elif _is_empty_experience_state(individual_experiences):
        experiences = source.experiences
    else:
        raise ValueError("divergent runtime experience authorities cannot be rebound")

    skill_state, lifecycle_state, retrieval_state = split_runtime_learning_state(source)
    bound = restore_runtime_learning_state(
        registry=runtime.registry,
        events=runtime.ledger,
        memory=runtime.memory,
        lifecycle=context.lifecycle,
        relations=context.relations,
        skills=runtime.evolution,
        experiences=experiences,
        skill_state=skill_state,
        lifecycle_state=lifecycle_state,
        retrieval_state=retrieval_state,
    )
    runtime.learning_substrate = bound
    runtime.individual_evolution.experiences = experiences
    runtime.individual_evolution.governed_skill_promoter = bound
    _bind_downstream_authority(runtime, bound)
    return bound


def restore_runtime_learning_overlay(runtime, state: Mapping[str, Any]) -> LearningSubstrate:
    """Restore the partitioned B overlay onto already unified runtime authorities."""

    bound = restore_runtime_learning_state(
        registry=runtime.registry,
        events=runtime.ledger,
        memory=runtime.memory,
        lifecycle=runtime.memory_context.lifecycle,
        relations=runtime.memory_context.relations,
        skills=runtime.evolution,
        experiences=runtime.individual_evolution.experiences,
        skill_state=state.get("learning_substrate", {}),
        lifecycle_state=state.get("memory_learning_lifecycle", {}),
        retrieval_state=state.get("memory_learning_retrieval", {}),
    )
    runtime.learning_substrate = bound
    runtime.individual_evolution.governed_skill_promoter = bound
    _bind_downstream_authority(runtime, bound)
    return bound


__all__ = (
    "bind_runtime_learning_authorities",
    "restore_runtime_learning_overlay",
    "restore_runtime_learning_state",
    "split_runtime_learning_state",
)
