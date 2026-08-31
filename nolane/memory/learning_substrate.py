from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.adaptive_policy import (
    MemoryAnchorHealthReceipt,
    MemoryCompactionReceipt,
    MemoryRetrievalPolicy,
    MemoryRetrievalQuery,
    MemoryRetrievalReceipt,
)
from nolane.memory.experience import ExperienceLedger, ExperienceOutcome, LearningLayer
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
_LAYER_KIND = {
    LearningLayer.EPISODIC: MemoryKind.EPISODIC,
    LearningLayer.SEMANTIC: MemoryKind.SEMANTIC,
    LearningLayer.PROCEDURAL: MemoryKind.PROCEDURAL,
    LearningLayer.STRATEGY: MemoryKind.STRATEGY,
    LearningLayer.TOOL_USE: MemoryKind.PROCEDURAL,
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


def _normalize_family_map(
    evidence_ids: tuple[str, ...],
    families: Mapping[str, str] | None,
    *,
    label: str,
) -> tuple[tuple[str, str], ...]:
    if families is None:
        raise ValueError(f"{label} evidence requires provenance family metadata")
    normalized: dict[str, str] = {}
    for evidence_id, family_id in families.items():
        evidence_key = str(evidence_id).strip()
        family_value = str(family_id).strip()
        if not evidence_key or not family_value:
            raise ValueError(f"{label} evidence family ids must be non-empty")
        normalized[evidence_key] = family_value
    if set(normalized) != set(evidence_ids):
        raise ValueError(f"{label} evidence family mapping must exactly cover evidence ids")
    return tuple(sorted(normalized.items()))


def _clean_refs(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


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
        start, end = _parse_time(self.valid_from), _parse_time(self.valid_until)
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

    def __post_init__(self) -> None:
        if not str(self.memory_id).strip():
            raise ValueError("memory tombstone requires a memory id")
        if not str(self.content_digest).strip():
            raise ValueError("memory tombstone requires a content digest")
        if not str(self.reason).strip():
            raise ValueError("memory tombstone requires a reason")
        if not self.evidence_refs or any(not str(value).strip() for value in self.evidence_refs):
            raise ValueError("memory tombstone requires non-empty evidence")

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
            str(state["memory_id"]),
            str(state["content_digest"]),
            str(state["reason"]),
            tuple(str(x) for x in state.get("evidence_refs", ())),
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
    receipt: MemoryRetrievalReceipt


@dataclass(frozen=True, slots=True)
class SkillValidation:
    skill_id: str
    regression_evidence_ids: tuple[str, ...]
    causal_ablation_evidence_ids: tuple[str, ...]
    regression_evidence_families: tuple[tuple[str, str], ...] = ()
    causal_ablation_evidence_families: tuple[tuple[str, str], ...] = ()

    def to_state(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "regression_evidence_ids": list(self.regression_evidence_ids),
            "causal_ablation_evidence_ids": list(self.causal_ablation_evidence_ids),
            "regression_evidence_families": [list(pair) for pair in self.regression_evidence_families],
            "causal_ablation_evidence_families": [list(pair) for pair in self.causal_ablation_evidence_families],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SkillValidation":
        return cls(
            str(state["skill_id"]),
            tuple(str(x) for x in state.get("regression_evidence_ids", ())),
            tuple(str(x) for x in state.get("causal_ablation_evidence_ids", ())),
            tuple((str(pair[0]), str(pair[1])) for pair in state.get("regression_evidence_families", ())),
            tuple((str(pair[0]), str(pair[1])) for pair in state.get("causal_ablation_evidence_families", ())),
        )


class LearningSubstrate:
    """Evidence-bounded orchestration for External Core B, without a second authority plane."""

    def __init__(
        self,
        *,
        registry,
        events,
        memory: MemoryFabric | None = None,
        lifecycle: MemoryLifecycleLedger | None = None,
        relations: MemoryRelationGraph | None = None,
        skills: SkillEvolutionEngine | None = None,
        experiences: ExperienceLedger | None = None,
    ) -> None:
        self.registry, self.events = registry, events
        self.memory = memory or MemoryFabric()
        self.lifecycle = lifecycle or MemoryLifecycleLedger(registry=registry, memory=self.memory, events=events)
        self.relations = relations or MemoryRelationGraph(registry=registry, memory=self.memory, events=events)
        self.skills = skills or SkillEvolutionEngine()
        self.experiences = experiences or ExperienceLedger(registry=registry, events=events)
        self._metadata: dict[str, LearningMemoryMetadata] = {}
        self._tombstones: dict[str, MemoryTombstone] = {}
        self._skill_validations: dict[str, SkillValidation] = {}
        self._retrieval_policies: dict[str, MemoryRetrievalPolicy] = {}
        self._retrieval_receipts: dict[str, MemoryRetrievalReceipt] = {}
        self._retrieval_snapshots: dict[str, dict[str, Any]] = {}
        self._compactions: dict[str, MemoryCompactionReceipt] = {}
        self._anchor_health: dict[str, list[MemoryAnchorHealthReceipt]] = {}

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
        kind, epistemic_type = MemoryKind(kind), EpistemicType(epistemic_type)
        validated = epistemic_type is EpistemicType.VERIFIED and bool(evidence_ids)
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
            initial_status=MemoryStatus.ACTIVE if validated else MemoryStatus.QUARANTINED,
            status_reason=None if validated else "awaiting_external_validation",
        )
        self._metadata[row.memory_id] = LearningMemoryMetadata(
            row.memory_id,
            kind,
            epistemic_type,
            tuple(sorted({str(x) for x in source_refs})),
            valid_from,
            valid_until,
            version_scope,
            last_verified_ref,
            float(salience),
            failure_condition,
            retry_if_changed,
        )
        return row

    def remember_experience(
        self,
        experience_id: str,
        *,
        failure_condition: str | None = None,
        retry_if_changed: str | None = None,
        salience: float = 0.6,
    ) -> MemoryEntry:
        experience = self.experiences.get(experience_id)
        failed = experience.outcome is ExperienceOutcome.FAILURE
        return self.remember(
            text=experience.summary,
            owner_agent_id=experience.agent_id,
            scope=MemoryScope.PERSONAL,
            kind=MemoryKind.FAILURE if failed else MemoryKind.EPISODIC,
            epistemic_type=EpistemicType.OBSERVATION,
            region=experience.region,
            task_id=experience.task_id,
            tags=(experience.domain, experience.outcome.value),
            evidence_ids=experience.evidence_refs,
            source_refs=(experience.experience_id,) + experience.object_refs,
            salience=salience,
            failure_condition=failure_condition if failed else None,
            retry_if_changed=retry_if_changed if failed else None,
        )

    def consolidate_attribution(self, attribution_id: str) -> MemoryEntry:
        attribution = self.experiences.get_attribution(attribution_id)
        if not attribution.positive:
            raise PermissionError("negative or unverified attribution cannot become verified memory")
        experience = self.experiences.get(attribution.experience_id)
        return self.remember(
            text=attribution.lesson,
            owner_agent_id=experience.agent_id,
            scope=MemoryScope.PERSONAL,
            kind=_LAYER_KIND[attribution.learning_layer],
            epistemic_type=EpistemicType.VERIFIED,
            region=experience.region,
            task_id=experience.task_id,
            tags=(experience.domain, attribution.learning_layer.value),
            evidence_ids=(attribution.evidence.evidence_id,),
            source_refs=(experience.experience_id, attribution.attribution_id),
            last_verified_ref=attribution.evidence.evidence_id,
            salience=0.75,
        )

    def metadata(self, memory_id: str) -> LearningMemoryMetadata:
        self.memory.get(memory_id)
        try:
            return self._metadata[str(memory_id)]
        except KeyError as exc:
            raise KeyError(f"missing learning metadata for {memory_id}") from exc

    def validate_memory(
        self,
        memory_id: str,
        *,
        actor_agent_id: str,
        evidence_refs: tuple[str, ...],
        correction_ref: str,
    ) -> MemoryEntry:
        receipt = self.lifecycle.transition(
            memory_id,
            actor_agent_id=actor_agent_id,
            new_status=MemoryStatus.ACTIVE,
            reason="external_validation_completed",
            evidence_refs=evidence_refs,
            correction_ref=correction_ref,
        )
        metadata = self.metadata(memory_id)
        self._metadata[memory_id] = replace(
            metadata,
            epistemic_type=EpistemicType.VERIFIED,
            last_verified_ref=str(correction_ref),
            source_refs=tuple(sorted(set(metadata.source_refs + receipt.evidence_refs))),
        )
        return self.memory.get(memory_id)

    def decay_memory(
        self,
        memory_id: str,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> MemoryEntry:
        self.lifecycle.transition(
            memory_id,
            actor_agent_id=actor_agent_id,
            new_status=MemoryStatus.STALE,
            reason=reason,
            evidence_refs=evidence_refs,
        )
        return self.memory.get(memory_id)

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
        start, end = _parse_time(metadata.valid_from), _parse_time(metadata.valid_until)
        if start is not None and as_of < start:
            return "not_yet_valid"
        if end is not None and as_of >= end:
            return "expired"
        return None

    @staticmethod
    def _score(row: MemoryEntry, metadata: LearningMemoryMetadata) -> float:
        return (
            _EPISTEMIC_RANK[metadata.epistemic_type] * 100.0
            + row.confidence * 50.0
            + metadata.salience * 20.0
            + (10.0 if row.evidence_ids else 0.0)
            + min(row.sequence, 1_000_000) / 1_000_000.0
        )

    def _latest_anchor_health(self, memory_id: str) -> MemoryAnchorHealthReceipt | None:
        rows = self._anchor_health.get(str(memory_id), ())
        return rows[-1] if rows else None

    def _ordered_anchor_health(self) -> tuple[MemoryAnchorHealthReceipt, ...]:
        return tuple(
            sorted(
                (receipt for receipts in self._anchor_health.values() for receipt in receipts),
                key=lambda receipt: receipt.sequence,
            )
        )

    def _retrieval_state_snapshot(self) -> dict[str, Any]:
        return {
            "memory": self.memory.to_state(),
            "metadata": [self._metadata[key].to_state() for key in sorted(self._metadata)],
            "tombstones": [self._tombstones[key].to_state() for key in sorted(self._tombstones)],
            "relations": self.relations.to_state(),
            "anchor_health": [receipt.to_state() for receipt in self._ordered_anchor_health()],
        }

    def _retrieval_state_digest(self) -> str:
        return canonical_digest(self._retrieval_state_snapshot())

    @staticmethod
    def _validate_retrieval_snapshot_digest(memory_state_digest: str, snapshot: Mapping[str, Any]) -> None:
        if canonical_digest(snapshot) != str(memory_state_digest):
            raise ValueError("retrieval replay snapshot digest mismatch")

    def _replay_retrieval_receipt(self, receipt: MemoryRetrievalReceipt) -> None:
        if not receipt.replayable or receipt.query is None:
            raise ValueError("retrieval receipt replay requires a v2 query envelope")
        try:
            snapshot = self._retrieval_snapshots[receipt.memory_state_digest]
        except KeyError as exc:
            raise ValueError("retrieval receipt replay snapshot is missing") from exc
        self._validate_retrieval_snapshot_digest(receipt.memory_state_digest, snapshot)

        replay_memory = MemoryFabric.from_state(snapshot.get("memory", {}))
        replay_relations = MemoryRelationGraph.from_state(
            registry=self.registry,
            memory=replay_memory,
            events=self.events,
            state=snapshot.get("relations", {}),
        )
        replay = LearningSubstrate(
            registry=self.registry,
            events=self.events,
            memory=replay_memory,
            relations=replay_relations,
        )
        replay_metadata = tuple(
            LearningMemoryMetadata.from_state(raw) for raw in snapshot.get("metadata", ())
        )
        replay._metadata = self._index_unique(
            replay_metadata, key=lambda row: row.memory_id, label="retrieval replay metadata row"
        )
        replay_tombstones = tuple(
            MemoryTombstone.from_state(raw) for raw in snapshot.get("tombstones", ())
        )
        replay._tombstones = self._index_unique(
            replay_tombstones, key=lambda row: row.memory_id, label="retrieval replay tombstone row"
        )
        replay_health = tuple(
            MemoryAnchorHealthReceipt.from_state(raw) for raw in snapshot.get("anchor_health", ())
        )
        self._index_unique(
            replay_health, key=lambda row: row.receipt_id, label="retrieval replay anchor health row"
        )
        expected_health_sequence = list(range(1, len(replay_health) + 1))
        if [row.sequence for row in replay_health] != expected_health_sequence:
            raise ValueError("retrieval replay anchor health sequence invariant violated")
        for metadata in replay._metadata.values():
            replay_memory.get(metadata.memory_id)
            if metadata.source_refs != _clean_refs(metadata.source_refs):
                raise ValueError("retrieval replay metadata source refs are not canonical")
        for memory_id, tombstone in replay._tombstones.items():
            row = replay_memory.get(memory_id)
            expected_digest = canonical_digest({"memory_id": row.memory_id, "text": row.text})
            if tombstone.content_digest != expected_digest:
                raise ValueError("retrieval replay tombstone content digest mismatch")
        for row in replay_health:
            replay._anchor_health.setdefault(row.memory_id, []).append(row)
            replay._validate_anchor_health_receipt_semantics(row)

        replay._retrieval_policies = dict(self._retrieval_policies)
        policy = replay.retrieval_policy(receipt.policy_id)
        query = receipt.query
        replayed = replay.retrieve(
            agent_id=query.agent_id,
            region=query.region,
            as_of=query.as_of,
            task_id=query.task_id,
            tags=query.tags,
            limit=query.limit,
            policy=policy,
        ).receipt
        if replayed != receipt:
            raise ValueError("retrieval receipt replay mismatch")

    def retrieve(
        self,
        *,
        agent_id: str,
        region: str,
        as_of: str,
        task_id: str | None = None,
        tags: tuple[str, ...] = (),
        limit: int = 8,
        policy: MemoryRetrievalPolicy | None = None,
    ) -> LearningRetrievalBundle:
        if limit < 0:
            raise ValueError("learning retrieval limit must be non-negative")
        timestamp = _parse_time(as_of)
        assert timestamp is not None
        retrieval_policy = policy or MemoryRetrievalPolicy()
        if not isinstance(retrieval_policy, MemoryRetrievalPolicy):
            raise TypeError("learning retrieval policy must be MemoryRetrievalPolicy")
        self.register_retrieval_policy(retrieval_policy)

        wanted = {str(x) for x in tags}
        rejected: dict[str, str] = {}
        candidates: list[RetrievedLearningMemory] = []
        estimated_units: dict[str, int] = {}
        visible = self.memory.visible_entries(
            agent_id=agent_id,
            region=region,
            task_id=task_id,
            include_inactive=True,
        )
        for row in visible:
            if row.memory_id in self._tombstones:
                rejected[row.memory_id] = "tombstoned"
                continue
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
            health = self._latest_anchor_health(row.memory_id)
            if health is not None and not health.healthy:
                rejected[row.memory_id] = "anchor_unhealthy"
                continue
            units = retrieval_policy.estimate_units(row.text)
            if retrieval_policy.max_estimated_units is not None and units > retrieval_policy.max_estimated_units:
                rejected[row.memory_id] = "policy_cost_budget"
                continue
            information_score = self._score(row, metadata) + 100.0 * len(wanted.intersection(row.tags))
            estimated_units[row.memory_id] = units
            candidates.append(
                RetrievedLearningMemory(
                    row,
                    metadata,
                    retrieval_policy.score(information_score, estimated_units=units),
                )
            )

        contradictions: dict[str, set[str]] = {}
        for relation in self.relations.relations():
            if relation.kind is MemoryRelationKind.CONTRADICTS:
                contradictions.setdefault(relation.source_memory_id, set()).add(relation.target_memory_id)
                contradictions.setdefault(relation.target_memory_id, set()).add(relation.source_memory_id)

        selected: list[RetrievedLearningMemory] = []
        selected_ids: set[str] = set()
        selected_units = 0
        for candidate in sorted(candidates, key=lambda item: (item.score, item.memory.sequence), reverse=True):
            memory_id = candidate.memory.memory_id
            conflicts = contradictions.get(memory_id, set()).intersection(selected_ids)
            if conflicts:
                rejected[memory_id] = "contradicted_by:" + sorted(conflicts)[0]
                continue
            if len(selected) >= limit:
                rejected[memory_id] = "budget"
                continue
            units = estimated_units[memory_id]
            if (
                retrieval_policy.max_estimated_units is not None
                and selected_units + units > retrieval_policy.max_estimated_units
            ):
                rejected[memory_id] = "policy_cost_budget"
                continue
            selected.append(candidate)
            selected_ids.add(memory_id)
            selected_units += units

        rejected_rows = tuple(sorted(rejected.items()))
        query = MemoryRetrievalQuery(
            agent_id=str(agent_id),
            region=str(region),
            as_of=str(as_of),
            task_id=None if task_id is None else str(task_id),
            tags=tuple(sorted(wanted)),
            limit=int(limit),
        )
        snapshot = self._retrieval_state_snapshot()
        memory_state_digest = canonical_digest(snapshot)
        receipt = MemoryRetrievalReceipt(
            policy_id=retrieval_policy.policy_id,
            query_digest=query.query_digest,
            memory_state_digest=memory_state_digest,
            selected_memory_ids=tuple(item.memory.memory_id for item in selected),
            rejected=rejected_rows,
            estimated_units=selected_units,
            query=query,
        )
        self._retrieval_snapshots.setdefault(memory_state_digest, deepcopy(snapshot))
        self._retrieval_receipts.setdefault(receipt.receipt_id, receipt)
        return LearningRetrievalBundle(tuple(selected), rejected_rows, receipt)

    def register_retrieval_policy(self, policy: MemoryRetrievalPolicy) -> MemoryRetrievalPolicy:
        if not isinstance(policy, MemoryRetrievalPolicy):
            raise TypeError("retrieval policy registration requires MemoryRetrievalPolicy")
        if policy.parent_policy_id is not None and policy.parent_policy_id not in self._retrieval_policies:
            raise ValueError("retrieval policy parent must be registered before its child")
        existing = self._retrieval_policies.get(policy.policy_id)
        if existing is not None and existing != policy:
            raise ValueError("retrieval policy id cannot be rebound")
        self._retrieval_policies[policy.policy_id] = policy
        return policy

    def retrieval_policy(self, policy_id: str) -> MemoryRetrievalPolicy:
        try:
            return self._retrieval_policies[str(policy_id)]
        except KeyError as exc:
            raise KeyError(f"unknown memory retrieval policy: {policy_id}") from exc

    def retrieval_receipt(self, receipt_id: str) -> MemoryRetrievalReceipt:
        try:
            return self._retrieval_receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown memory retrieval receipt: {receipt_id}") from exc

    @staticmethod
    def _source_projection(row: MemoryEntry, metadata: LearningMemoryMetadata) -> dict[str, Any]:
        # Lifecycle state is deliberately excluded. Compaction binds source content
        # and epistemic metadata while allowing later stale/archive transitions.
        return {
            "memory_id": row.memory_id,
            "sequence": row.sequence,
            "scope": row.scope.value,
            "text": row.text,
            "owner_agent_id": row.owner_agent_id,
            "region": row.region,
            "task_id": row.task_id,
            "tags": list(row.tags),
            "parent_memory_id": row.parent_memory_id,
            "promotion_receipt_id": row.promotion_receipt_id,
            "evidence_ids": list(row.evidence_ids),
            "confidence": row.confidence,
            "dependencies": list(row.dependencies),
            "supersedes": row.supersedes,
            "metadata": metadata.to_state(),
        }

    def _compaction_source_digest(self, source_memory_ids: tuple[str, ...]) -> str:
        return canonical_digest(
            [
                self._source_projection(self.memory.get(memory_id), self.metadata(memory_id))
                for memory_id in source_memory_ids
            ]
        )

    @staticmethod
    def _intersection_bound(
        metadata_rows: tuple[LearningMemoryMetadata, ...],
        *,
        field: str,
        choose_max: bool,
    ) -> str | None:
        values = [(getattr(row, field), _parse_time(getattr(row, field))) for row in metadata_rows]
        present = [(raw, parsed) for raw, parsed in values if parsed is not None]
        if not present:
            return None
        raw, _ = (max if choose_max else min)(present, key=lambda pair: pair[1])
        return raw

    def compact(
        self,
        *,
        source_memory_ids: tuple[str, ...],
        summary_text: str,
        owner_agent_id: str,
        scope: MemoryScope,
        kind: MemoryKind,
        actor_agent_id: str,
        evidence_refs: tuple[str, ...],
    ) -> tuple[MemoryEntry, MemoryCompactionReceipt]:
        source_ids = tuple(sorted({str(value).strip() for value in source_memory_ids if str(value).strip()}))
        if len(source_ids) < 2:
            raise ValueError("memory compaction requires at least two source memories")
        evidence = _clean_refs(evidence_refs)
        if not evidence:
            raise ValueError("memory compaction requires external evidence")
        owner = str(owner_agent_id).strip()
        actor = str(actor_agent_id).strip()
        if not owner or not actor:
            raise ValueError("memory compaction requires explicit owner and actor")
        self.registry.get(actor)
        if actor == owner:
            raise PermissionError("memory compaction requires external review; owner cannot self-certify")

        rows = tuple(self.memory.get(memory_id) for memory_id in source_ids)
        metadata_rows = tuple(self.metadata(memory_id) for memory_id in source_ids)
        epistemic_types = {row.epistemic_type for row in metadata_rows}
        if len(epistemic_types) != 1:
            raise ValueError("memory compaction cannot mix epistemic type classes")
        if any(row.status is not MemoryStatus.ACTIVE for row in rows):
            raise ValueError("memory compaction only accepts active source memories")
        source_kinds = {row.kind for row in metadata_rows}
        if len(source_kinds) != 1 or MemoryKind(kind) not in source_kinds:
            raise ValueError("memory compaction must preserve memory kind")
        target_scope = MemoryScope(scope)
        if any(row.owner_agent_id != owner for row in rows):
            raise ValueError("memory compaction cannot cross memory owners")
        if any(row.scope is not target_scope for row in rows):
            raise ValueError("memory compaction cannot weaken or change memory scope")
        regions = {row.region for row in rows}
        tasks = {row.task_id for row in rows}
        if len(regions) != 1 or len(tasks) != 1:
            raise ValueError("memory compaction requires uniform region/task bindings")
        version_scopes = {row.version_scope for row in metadata_rows}
        if len(version_scopes) != 1:
            raise ValueError("memory compaction cannot mix version scopes")

        valid_from = self._intersection_bound(metadata_rows, field="valid_from", choose_max=True)
        valid_until = self._intersection_bound(metadata_rows, field="valid_until", choose_max=False)
        start, end = _parse_time(valid_from), _parse_time(valid_until)
        if start is not None and end is not None and end <= start:
            raise ValueError("memory compaction source validity windows do not overlap")

        epistemic_type = next(iter(epistemic_types))
        combined_evidence = _clean_refs(
            evidence + tuple(value for row in rows for value in row.evidence_ids)
        )
        combined_sources = _clean_refs(
            source_ids + tuple(value for metadata in metadata_rows for value in metadata.source_refs)
        )
        combined_tags = _clean_refs(tuple(value for row in rows for value in row.tags) + ("compacted",))
        combined_dependencies = _clean_refs(source_ids + tuple(value for row in rows for value in row.dependencies))
        compacted = self.remember(
            text=summary_text,
            owner_agent_id=owner,
            scope=target_scope,
            kind=MemoryKind(kind),
            epistemic_type=epistemic_type,
            region=rows[0].region,
            task_id=rows[0].task_id,
            tags=combined_tags,
            evidence_ids=combined_evidence,
            confidence=min(row.confidence for row in rows),
            dependencies=combined_dependencies,
            source_refs=combined_sources,
            valid_from=valid_from,
            valid_until=valid_until,
            version_scope=metadata_rows[0].version_scope,
            last_verified_ref=evidence[0] if epistemic_type is EpistemicType.VERIFIED else None,
            salience=max(row.salience for row in metadata_rows),
        )
        receipt = MemoryCompactionReceipt(
            source_memory_ids=source_ids,
            compacted_memory_id=compacted.memory_id,
            source_digest=self._compaction_source_digest(source_ids),
            epistemic_type=epistemic_type.value,
            actor_agent_id=actor,
            evidence_refs=evidence,
        )
        self._compactions[receipt.compaction_id] = receipt
        return compacted, receipt

    def compaction_receipt(self, compaction_id: str) -> MemoryCompactionReceipt:
        try:
            return self._compactions[str(compaction_id)]
        except KeyError as exc:
            raise KeyError(f"unknown memory compaction receipt: {compaction_id}") from exc

    def reconstruct_compaction(self, compaction_id: str) -> tuple[MemoryEntry, ...]:
        receipt = self.compaction_receipt(compaction_id)
        rows = tuple(self.memory.get(memory_id) for memory_id in receipt.source_memory_ids)
        actual = self._compaction_source_digest(receipt.source_memory_ids)
        if actual != receipt.source_digest:
            raise ValueError("memory compaction source digest mismatch")
        return rows

    def record_anchor_health(
        self,
        memory_id: str,
        *,
        actor_agent_id: str,
        healthy: bool,
        evidence_ref: str,
        observed_version_scope: str | None,
        reason: str,
    ) -> MemoryAnchorHealthReceipt:
        row = self.memory.get(memory_id)
        metadata = self.metadata(memory_id)
        actor = str(actor_agent_id).strip()
        evidence = str(evidence_ref).strip()
        normalized_reason = str(reason).strip()
        observed = None if observed_version_scope is None else str(observed_version_scope).strip()
        if not actor or not evidence or not normalized_reason:
            raise ValueError("anchor health requires actor, evidence, and reason")
        if observed_version_scope is not None and not observed:
            raise ValueError("observed version scope must be non-empty when present")
        self.registry.get(actor)
        if actor == row.owner_agent_id:
            raise PermissionError("anchor health requires external observation; owner cannot self-certify")
        if bool(healthy) and metadata.version_scope is not None and observed != metadata.version_scope:
            raise ValueError("healthy anchor observation cannot contradict its bound version scope")
        sequence = 1 + sum(len(receipts) for receipts in self._anchor_health.values())
        receipt = MemoryAnchorHealthReceipt(
            sequence=sequence,
            memory_id=row.memory_id,
            actor_agent_id=actor,
            healthy=bool(healthy),
            evidence_ref=evidence,
            observed_version_scope=observed,
            reason=normalized_reason,
        )
        self._anchor_health.setdefault(row.memory_id, []).append(receipt)
        return receipt

    def anchor_health(self, memory_id: str) -> tuple[MemoryAnchorHealthReceipt, ...]:
        self.memory.get(memory_id)
        return tuple(self._anchor_health.get(str(memory_id), ()))

    def forget(
        self,
        memory_id: str,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> MemoryTombstone:
        row, reason = self.memory.get(memory_id), str(reason).strip()
        actor = self.registry.get(str(actor_agent_id).strip())
        if actor.region != self.lifecycle.REGION:
            raise PermissionError("forgetting memory requires a Memory/Context identity")
        evidence = _clean_refs(evidence_refs)
        if not reason:
            raise ValueError("forgetting requires an explicit reason")
        if not evidence:
            raise ValueError("forgetting requires evidence")
        candidate = MemoryTombstone(
            row.memory_id,
            canonical_digest({"memory_id": row.memory_id, "text": row.text}),
            reason,
            evidence,
        )
        existing = self._tombstones.get(row.memory_id)
        if existing is not None:
            if existing != candidate:
                raise ValueError("memory tombstone cannot be rebound")
            return existing
        if row.status is not MemoryStatus.ARCHIVED:
            self.lifecycle.transition(
                row.memory_id,
                actor_agent_id=actor_agent_id,
                new_status=MemoryStatus.ARCHIVED,
                reason=reason,
                evidence_refs=evidence,
            )
        else:
            archive_authority = tuple(
                receipt
                for receipt in self.lifecycle.receipts_for(row.memory_id)
                if receipt.new_status is MemoryStatus.ARCHIVED
                and receipt.actor_agent_id == str(actor_agent_id).strip()
                and receipt.reason == reason
                and receipt.evidence_refs == evidence
            )
            if not archive_authority:
                raise ValueError(
                    "forgetting already archived memory requires matching archive lifecycle authority"
                )
        self._tombstones[row.memory_id] = candidate
        return candidate

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
        regression_evidence_families: Mapping[str, str] | None = None,
        causal_ablation_evidence_families: Mapping[str, str] | None = None,
    ) -> SkillValidation:
        self.skills.get(skill_id)
        regressions = tuple(sorted({str(x).strip() for x in regression_evidence_ids if str(x).strip()}))
        causal = tuple(sorted({str(x).strip() for x in causal_ablation_evidence_ids if str(x).strip()}))
        if not regressions:
            raise ValueError("skill validation requires executed regression evidence")
        if not causal:
            raise ValueError("skill validation requires causal ablation evidence")
        regression_families = _normalize_family_map(
            regressions,
            regression_evidence_families,
            label="regression",
        )
        causal_families = _normalize_family_map(
            causal,
            causal_ablation_evidence_families,
            label="causal ablation",
        )
        regression_family_ids = {family_id for _, family_id in regression_families}
        causal_family_ids = {family_id for _, family_id in causal_families}
        if len(regression_family_ids) < 2:
            raise ValueError("skill validation requires independent regression evidence families")
        if regression_family_ids.intersection(causal_family_ids):
            raise ValueError("causal ablation evidence families must be independent of regression families")
        row = SkillValidation(
            str(skill_id),
            regressions,
            causal,
            regression_families,
            causal_families,
        )
        self._validate_skill_validation_semantics(row)
        self._skill_validations[row.skill_id] = row
        return row

    @staticmethod
    def _validate_skill_validation_semantics(validation: SkillValidation) -> None:
        regressions = _clean_refs(validation.regression_evidence_ids)
        causal = _clean_refs(validation.causal_ablation_evidence_ids)
        if not regressions:
            raise ValueError("skill validation requires executed regression evidence")
        if not causal:
            raise ValueError("skill validation requires causal ablation evidence")
        if regressions != validation.regression_evidence_ids:
            raise ValueError("skill validation regression evidence ids are not canonical")
        if causal != validation.causal_ablation_evidence_ids:
            raise ValueError("skill validation causal evidence ids are not canonical")

        regression_pairs = validation.regression_evidence_families
        causal_pairs = validation.causal_ablation_evidence_families
        if len(dict(regression_pairs)) != len(regression_pairs):
            raise ValueError("skill validation regression evidence family mapping contains duplicate ids")
        if len(dict(causal_pairs)) != len(causal_pairs):
            raise ValueError("skill validation causal evidence family mapping contains duplicate ids")
        regression_families = _normalize_family_map(
            regressions, dict(regression_pairs), label="regression"
        )
        causal_families = _normalize_family_map(
            causal, dict(causal_pairs), label="causal ablation"
        )
        if regression_families != regression_pairs or causal_families != causal_pairs:
            raise ValueError("skill validation evidence family mapping is not canonical")
        regression_family_ids = {family_id for _, family_id in regression_families}
        causal_family_ids = {family_id for _, family_id in causal_families}
        if len(regression_family_ids) < 2:
            raise ValueError("skill validation requires independent regression evidence families")
        if not causal_family_ids:
            raise ValueError("skill validation requires causal ablation evidence families")
        if regression_family_ids.intersection(causal_family_ids):
            raise ValueError("causal ablation evidence families must be independent of regression families")

    @staticmethod
    def _require_independent_skill_validation(validation: SkillValidation) -> None:
        regression_family_ids = {family_id for _, family_id in validation.regression_evidence_families}
        causal_family_ids = {family_id for _, family_id in validation.causal_ablation_evidence_families}
        if len(regression_family_ids) < 2:
            raise PermissionError("persistent skill promotion requires independent regression evidence families")
        if not causal_family_ids:
            raise PermissionError("persistent skill promotion requires causal ablation evidence families")
        if regression_family_ids.intersection(causal_family_ids):
            raise PermissionError(
                "persistent skill promotion requires causal evidence independent of regression families"
            )

    def promote_skill(self, skill_id: str, scope: SkillScope) -> SkillRecord:
        validation = self._skill_validations.get(str(skill_id))
        if validation is None or not validation.regression_evidence_ids:
            raise PermissionError("persistent skill promotion requires executed regression evidence")
        if not validation.causal_ablation_evidence_ids:
            raise PermissionError("persistent skill promotion requires causal ablation evidence")
        self._require_independent_skill_validation(validation)
        return self.skills.promote(skill_id, scope)

    @staticmethod
    def _index_unique(rows, *, key, label: str):
        indexed = {}
        for row in rows:
            identity = key(row)
            if identity in indexed:
                raise ValueError(f"duplicate {label}: {identity}")
            indexed[identity] = row
        return indexed

    def _validate_policy_lineage(self) -> None:
        for policy in self._retrieval_policies.values():
            parent_id = policy.parent_policy_id
            if parent_id is not None and parent_id not in self._retrieval_policies:
                raise ValueError(f"retrieval policy parent is missing: {parent_id}")
        for policy_id in self._retrieval_policies:
            seen: set[str] = set()
            current = policy_id
            while current is not None:
                if current in seen:
                    raise ValueError("retrieval policy parent lineage contains a cycle")
                seen.add(current)
                current = self._retrieval_policies[current].parent_policy_id

    def _validate_compaction_receipt_semantics(self, receipt: MemoryCompactionReceipt) -> None:
        self.registry.get(receipt.actor_agent_id)
        compacted = self.memory.get(receipt.compacted_memory_id)
        compacted_metadata = self.metadata(compacted.memory_id)
        source_rows = tuple(self.memory.get(memory_id) for memory_id in receipt.source_memory_ids)
        source_metadata = tuple(self.metadata(memory_id) for memory_id in receipt.source_memory_ids)
        owners = {row.owner_agent_id for row in source_rows}
        if len(owners) != 1 or compacted.owner_agent_id not in owners:
            raise ValueError("memory compaction restore cannot cross memory owners")
        owner = next(iter(owners))
        if receipt.actor_agent_id == owner:
            raise PermissionError("memory compaction restore requires external review; owner cannot self-certify")
        scopes = {row.scope for row in source_rows}
        if len(scopes) != 1 or compacted.scope not in scopes:
            raise ValueError("memory compaction restore cannot change memory scope")
        kinds = {row.kind for row in source_metadata}
        if len(kinds) != 1 or compacted_metadata.kind not in kinds:
            raise ValueError("memory compaction restore must preserve memory kind")
        epistemic_types = {row.epistemic_type for row in source_metadata}
        if len(epistemic_types) != 1:
            raise ValueError("memory compaction restore cannot mix epistemic type classes")
        epistemic_type = next(iter(epistemic_types))
        if receipt.epistemic_type != epistemic_type.value or compacted_metadata.epistemic_type is not epistemic_type:
            raise ValueError("memory compaction restore epistemic type mismatch")
        regions = {row.region for row in source_rows}
        tasks = {row.task_id for row in source_rows}
        if len(regions) != 1 or compacted.region not in regions or len(tasks) != 1 or compacted.task_id not in tasks:
            raise ValueError("memory compaction restore region/task binding mismatch")
        versions = {row.version_scope for row in source_metadata}
        if len(versions) != 1 or compacted_metadata.version_scope not in versions:
            raise ValueError("memory compaction restore version scope mismatch")
        if not set(receipt.source_memory_ids).issubset(compacted.dependencies):
            raise ValueError("memory compaction restore lost source dependency bindings")
        if not set(receipt.source_memory_ids).issubset(compacted_metadata.source_refs):
            raise ValueError("memory compaction restore lost source provenance bindings")
        if not set(receipt.evidence_refs).issubset(compacted.evidence_ids):
            raise ValueError("memory compaction restore lost review evidence")
        self.reconstruct_compaction(receipt.compaction_id)

    def _validate_anchor_health_receipt_semantics(self, receipt: MemoryAnchorHealthReceipt) -> None:
        row = self.memory.get(receipt.memory_id)
        metadata = self.metadata(receipt.memory_id)
        self.registry.get(receipt.actor_agent_id)
        if receipt.actor_agent_id == row.owner_agent_id:
            raise PermissionError("anchor health restore requires external observation; owner cannot self-certify")
        if receipt.healthy and metadata.version_scope is not None and receipt.observed_version_scope != metadata.version_scope:
            raise ValueError("healthy anchor restore cannot contradict its bound version scope")

    def _validate_learning_metadata_semantics(self, metadata: LearningMemoryMetadata) -> None:
        row = self.memory.get(metadata.memory_id)
        if metadata.source_refs != _clean_refs(metadata.source_refs):
            raise ValueError("learning metadata source refs are not canonical")
        if row.status is not MemoryStatus.ACTIVE:
            return
        if metadata.epistemic_type is not EpistemicType.VERIFIED:
            raise ValueError("active learning memory requires verified epistemic metadata")
        if row.evidence_ids:
            return
        lifecycle_rows = self.lifecycle.receipts_for(row.memory_id)
        activation = lifecycle_rows[-1] if lifecycle_rows else None
        if (
            activation is None
            or activation.new_status is not MemoryStatus.ACTIVE
            or not activation.evidence_refs
            or not str(activation.correction_ref or "").strip()
        ):
            raise ValueError("active learning memory requires verification proof")

    def _validate_tombstone_semantics(self, tombstone: MemoryTombstone) -> None:
        row = self.memory.get(tombstone.memory_id)
        if row.status is not MemoryStatus.ARCHIVED:
            raise ValueError("memory tombstone requires archived memory state")
        archive_authority = tuple(
            receipt
            for receipt in self.lifecycle.receipts_for(tombstone.memory_id)
            if receipt.new_status is MemoryStatus.ARCHIVED
            and receipt.reason == tombstone.reason
            and receipt.evidence_refs == tombstone.evidence_refs
        )
        if not archive_authority:
            raise ValueError("memory tombstone requires matching archive lifecycle authority")

    def to_state(self) -> dict[str, Any]:
        return {
            "memory": self.memory.to_state(),
            "lifecycle": self.lifecycle.to_state(),
            "relations": self.relations.to_state(),
            "skills": self.skills.to_state(),
            "experiences": self.experiences.to_state(),
            "metadata": [self._metadata[key].to_state() for key in sorted(self._metadata)],
            "tombstones": [self._tombstones[key].to_state() for key in sorted(self._tombstones)],
            "skill_validations": [
                self._skill_validations[key].to_state() for key in sorted(self._skill_validations)
            ],
            "retrieval_policies": [
                self._retrieval_policies[key].to_state() for key in sorted(self._retrieval_policies)
            ],
            "retrieval_receipts": [
                self._retrieval_receipts[key].to_state() for key in sorted(self._retrieval_receipts)
            ],
            "retrieval_snapshots": [
                {
                    "memory_state_digest": key,
                    "state": deepcopy(self._retrieval_snapshots[key]),
                }
                for key in sorted(self._retrieval_snapshots)
            ],
            "compactions": [self._compactions[key].to_state() for key in sorted(self._compactions)],
            "anchor_health": [receipt.to_state() for receipt in self._ordered_anchor_health()],
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
            experiences=ExperienceLedger.from_state(
                registry=registry,
                events=events,
                state=state.get("experiences", {}),
            ),
        )
        metadata_rows = tuple(LearningMemoryMetadata.from_state(raw) for raw in state.get("metadata", ()))
        result._metadata = cls._index_unique(
            metadata_rows, key=lambda row: row.memory_id, label="learning metadata row"
        )
        tombstones = tuple(MemoryTombstone.from_state(raw) for raw in state.get("tombstones", ()))
        result._tombstones = cls._index_unique(
            tombstones, key=lambda row: row.memory_id, label="memory tombstone row"
        )
        skill_validations = tuple(SkillValidation.from_state(raw) for raw in state.get("skill_validations", ()))
        result._skill_validations = cls._index_unique(
            skill_validations, key=lambda row: row.skill_id, label="skill validation row"
        )
        retrieval_policies = tuple(
            MemoryRetrievalPolicy.from_state(raw) for raw in state.get("retrieval_policies", ())
        )
        result._retrieval_policies = cls._index_unique(
            retrieval_policies, key=lambda row: row.policy_id, label="retrieval policy row"
        )
        result._validate_policy_lineage()
        retrieval_receipts = tuple(
            MemoryRetrievalReceipt.from_state(raw) for raw in state.get("retrieval_receipts", ())
        )
        result._retrieval_receipts = cls._index_unique(
            retrieval_receipts, key=lambda row: row.receipt_id, label="retrieval receipt row"
        )
        retrieval_snapshots: dict[str, dict[str, Any]] = {}
        for raw in state.get("retrieval_snapshots", ()):
            memory_state_digest = str(raw["memory_state_digest"])
            snapshot = raw.get("state")
            if not isinstance(snapshot, Mapping):
                raise ValueError("retrieval replay snapshot state must be a mapping")
            cls._validate_retrieval_snapshot_digest(memory_state_digest, snapshot)
            if memory_state_digest in retrieval_snapshots:
                raise ValueError("duplicate retrieval replay snapshot digest")
            retrieval_snapshots[memory_state_digest] = deepcopy(dict(snapshot))
        result._retrieval_snapshots = retrieval_snapshots
        compactions = tuple(MemoryCompactionReceipt.from_state(raw) for raw in state.get("compactions", ()))
        result._compactions = cls._index_unique(
            compactions, key=lambda row: row.compaction_id, label="compaction receipt row"
        )
        anchor_health = tuple(
            MemoryAnchorHealthReceipt.from_state(raw) for raw in state.get("anchor_health", ())
        )
        cls._index_unique(anchor_health, key=lambda row: row.receipt_id, label="anchor health receipt row")
        expected_health_sequence = list(range(1, len(anchor_health) + 1))
        actual_health_sequence = [row.sequence for row in anchor_health]
        if actual_health_sequence != expected_health_sequence:
            raise ValueError("anchor health sequence invariant violated")
        for row in anchor_health:
            result._anchor_health.setdefault(row.memory_id, []).append(row)

        for metadata in result._metadata.values():
            result._validate_learning_metadata_semantics(metadata)
        for memory_id, tombstone in result._tombstones.items():
            row = memory.get(memory_id)
            expected_digest = canonical_digest({"memory_id": row.memory_id, "text": row.text})
            if tombstone.content_digest != expected_digest:
                raise ValueError("memory tombstone content digest mismatch")
            result._validate_tombstone_semantics(tombstone)
        for skill_id, validation in result._skill_validations.items():
            result.skills.get(skill_id)
            result._validate_skill_validation_semantics(validation)
        for raw_skill in result.skills.to_state().get("skills", ()):
            if (
                SkillScope(str(raw_skill.get("scope", SkillScope.CANDIDATE.value)))
                is not SkillScope.CANDIDATE
                and str(raw_skill["skill_id"]) not in result._skill_validations
            ):
                raise PermissionError("restored persistent skill requires governed learning validation")
        for receipt in retrieval_receipts:
            if receipt.policy_id not in result._retrieval_policies:
                raise ValueError("retrieval receipt references unknown policy")
            for memory_id in receipt.selected_memory_ids:
                memory.get(memory_id)
            for memory_id, _ in receipt.rejected:
                memory.get(memory_id)
            result._replay_retrieval_receipt(receipt)
        for receipt in compactions:
            result._validate_compaction_receipt_semantics(receipt)
        for receipt in anchor_health:
            result._validate_anchor_health_receipt_semantics(receipt)
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
