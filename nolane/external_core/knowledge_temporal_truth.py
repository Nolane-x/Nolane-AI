from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.knowledge import RelationCardinality, RelationSemanticsRegistry
from .knowledge_truth import KnowledgeClaim, KnowledgeLedger
from .temporal_truth import TemporalContext, TruthInterval


PARENT_COMPONENT_ID = "external.knowledge"
TRUTH_PROTOCOL = "truth-knowledge-temporal-binding-v1"
PROJECTION_PROTOCOL = "truth-knowledge-temporal-scope-v1"


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} state field(s): {','.join(sorted(extra))}")


def _ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be explicit and unique")
    return rows


@dataclass(frozen=True, slots=True)
class KnowledgeTemporalBinding:
    claim_id: str
    claim_digest: str
    interval: TruthInterval
    digest: str

    @classmethod
    def create(
        cls,
        claim: KnowledgeClaim,
        *,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> "KnowledgeTemporalBinding":
        if not isinstance(claim, KnowledgeClaim):
            raise TypeError("knowledge temporal binding requires canonical KnowledgeClaim")
        interval = TruthInterval.create(valid_from=valid_from, valid_until=valid_until)
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "claim_id": claim.claim_id,
            "claim_digest": claim.content_digest,
            "interval": interval.to_state(),
        }
        return cls(claim.claim_id, claim.content_digest, interval, canonical_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "claim_id": self.claim_id,
            "claim_digest": self.claim_digest,
            "interval": self.interval.to_state(),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "KnowledgeTemporalBinding":
        _unexpected(state, {"protocol", "claim_id", "claim_digest", "interval", "digest"}, "knowledge temporal binding")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported knowledge temporal binding protocol")
        claim_id = str(state["claim_id"]).strip()
        claim_digest = str(state["claim_digest"]).strip()
        if not claim_id or not claim_digest:
            raise ValueError("knowledge temporal binding identity must be explicit")
        interval = TruthInterval.from_state(state["interval"])
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "claim_id": claim_id,
            "claim_digest": claim_digest,
            "interval": interval.to_state(),
        }
        row = cls(claim_id, claim_digest, interval, canonical_digest(payload))
        if str(state["digest"]) != row.digest:
            raise ValueError("knowledge temporal binding digest mismatch")
        return row


class TemporalKnowledgeView:
    """Append-only temporal applicability sidecar for canonical KnowledgeClaim rows."""

    def __init__(self) -> None:
        self._bindings: dict[str, KnowledgeTemporalBinding] = {}

    def record(self, row: KnowledgeTemporalBinding) -> KnowledgeTemporalBinding:
        if not isinstance(row, KnowledgeTemporalBinding):
            raise TypeError("temporal knowledge view accepts KnowledgeTemporalBinding only")
        old = self._bindings.get(row.claim_id)
        if old is not None and old != row:
            raise ValueError("knowledge temporal binding rebind collision")
        self._bindings[row.claim_id] = row
        return row

    def bind(
        self,
        claim: KnowledgeClaim,
        *,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> KnowledgeTemporalBinding:
        return self.record(KnowledgeTemporalBinding.create(
            claim,
            valid_from=valid_from,
            valid_until=valid_until,
        ))

    def binding(self, claim_id: str) -> KnowledgeTemporalBinding | None:
        return self._bindings.get(str(claim_id))

    def state_at(
        self,
        claim_id: str,
        *,
        knowledge: KnowledgeLedger,
        temporal_context: TemporalContext,
    ) -> str:
        if not isinstance(temporal_context, TemporalContext):
            raise TypeError("temporal knowledge state requires TemporalContext")
        claim_id = str(claim_id)
        try:
            claim = knowledge.get(claim_id)
        except KeyError:
            return "missing"
        binding = self.binding(claim_id)
        if binding is None:
            return "active"
        if binding.claim_digest != claim.content_digest:
            return "binding_mismatch"
        return binding.interval.state_at(temporal_context.as_of)

    def truth_scope_claim_ids_v4(
        self,
        claim_id: str,
        *,
        knowledge: KnowledgeLedger,
        relation_semantics: RelationSemanticsRegistry,
        temporal_context: TemporalContext,
    ) -> tuple[str, ...]:
        if not isinstance(relation_semantics, RelationSemanticsRegistry):
            raise TypeError("temporal relation-aware scope requires canonical relation semantics registry")
        target = str(claim_id)
        scope = set(knowledge.lineage_claim_ids(target))
        changed = True
        while changed:
            changed = False
            competitors: set[str] = set()
            for current in tuple(scope):
                if self.state_at(current, knowledge=knowledge, temporal_context=temporal_context) != "active":
                    continue
                claim = knowledge.get(current)
                if relation_semantics.cardinality(claim.relation) is RelationCardinality.MULTI_VALUED:
                    continue
                for row in knowledge.claims():
                    if (
                        row.claim_id != claim.claim_id
                        and row.subject == claim.subject
                        and row.relation == claim.relation
                        and row.object != claim.object
                        and self.state_at(row.claim_id, knowledge=knowledge, temporal_context=temporal_context) == "active"
                    ):
                        competitors.add(row.claim_id)
            expanded = set(scope)
            for competitor in competitors:
                expanded.update(knowledge.lineage_claim_ids(competitor))
            if expanded != scope:
                scope = expanded
                changed = True
        return tuple(sorted(scope))

    def projection_state(
        self,
        claim_ids: tuple[str, ...],
        *,
        knowledge: KnowledgeLedger,
        temporal_context: TemporalContext,
    ) -> dict[str, Any]:
        ids = _ids(tuple(claim_ids), "temporal knowledge claim ids")
        if not ids:
            raise ValueError("temporal knowledge projection requires at least one claim")
        rows = []
        for claim_id in ids:
            binding = self.binding(claim_id)
            rows.append({
                "claim_id": claim_id,
                "state": self.state_at(claim_id, knowledge=knowledge, temporal_context=temporal_context),
                "binding": None if binding is None else binding.to_state(),
            })
        return {
            "protocol": PROJECTION_PROTOCOL,
            "temporal_context_digest": temporal_context.digest,
            "as_of": temporal_context.as_of,
            "base_knowledge": knowledge.scoped_state(ids),
            "claims": rows,
        }

    def projection_digest(
        self,
        claim_ids: tuple[str, ...],
        *,
        knowledge: KnowledgeLedger,
        temporal_context: TemporalContext,
    ) -> str:
        return canonical_digest(self.projection_state(
            claim_ids,
            knowledge=knowledge,
            temporal_context=temporal_context,
        ))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "bindings": [self._bindings[key].to_state() for key in sorted(self._bindings)],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TemporalKnowledgeView":
        _unexpected(state, {"protocol", "bindings"}, "temporal knowledge view")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported temporal knowledge view protocol")
        view = cls()
        seen: set[str] = set()
        for value in state.get("bindings", ()):
            row = KnowledgeTemporalBinding.from_state(value)
            if row.claim_id in seen:
                raise ValueError("duplicate serialized knowledge temporal binding")
            seen.add(row.claim_id)
            view.record(row)
        return view


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "PROJECTION_PROTOCOL",
    "KnowledgeTemporalBinding",
    "TemporalKnowledgeView",
)
