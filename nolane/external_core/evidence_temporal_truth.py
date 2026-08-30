from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .evidence_truth import EvidenceLedger, TruthEvidence
from .temporal_truth import TemporalContext, TruthInterval


PARENT_COMPONENT_ID = "external.evidence"
TRUTH_PROTOCOL = "truth-evidence-temporal-binding-v1"
PROJECTION_PROTOCOL = "truth-evidence-temporal-scope-v1"


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} state field(s): {','.join(sorted(extra))}")


def _ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError("temporal evidence ids must be explicit and unique")
    return rows


@dataclass(frozen=True, slots=True)
class EvidenceTemporalBinding:
    evidence_id: str
    evidence_digest: str
    revision: int
    previous_digest: str
    interval: TruthInterval
    digest: str

    @classmethod
    def create(
        cls,
        evidence: TruthEvidence,
        *,
        revision: int = 1,
        previous_digest: str = "",
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> "EvidenceTemporalBinding":
        if not isinstance(evidence, TruthEvidence):
            raise TypeError("evidence temporal binding requires canonical TruthEvidence")
        revision = int(revision)
        previous_digest = str(previous_digest).strip()
        if revision < 1:
            raise ValueError("evidence temporal revision must be positive")
        if revision == 1 and previous_digest:
            raise ValueError("first evidence temporal revision cannot declare predecessor")
        if revision > 1 and not previous_digest:
            raise ValueError("later evidence temporal revision requires predecessor")
        interval = TruthInterval.create(valid_from=valid_from, valid_until=valid_until)
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "evidence_id": evidence.evidence_id,
            "evidence_digest": evidence.content_digest,
            "revision": revision,
            "previous_digest": previous_digest,
            "interval": interval.to_state(),
        }
        return cls(
            evidence.evidence_id,
            evidence.content_digest,
            revision,
            previous_digest,
            interval,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "evidence_id": self.evidence_id,
            "evidence_digest": self.evidence_digest,
            "revision": self.revision,
            "previous_digest": self.previous_digest,
            "interval": self.interval.to_state(),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EvidenceTemporalBinding":
        _unexpected(
            state,
            {"protocol", "evidence_id", "evidence_digest", "revision", "previous_digest", "interval", "digest"},
            "evidence temporal binding",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported evidence temporal binding protocol")
        evidence_id = str(state["evidence_id"]).strip()
        evidence_digest = str(state["evidence_digest"]).strip()
        if not evidence_id or not evidence_digest:
            raise ValueError("evidence temporal binding identity must be explicit")
        revision = int(state["revision"])
        previous_digest = str(state.get("previous_digest", "")).strip()
        if revision < 1:
            raise ValueError("evidence temporal revision must be positive")
        if revision == 1 and previous_digest:
            raise ValueError("first evidence temporal revision cannot declare predecessor")
        if revision > 1 and not previous_digest:
            raise ValueError("later evidence temporal revision requires predecessor")
        interval = TruthInterval.from_state(state["interval"])
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "evidence_id": evidence_id,
            "evidence_digest": evidence_digest,
            "revision": revision,
            "previous_digest": previous_digest,
            "interval": interval.to_state(),
        }
        row = cls(
            evidence_id,
            evidence_digest,
            revision,
            previous_digest,
            interval,
            canonical_digest(payload),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("evidence temporal binding digest mismatch")
        return row


class TemporalEvidenceView:
    """Append-only temporal applicability revision lineage for TruthEvidence rows."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[EvidenceTemporalBinding]] = {}

    def record(self, row: EvidenceTemporalBinding) -> EvidenceTemporalBinding:
        if not isinstance(row, EvidenceTemporalBinding):
            raise TypeError("temporal evidence view accepts EvidenceTemporalBinding only")
        history = self._revisions.setdefault(row.evidence_id, [])
        if not history:
            if row.revision != 1:
                raise ValueError("evidence temporal revision sequence must start at 1")
            history.append(row)
            return row
        current = history[-1]
        if row.evidence_digest != current.evidence_digest:
            raise ValueError("evidence temporal lineage cannot rebind base evidence")
        if row.revision == current.revision:
            if row != current:
                raise ValueError("evidence temporal revision collision")
            return current
        if row.revision != current.revision + 1:
            raise ValueError("evidence temporal revision sequence must advance exactly once")
        if row.previous_digest != current.digest:
            raise ValueError("evidence temporal predecessor mismatch")
        history.append(row)
        return row

    def bind(
        self,
        evidence: TruthEvidence,
        *,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> EvidenceTemporalBinding:
        return self.record(EvidenceTemporalBinding.create(
            evidence,
            revision=1,
            previous_digest="",
            valid_from=valid_from,
            valid_until=valid_until,
        ))

    def revise(
        self,
        evidence: TruthEvidence,
        *,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> EvidenceTemporalBinding:
        current = self.binding(evidence.evidence_id)
        if current is None:
            raise ValueError("evidence temporal revision requires existing lineage")
        if current.evidence_digest != evidence.content_digest:
            raise ValueError("evidence temporal revision cannot rebind base evidence")
        return self.record(EvidenceTemporalBinding.create(
            evidence,
            revision=current.revision + 1,
            previous_digest=current.digest,
            valid_from=valid_from,
            valid_until=valid_until,
        ))

    def revisions(self, evidence_id: str) -> tuple[EvidenceTemporalBinding, ...]:
        return tuple(self._revisions.get(str(evidence_id), ()))

    def binding(self, evidence_id: str) -> EvidenceTemporalBinding | None:
        rows = self.revisions(evidence_id)
        return rows[-1] if rows else None

    def state_at(
        self,
        evidence_id: str,
        *,
        evidence: EvidenceLedger,
        temporal_context: TemporalContext,
    ) -> str:
        if not isinstance(temporal_context, TemporalContext):
            raise TypeError("temporal evidence state requires TemporalContext")
        evidence_id = str(evidence_id)
        try:
            row = evidence.get(evidence_id)
        except KeyError:
            return "missing"
        if not evidence.is_active(evidence_id):
            return "revoked"
        binding = self.binding(evidence_id)
        if binding is None:
            return "active"
        if binding.evidence_digest != row.content_digest:
            return "binding_mismatch"
        return binding.interval.state_at(temporal_context.as_of)

    def projection_state(
        self,
        evidence_ids: tuple[str, ...],
        *,
        evidence: EvidenceLedger,
        temporal_context: TemporalContext,
    ) -> dict[str, Any]:
        ids = _ids(tuple(evidence_ids))
        rows = []
        for evidence_id in ids:
            binding = self.binding(evidence_id)
            rows.append({
                "evidence_id": evidence_id,
                "state": self.state_at(evidence_id, evidence=evidence, temporal_context=temporal_context),
                "binding": None if binding is None else binding.to_state(),
            })
        return {
            "protocol": PROJECTION_PROTOCOL,
            "temporal_context_digest": temporal_context.digest,
            "as_of": temporal_context.as_of,
            "base_evidence": evidence.scoped_state(ids),
            "evidence": rows,
        }

    def projection_digest(
        self,
        evidence_ids: tuple[str, ...],
        *,
        evidence: EvidenceLedger,
        temporal_context: TemporalContext,
    ) -> str:
        return canonical_digest(self.projection_state(
            evidence_ids,
            evidence=evidence,
            temporal_context=temporal_context,
        ))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "bindings": [
                row.to_state()
                for evidence_id in sorted(self._revisions)
                for row in self._revisions[evidence_id]
            ],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TemporalEvidenceView":
        _unexpected(state, {"protocol", "bindings"}, "temporal evidence view")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported temporal evidence view protocol")
        view = cls()
        seen: set[tuple[str, int]] = set()
        for value in state.get("bindings", ()):
            row = EvidenceTemporalBinding.from_state(value)
            key = (row.evidence_id, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized evidence temporal revision")
            seen.add(key)
            view.record(row)
        return view


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "PROJECTION_PROTOCOL",
    "EvidenceTemporalBinding",
    "TemporalEvidenceView",
)
