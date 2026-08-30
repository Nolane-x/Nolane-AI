from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.fabric import MemoryEntry, MemoryFabric, MemoryScope, MemoryStatus
from nolane.memory.lifecycle import MemoryLifecycleLedger, MemoryRelationGraph, MemoryRelationKind
from nolane.memory.skills import SkillEvolutionEngine, SkillRecord, SkillScope


class MemoryKind(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    STRATEGY = "strategy"
    FAILURE = "failure"
    PROJECT_STATE = "project_state"
    DECISION = "decision"


class EpistemicType(str, Enum):
    OBSERVATION = "observation"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    VERIFIED = "verified"
    REJECTED = "rejected"


_EPISTEMIC_RANK = {
    EpistemicType.REJECTED: 0,
    EpistemicType.HYPOTHESIS: 1,
    EpistemicType.INFERENCE: 2,
    EpistemicType.OBSERVATION: 3,
    EpistemicType.VERIFIED: 4,
}


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise ValueError("memory temporal metadata must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("memory temporal metadata must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("memory temporal metadata must be timezone-aware")
    return parsed


@dataclass(frozen=True, slots=True)
class LearningMemoryMetadata:
    memory_id: str
    kind: MemoryKind
    epistemic_type: EpistemicType
    source_refs: tuple[str, ...] = ()
    valid_from: str | None = None
    valid_until: str | None = None
    version_scope: str | None = None
    last_verified_ref: str | None = None
    salience: float = 0.5
    failure_condition: str | None = None
    retry_if_changed: str | None = None

    def __post_init__(self) -> None:
        if not str(self.memory_id).strip():
            raise ValueError("learning memory metadata requires a memory id")
        if not 0.0 <= float(self.salience) <= 1.0:
            raise ValueError("memory salience must lie in [0, 1]")
        start = _parse_time(self.valid_from)
        end = _parse_time(self.valid_until)
        if start is not None and end is not None and end <= start:
            raise ValueError("memory valid_until must be later than valid_from")
        if self.kind is MemoryKind.FAILURE:
            if not str(self.failure_condition or "").strip():
                raise ValueError("failure memory requires the failure condition")
            if not str(self.retry_if_changed or "").strip():
                raise ValueError("failure memory requires an explicit retry condition")

    def to_state(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "kind": self.kind.value,
            "epistemic_type": self.epistemic_type.value,
            "source_refs": list(self.source_refs),
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "version_scope": self.version_scope,
            "last_verified_ref": self.last_verified_ref,
            "salience": self.salience,
            "failure_condition": self.failure_condition,
            "retry_if_changed": self.retry_if_changed,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "LearningMemoryMetadata":
        return cls(
            memory_id=str(state["memory_id"]),
            kind=MemoryKind(str(state["kind"])),
            epistemic_type=EpistemicType(str(state["epistemic_type"])),
            source_refs=tuple(str(x) for x in state.get("source_refs", ())),
            valid_from=None if state.get("valid_from") is None else str(state["valid_from"]),
            valid_until=None if state.get("valid_until") is None else str(state["valid_until"]),
            version_scope=None if state.get("version_scope") is None else str(state["version_scope"]),
            last_verified_ref=None if state.get("last_verified_ref") is None else str(state["last_verified_ref"]),
            salience=float(state.get("salience", 0.5)),
            failure_condition=None if state.get("failure_condition") is None else str(state["failure_condition"]),
            retry_if_changed=None if state.get("retry_if_changed") is None else str(state["retry_if_changed"]),
        )


@dataclass(frozen=True, slots=True)
class MemoryTombstone:
    memory_id: str
    content_digest: str
    reason: str
    evidence_refs: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content_digest": self.content_digest,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryTombstone":
        return cls(
            memory_id=str(state["memory_id"]),
            content_digest=str(state["content_digest"]),
            reason=str(state["reason"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
        )


@dataclass(frozen=True, slots=True)
class RetrievedLearningMemory:
    memory: MemoryEntry
    metadata: LearningMemoryMetadata
    score: float


@dataclass(frozen=True, slots=True)
class LearningRetrievalBundle:
    selected: tuple[RetrievedLearningMemory, ...]
    rejected: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class SkillValidation:
    skill_id: str
    regression_evidence_ids: tuple[str, ...]
    causal_ablation_evidence_ids: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "regression_evidence_ids": list(self.regression_evidence_ids),
            "causal_ablation_evidence_ids": list(self.causal_ablation_evidence_ids),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SkillValidation":
        return cls(
            skill_id=str(state["skill_id"]),
            regression_evidence_ids=tuple(str(x) for x in state.get("regression_evidence_ids", ())),
            causal_ablation_evidence_ids=tuple(str(x) for x in state.get("causal_ablation_evidence_ids", ())),
        )


class LearningSubstrate:
    """Evidence-bounded orchestration across Memory/Learning primitives.

    This is not a second memory authority. It composes the canonical MemoryFabric,
    lifecycle ledger, relation graph, and skill engine while adding the missing
    cross-cutting contracts: epistemic typing, temporal/version validity,
    contradiction-safe retrieval, tombstoned forgetting and causal skill gates.
    """

    def __init__(
        self,
        *,
        registry,
        events,
        memory: MemoryFabric | None = None,
        lifecycle: MemoryLifecycleLedger | None = None,
        relations: MemoryRelationGraph | None = None,
        skills: SkillEvolutionEngine | None = None,
    ) -> None:
        self.registry = registry
        self.events = events
        self.memory = memory or MemoryFabric()
        self.lifecycle = lifecycle or MemoryLifecycleLedger(registry=registry, memory=self.memory, events=events)
        self.relations = relations or MemoryRelationGraph(registry=registry, memory=self.memory, events=events)
        self.skills = skills or SkillEvolutionEngine()
        self._metadata: dict[str, LearningMemoryMetadata] = {}
        self._tombstones: dict[str, MemoryTombstone] = {}
        self._skill_validations: dict[str, SkillValidation] = {}

    def remember(
        self,
        *,
        text: str,
        owner_agent_id: str,
        scope: MemoryScope,
        kind: MemoryKind,
        epistemic_type: EpistemicType,
        region: str | None = None,
        task_id: str | None = None,
        tags: tuple[str, ...] = (),
        evidence_ids: tuple[str, ...] = (),
        confidence: float = 1.0,
        dependencies: tuple[str, ...] = (),
        supersedes: str | None = None,
        source_refs: tuple[str, ...] = (),
        valid_from: str | None = None,
        valid_until: str | None = None,
        version_scope: str | None = None,
        last_verified_ref: str | None = None,
        salience: float = 0.5,
        failure_condition: str | None = None,
        retry_if_changed: str | None = None,
    ) -> MemoryEntry:
        kind = MemoryKind(kind)
        epistemic_type = EpistemicType(epistemic_type)
        validated = epistemic_type is EpistemicType.VERIFIED and bool(evidence_ids)
        status = MemoryStatus.ACTIVE if validated else MemoryStatus.QUARANTINED
        reason = None if validated else "awaiting_external_validation"
        row = self.memory.write(
            scope,
            text,
            owner_agent_id=owner_agent_id,
            region=region,
            task_id=task_id,
            tags=tags,
            evidence_ids=evidence_ids,
            confidence=confidence,
            dependencies=dependencies,
            supersedes=supersedes,
            initial_status=status,
            status_reason=reason,
        )
        metadata = LearningMemoryMetadata(
            memory_id=row.memory_id,
            kind=kind,
            epistemic_type=epistemic_type,
            source_refs=tuple(sorted({str(x) for x in source_refs})),
            valid_from=valid_from,
            valid_until=valid_until,
            version_scope=version_scope,
            last_verified_ref=last_verified_ref,
            salience=float(salience),
            failure_condition=failure_condition,
            retry_if_changed=retry_if_changed,
        )
        self._metadata[row.memory_id] = metadata
        return row

    def metadata(self, memory_id: str) -> LearningMemoryMetadata:
        self.memory.get(memory_id)
        try:
            return self._metadata[str(memory_id)]
        except KeyError as exc:
            raise KeyError(f"missing learning metadata for {memory_id}") from exc

    def relate(
        self,
        *,
        actor_agent_id: str,
        source_memory_id: str,
        target_memory_id: str,
        kind: MemoryRelationKind,
        evidence_refs: tuple[str, ...],
    ):
        return self.relations.add(
            actor_agent_id=actor_agent_id,
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            kind=kind,
            evidence_refs=evidence_refs,
        )

    @staticmethod
    def _temporal_rejection(metadata: LearningMemoryMetadata, as_of: datetime) -> str | None:
        start = _parse_time(metadata.valid_from)
        end = _parse_time(metadata.valid_until)
        if start is not None and as_of < start:
            return "not_yet_valid"
        if end is not None and as_of >= end:
            return "expired"
        return None

    def _score(self, row: MemoryEntry, metadata: LearningMemoryMetadata) -> float:
        return (
            _EPISTEMIC_RANK[metadata.epistemic_type] * 100.0
            + row.confidence * 50.0
            + metadata.salience * 20.0
            + (10.0 if row.evidence_ids else 0.0)
            + min(row.sequence, 1000000) / 1000000.0
        )

    def retrieve(
        self,
        *,
        agent_id: str,
        region: str,
        as_of: str,
        task_id: str | None = None,
        tags: tuple[str, ...] = (),
        limit: int = 8,
    ) -> LearningRetrievalBundle:
        if limit < 0:
            raise ValueError("learning retrieval limit must be non-negative")
        timestamp = _parse_time(as_of)
        assert timestamp is not None
        visible = self.memory.visible_entries(
            agent_id=agent_id,
            region=region,
            task_id=task_id,
            include_inactive=True,
        )
        wanted = {str(x) for x in tags}
        rejected: dict[str, str] = {}
        candidates: list[RetrievedLearningMemory] = []
        for row in visible:
            metadata = self._metadata.get(row.memory_id)
            if metadata is None:
                rejected[row.memory_id] = "missing_learning_metadata"
                continue
            temporal = self._temporal_rejection(metadata, timestamp)
            if temporal is not None:
                rejected[row.memory_id] = temporal
                continue
            if row.status is not MemoryStatus.ACTIVE:
                rejected[row.memory_id] = row.status.value
                continue
            if metadata.epistemic_type is EpistemicType.REJECTED:
                rejected[row.memory_id] = "epistemically_rejected"
                continue
            score = self._score(row, metadata)
            if wanted:
                score += 100.0 * len(wanted.intersection(row.tags))
            candidates.append(RetrievedLearningMemory(row, metadata, score))

        contradictions: dict[str, set[str]] = {}
        for relation in self.relations.relations():
            if relation.kind is not MemoryRelationKind.CONTRADICTS:
                continue
            contradictions.setdefault(relation.source_memory_id, set()).add(relation.target_memory_id)
            contradictions.setdefault(relation.target_memory_id, set()).add(relation.source_memory_id)

        selected: list[RetrievedLearningMemory] = []
        selected_ids: set[str] = set()
        for candidate in sorted(candidates, key=lambda item: (item.score, item.memory.sequence), reverse=True):
            conflicts = contradictions.get(candidate.memory.memory_id, set()).intersection(selected_ids)
            if conflicts:
                rejected[candidate.memory.memory_id] = "contradicted_by:" + sorted(conflicts)[0]
                continue
            selected.append(candidate)
            selected_ids.add(candidate.memory.memory_id)
            if len(selected) >= limit:
                break
        for candidate in candidates:
            if candidate.memory.memory_id not in selected_ids and candidate.memory.memory_id not in rejected:
                rejected[candidate.memory.memory_id] = "budget"
        return LearningRetrievalBundle(tuple(selected), tuple(sorted(rejected.items())))

    def forget(
        self,
        memory_id: str,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> MemoryTombstone:
        row = self.memory.get(memory_id)
        reason = str(reason).strip()
        if not reason:
            raise ValueError("forgetting requires an explicit reason")
        evidence = tuple(sorted({str(x) for x in evidence_refs if str(x)}))
        if not evidence:
            raise ValueError("forgetting requires evidence")
        if row.status is not MemoryStatus.ARCHIVED:
            self.lifecycle.transition(
                row.memory_id,
                actor_agent_id=actor_agent_id,
                new_status=MemoryStatus.ARCHIVED,
                reason=reason,
                evidence_refs=evidence,
            )
        tombstone = MemoryTombstone(
            memory_id=row.memory_id,
            content_digest=canonical_digest({"memory_id": row.memory_id, "text": row.text}),
            reason=reason,
            evidence_refs=evidence,
        )
        self._tombstones[row.memory_id] = tombstone
        return tombstone

    def tombstone(self, memory_id: str) -> MemoryTombstone:
        try:
            return self._tombstones[str(memory_id)]
        except KeyError as exc:
            raise KeyError(f"missing tombstone for {memory_id}") from exc

    def record_skill_validation(
        self,
        skill_id: str,
        *,
        regression_evidence_ids: tuple[str, ...],
        causal_ablation_evidence_ids: tuple[str, ...],
    ) -> SkillValidation:
        self.skills.get(skill_id)
        regressions = tuple(sorted({str(x) for x in regression_evidence_ids if str(x)}))
        causal = tuple(sorted({str(x) for x in causal_ablation_evidence_ids if str(x)}))
        if not regressions:
            raise ValueError("skill validation requires executed regression evidence")
        if not causal:
            raise ValueError("skill validation requires causal ablation evidence")
        row = SkillValidation(str(skill_id), regressions, causal)
        self._skill_validations[row.skill_id] = row
        return row

    def promote_skill(self, skill_id: str, scope: SkillScope) -> SkillRecord:
        validation = self._skill_validations.get(str(skill_id))
        if validation is None or not validation.regression_evidence_ids:
            raise PermissionError("persistent skill promotion requires executed regression evidence")
        if not validation.causal_ablation_evidence_ids:
            raise PermissionError("persistent skill promotion requires causal ablation evidence")
        return self.skills.promote(skill_id, scope)

    def to_state(self) -> dict[str, Any]:
        return {
            "memory": self.memory.to_state(),
            "lifecycle": self.lifecycle.to_state(),
            "relations": self.relations.to_state(),
            "skills": self.skills.to_state(),
            "metadata": [self._metadata[key].to_state() for key in sorted(self._metadata)],
            "tombstones": [self._tombstones[key].to_state() for key in sorted(self._tombstones)],
            "skill_validations": [self._skill_validations[key].to_state() for key in sorted(self._skill_validations)],
        }

    @classmethod
    def from_state(cls, *, registry, events, state: Mapping[str, Any]) -> "LearningSubstrate":
        memory = MemoryFabric.from_state(state.get("memory", {}))
        lifecycle = MemoryLifecycleLedger.from_state(
            registry=registry,
            memory=memory,
            events=events,
            state=state.get("lifecycle", {}),
        )
        relations = MemoryRelationGraph.from_state(
            registry=registry,
            memory=memory,
            events=events,
            state=state.get("relations", {}),
        )
        result = cls(
            registry=registry,
            events=events,
            memory=memory,
            lifecycle=lifecycle,
            relations=relations,
            skills=SkillEvolutionEngine.from_state(state.get("skills", {})),
        )
        result._metadata = {
            row.memory_id: row
            for row in (LearningMemoryMetadata.from_state(raw) for raw in state.get("metadata", ()))
        }
        result._tombstones = {
            row.memory_id: row
            for row in (MemoryTombstone.from_state(raw) for raw in state.get("tombstones", ()))
        }
        result._skill_validations = {
            row.skill_id: row
            for row in (SkillValidation.from_state(raw) for raw in state.get("skill_validations", ()))
        }
        for memory_id in result._metadata:
            memory.get(memory_id)
        for memory_id in result._tombstones:
            memory.get(memory_id)
        for skill_id in result._skill_validations:
            result.skills.get(skill_id)
        return result


__all__ = (
    "MemoryKind",
    "EpistemicType",
    "LearningMemoryMetadata",
    "MemoryTombstone",
    "RetrievedLearningMemory",
    "LearningRetrievalBundle",
    "SkillValidation",
    "LearningSubstrate",
)
