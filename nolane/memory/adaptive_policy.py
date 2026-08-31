from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


_POLICY_SCHEMA = "nolane-memory-retrieval-policy-v1"
_RETRIEVAL_RECEIPT_SCHEMA_V1 = "nolane-memory-retrieval-receipt-v1"
_RETRIEVAL_RECEIPT_SCHEMA_V2 = "nolane-memory-retrieval-receipt-v2"
_COMPACTION_RECEIPT_SCHEMA = "nolane-memory-compaction-receipt-v1"
_ANCHOR_HEALTH_RECEIPT_SCHEMA = "nolane-memory-anchor-health-receipt-v1"


def _require_nonempty(value: str, *, label: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{label} must be non-empty")
    return normalized


def _require_weight(value: float, *, label: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return normalized


def _require_content_address(
    state: Mapping[str, Any],
    *,
    key: str,
    expected: str,
    label: str,
) -> None:
    supplied = state.get(key)
    if supplied is None or not str(supplied).strip():
        raise ValueError(f"{label} requires persisted {key}")
    if str(supplied) != expected:
        raise ValueError(f"{label} content-address mismatch")


@dataclass(frozen=True, slots=True)
class MemoryRetrievalPolicy:
    """Deterministic, content-addressed retrieval policy for External Core B.

    The policy can change ranking/cost pressure, but it cannot relax visibility,
    lifecycle, epistemic, contradiction, or anchor-health gates owned elsewhere.
    """

    information_weight: float = 1.0
    cost_weight: float = 0.0
    max_estimated_units: int | None = None
    parent_policy_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "information_weight", _require_weight(self.information_weight, label="information_weight"))
        object.__setattr__(self, "cost_weight", _require_weight(self.cost_weight, label="cost_weight"))
        if self.max_estimated_units is not None:
            budget = int(self.max_estimated_units)
            if budget <= 0:
                raise ValueError("max_estimated_units must be positive when present")
            object.__setattr__(self, "max_estimated_units", budget)
        if self.parent_policy_id is not None:
            object.__setattr__(self, "parent_policy_id", _require_nonempty(self.parent_policy_id, label="parent_policy_id"))

    @property
    def policy_id(self) -> str:
        return "mrp-" + canonical_digest(self._identity_state())[:24]

    def _identity_state(self) -> dict[str, Any]:
        return {
            "schema": _POLICY_SCHEMA,
            "information_weight": self.information_weight,
            "cost_weight": self.cost_weight,
            "max_estimated_units": self.max_estimated_units,
            "parent_policy_id": self.parent_policy_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, **self._identity_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryRetrievalPolicy":
        if str(state.get("schema", _POLICY_SCHEMA)) != _POLICY_SCHEMA:
            raise ValueError("unsupported memory retrieval policy schema")
        result = cls(
            information_weight=float(state.get("information_weight", 1.0)),
            cost_weight=float(state.get("cost_weight", 0.0)),
            max_estimated_units=None if state.get("max_estimated_units") is None else int(state["max_estimated_units"]),
            parent_policy_id=None if state.get("parent_policy_id") is None else str(state["parent_policy_id"]),
        )
        _require_content_address(
            state,
            key="policy_id",
            expected=result.policy_id,
            label="memory retrieval policy",
        )
        return result

    def migrate(self, **overrides: Any) -> "MemoryRetrievalPolicy":
        allowed = {"information_weight", "cost_weight", "max_estimated_units"}
        unknown = set(overrides).difference(allowed)
        if unknown:
            raise TypeError("unsupported retrieval policy override(s): " + ", ".join(sorted(unknown)))
        return replace(self, parent_policy_id=self.policy_id, **overrides)

    @staticmethod
    def estimate_units(text: str) -> int:
        # A deterministic coarse cost unit. It deliberately avoids tokenizer/model
        # coupling so receipts replay identically across Python/model versions.
        byte_count = len(str(text).encode("utf-8"))
        return max(1, (byte_count + 63) // 64)

    def score(self, information_score: float, *, estimated_units: int) -> float:
        units = int(estimated_units)
        if units <= 0:
            raise ValueError("estimated_units must be positive")
        return self.information_weight * float(information_score) - self.cost_weight * units


@dataclass(frozen=True, slots=True)
class MemoryRetrievalQuery:
    agent_id: str
    region: str
    as_of: str
    task_id: str | None = None
    tags: tuple[str, ...] = ()
    limit: int = 8

    def __post_init__(self) -> None:
        object.__setattr__(self, "agent_id", _require_nonempty(self.agent_id, label="retrieval query agent_id"))
        object.__setattr__(self, "region", _require_nonempty(self.region, label="retrieval query region"))
        object.__setattr__(self, "as_of", _require_nonempty(self.as_of, label="retrieval query as_of"))
        if self.task_id is not None:
            object.__setattr__(self, "task_id", _require_nonempty(self.task_id, label="retrieval query task_id"))
        normalized_tags = tuple(sorted({str(value) for value in self.tags}))
        object.__setattr__(self, "tags", normalized_tags)
        normalized_limit = int(self.limit)
        if normalized_limit < 0:
            raise ValueError("retrieval query limit must be non-negative")
        object.__setattr__(self, "limit", normalized_limit)

    @property
    def query_digest(self) -> str:
        return canonical_digest(self.to_state())

    def to_state(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "region": self.region,
            "as_of": self.as_of,
            "task_id": self.task_id,
            "tags": list(self.tags),
            "limit": int(self.limit),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryRetrievalQuery":
        return cls(
            agent_id=str(state["agent_id"]),
            region=str(state["region"]),
            as_of=str(state["as_of"]),
            task_id=None if state.get("task_id") is None else str(state["task_id"]),
            tags=tuple(str(value) for value in state.get("tags", ())),
            limit=int(state.get("limit", 8)),
        )


@dataclass(frozen=True, slots=True)
class MemoryRetrievalReceipt:
    policy_id: str
    query_digest: str
    memory_state_digest: str
    selected_memory_ids: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    estimated_units: int
    query: MemoryRetrievalQuery | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("policy_id", self.policy_id),
            ("query_digest", self.query_digest),
            ("memory_state_digest", self.memory_state_digest),
        ):
            _require_nonempty(value, label=label)
        if int(self.estimated_units) < 0:
            raise ValueError("estimated_units must be non-negative")
        if self.query is not None:
            if not isinstance(self.query, MemoryRetrievalQuery):
                raise TypeError("memory retrieval receipt query must be MemoryRetrievalQuery")
            if self.query_digest != self.query.query_digest:
                raise ValueError("memory retrieval receipt query digest mismatch")

    @property
    def schema(self) -> str:
        return _RETRIEVAL_RECEIPT_SCHEMA_V2 if self.query is not None else _RETRIEVAL_RECEIPT_SCHEMA_V1

    @property
    def replayable(self) -> bool:
        return self.query is not None

    @property
    def receipt_id(self) -> str:
        return "mrr-" + canonical_digest(self._identity_state())[:24]

    def _identity_state(self) -> dict[str, Any]:
        state = {
            "schema": self.schema,
            "policy_id": self.policy_id,
            "query_digest": self.query_digest,
            "memory_state_digest": self.memory_state_digest,
            "selected_memory_ids": list(self.selected_memory_ids),
            "rejected": [list(pair) for pair in self.rejected],
            "estimated_units": int(self.estimated_units),
        }
        if self.query is not None:
            state["query"] = self.query.to_state()
        return state

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self._identity_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryRetrievalReceipt":
        schema = str(state.get("schema", _RETRIEVAL_RECEIPT_SCHEMA_V1))
        if schema not in {_RETRIEVAL_RECEIPT_SCHEMA_V1, _RETRIEVAL_RECEIPT_SCHEMA_V2}:
            raise ValueError("unsupported memory retrieval receipt schema")
        query = None
        if schema == _RETRIEVAL_RECEIPT_SCHEMA_V2:
            raw_query = state.get("query")
            if not isinstance(raw_query, Mapping):
                raise ValueError("memory retrieval receipt v2 requires replay query envelope")
            query = MemoryRetrievalQuery.from_state(raw_query)
        result = cls(
            policy_id=str(state["policy_id"]),
            query_digest=str(state["query_digest"]),
            memory_state_digest=str(state["memory_state_digest"]),
            selected_memory_ids=tuple(str(value) for value in state.get("selected_memory_ids", ())),
            rejected=tuple((str(pair[0]), str(pair[1])) for pair in state.get("rejected", ())),
            estimated_units=int(state.get("estimated_units", 0)),
            query=query,
        )
        if result.schema != schema:
            raise ValueError("memory retrieval receipt schema/query envelope mismatch")
        selected = result.selected_memory_ids
        if any(not str(memory_id).strip() for memory_id in selected):
            raise ValueError("memory retrieval receipt selected ids must be non-empty")
        if len(set(selected)) != len(selected):
            raise ValueError("memory retrieval receipt selected ids must be unique")
        rejected_ids = tuple(memory_id for memory_id, _ in result.rejected)
        if any(not str(memory_id).strip() or not str(reason).strip() for memory_id, reason in result.rejected):
            raise ValueError("memory retrieval receipt rejection ids/reasons must be non-empty")
        if len(set(rejected_ids)) != len(rejected_ids):
            raise ValueError("memory retrieval receipt rejected ids must be unique")
        if set(selected).intersection(rejected_ids):
            raise ValueError("memory retrieval receipt selected/rejected overlap")
        _require_content_address(
            state,
            key="receipt_id",
            expected=result.receipt_id,
            label="memory retrieval receipt",
        )
        return result


@dataclass(frozen=True, slots=True)
class MemoryCompactionReceipt:
    source_memory_ids: tuple[str, ...]
    compacted_memory_id: str
    source_digest: str
    epistemic_type: str
    actor_agent_id: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.source_memory_ids) < 2:
            raise ValueError("memory compaction requires at least two sources")
        if tuple(sorted(set(self.source_memory_ids))) != self.source_memory_ids:
            raise ValueError("compaction source ids must be unique and sorted")
        for label, value in (
            ("compacted_memory_id", self.compacted_memory_id),
            ("source_digest", self.source_digest),
            ("epistemic_type", self.epistemic_type),
            ("actor_agent_id", self.actor_agent_id),
        ):
            _require_nonempty(value, label=label)
        if not self.evidence_refs:
            raise ValueError("memory compaction receipt requires evidence")

    @property
    def compaction_id(self) -> str:
        return "mcr-" + canonical_digest(self._identity_state())[:24]

    def _identity_state(self) -> dict[str, Any]:
        return {
            "schema": _COMPACTION_RECEIPT_SCHEMA,
            "source_memory_ids": list(self.source_memory_ids),
            "compacted_memory_id": self.compacted_memory_id,
            "source_digest": self.source_digest,
            "epistemic_type": self.epistemic_type,
            "actor_agent_id": self.actor_agent_id,
            "evidence_refs": list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {"compaction_id": self.compaction_id, **self._identity_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryCompactionReceipt":
        if str(state.get("schema", _COMPACTION_RECEIPT_SCHEMA)) != _COMPACTION_RECEIPT_SCHEMA:
            raise ValueError("unsupported memory compaction receipt schema")
        result = cls(
            source_memory_ids=tuple(str(value) for value in state.get("source_memory_ids", ())),
            compacted_memory_id=str(state["compacted_memory_id"]),
            source_digest=str(state["source_digest"]),
            epistemic_type=str(state["epistemic_type"]),
            actor_agent_id=str(state["actor_agent_id"]),
            evidence_refs=tuple(str(value) for value in state.get("evidence_refs", ())),
        )
        _require_content_address(
            state,
            key="compaction_id",
            expected=result.compaction_id,
            label="memory compaction receipt",
        )
        return result


@dataclass(frozen=True, slots=True)
class MemoryAnchorHealthReceipt:
    sequence: int
    memory_id: str
    actor_agent_id: str
    healthy: bool
    evidence_ref: str
    observed_version_scope: str | None
    reason: str

    def __post_init__(self) -> None:
        if int(self.sequence) <= 0:
            raise ValueError("anchor health sequence must be positive")
        for label, value in (
            ("memory_id", self.memory_id),
            ("actor_agent_id", self.actor_agent_id),
            ("evidence_ref", self.evidence_ref),
            ("reason", self.reason),
        ):
            _require_nonempty(value, label=label)
        if self.observed_version_scope is not None:
            _require_nonempty(self.observed_version_scope, label="observed_version_scope")

    @property
    def receipt_id(self) -> str:
        return "mahr-" + canonical_digest(self._identity_state())[:24]

    def _identity_state(self) -> dict[str, Any]:
        return {
            "schema": _ANCHOR_HEALTH_RECEIPT_SCHEMA,
            "sequence": int(self.sequence),
            "memory_id": self.memory_id,
            "actor_agent_id": self.actor_agent_id,
            "healthy": bool(self.healthy),
            "evidence_ref": self.evidence_ref,
            "observed_version_scope": self.observed_version_scope,
            "reason": self.reason,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self._identity_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryAnchorHealthReceipt":
        if str(state.get("schema", _ANCHOR_HEALTH_RECEIPT_SCHEMA)) != _ANCHOR_HEALTH_RECEIPT_SCHEMA:
            raise ValueError("unsupported memory anchor health receipt schema")
        result = cls(
            sequence=int(state["sequence"]),
            memory_id=str(state["memory_id"]),
            actor_agent_id=str(state["actor_agent_id"]),
            healthy=bool(state["healthy"]),
            evidence_ref=str(state["evidence_ref"]),
            observed_version_scope=None if state.get("observed_version_scope") is None else str(state["observed_version_scope"]),
            reason=str(state["reason"]),
        )
        _require_content_address(
            state,
            key="receipt_id",
            expected=result.receipt_id,
            label="memory anchor health receipt",
        )
        return result


__all__ = (
    "MemoryRetrievalPolicy",
    "MemoryRetrievalQuery",
    "MemoryRetrievalReceipt",
    "MemoryCompactionReceipt",
    "MemoryAnchorHealthReceipt",
)
