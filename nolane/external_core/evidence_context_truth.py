from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .evidence_truth import EvidenceLedger, TruthEvidence
from .knowledge_context_truth import TruthContext


PARENT_COMPONENT_ID = "external.evidence"
EVIDENCE_CONTEXT_PROTOCOL = "truth-evidence-applicability-context-v9"
EVIDENCE_CONTEXT_PROJECTION_PROTOCOL = "truth-evidence-applicability-context-projection-v9"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


def _qualifiers(
    values: tuple[tuple[str, str], ...],
    *,
    allow_empty: bool,
    field: str,
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    for raw in tuple(values):
        if not isinstance(raw, (tuple, list)) or len(raw) != 2:
            raise ValueError(f"{field} entries must be key/value pairs")
        key = _explicit(str(raw[0]), f"{field} key")
        value = _explicit(str(raw[1]), f"{field} value")
        rows.append((key, value))
    rows.sort()
    keys = [key for key, _ in rows]
    if len(set(keys)) != len(keys):
        raise ValueError(f"{field} keys must be unique")
    if not allow_empty and not rows:
        raise ValueError(f"{field} must be explicit and non-empty")
    return tuple(rows)


def _qualifier_state(values: tuple[tuple[str, str], ...]) -> list[list[str]]:
    return [[key, value] for key, value in values]


@dataclass(frozen=True, slots=True)
class EvidenceContextBindingRevision:
    evidence_id: str
    evidence_content_digest: str
    revision: int
    predecessor_digest: str
    qualifiers: tuple[tuple[str, str], ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        evidence: TruthEvidence,
        revision: int = 1,
        predecessor_digest: str = "",
        qualifiers: tuple[tuple[str, str], ...],
    ) -> "EvidenceContextBindingRevision":
        if not isinstance(evidence, TruthEvidence):
            raise TypeError("evidence context binding requires exact TruthEvidence")
        revision = int(revision)
        if revision < 1:
            raise ValueError("evidence context revision must be positive")
        predecessor = str(predecessor_digest).strip()
        rows = _qualifiers(
            tuple(qualifiers),
            allow_empty=False,
            field="evidence context qualifiers",
        )
        payload = {
            "protocol": EVIDENCE_CONTEXT_PROTOCOL,
            "evidence_id": _explicit(evidence.evidence_id, "evidence context evidence id"),
            "evidence_content_digest": _explicit(
                evidence.content_digest,
                "evidence context content digest",
            ),
            "revision": revision,
            "predecessor_digest": predecessor,
            "qualifiers": _qualifier_state(rows),
        }
        return cls(
            payload["evidence_id"],
            payload["evidence_content_digest"],
            revision,
            predecessor,
            rows,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": EVIDENCE_CONTEXT_PROTOCOL,
            "evidence_id": self.evidence_id,
            "evidence_content_digest": self.evidence_content_digest,
            "revision": self.revision,
            "predecessor_digest": self.predecessor_digest,
            "qualifiers": _qualifier_state(self.qualifiers),
            "digest": self.digest,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        evidence: EvidenceLedger,
    ) -> "EvidenceContextBindingRevision":
        _unexpected(
            state,
            {
                "protocol",
                "evidence_id",
                "evidence_content_digest",
                "revision",
                "predecessor_digest",
                "qualifiers",
                "digest",
            },
            "evidence context revision",
        )
        if str(state.get("protocol", "")) != EVIDENCE_CONTEXT_PROTOCOL:
            raise ValueError("unsupported evidence context protocol")
        item = evidence.get(str(state["evidence_id"]))
        if str(state["evidence_content_digest"]) != item.content_digest:
            raise ValueError("evidence context content digest mismatch")
        row = cls.create(
            evidence=item,
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            qualifiers=tuple(
                (str(value[0]), str(value[1]))
                for value in state.get("qualifiers", ())
            ),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("evidence context revision digest mismatch")
        return row


class EvidenceContextBindingRegistry:
    """Append-only applicability bindings for immutable TruthEvidence identities."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[EvidenceContextBindingRevision]] = {}
        self._content_digests: dict[str, str] = {}

    def register(
        self,
        row: EvidenceContextBindingRevision,
        *,
        evidence: EvidenceLedger,
    ) -> EvidenceContextBindingRevision:
        if not isinstance(row, EvidenceContextBindingRevision):
            raise TypeError("evidence context registry accepts evidence context revisions only")
        item = evidence.get(row.evidence_id)
        if item.content_digest != row.evidence_content_digest:
            raise ValueError("evidence context content digest mismatch")
        bound = self._content_digests.get(row.evidence_id)
        if bound is not None and bound != row.evidence_content_digest:
            raise ValueError("evidence context evidence/content rebind")
        history = self._revisions.setdefault(row.evidence_id, [])
        if not history:
            if row.revision != 1:
                raise ValueError("evidence context revision must start at 1")
            if row.predecessor_digest:
                raise ValueError("evidence context first revision cannot have predecessor")
        else:
            previous = history[-1]
            if row.revision != previous.revision + 1:
                raise ValueError("evidence context revision must advance exactly once")
            if row.predecessor_digest != previous.digest:
                raise ValueError("evidence context predecessor digest mismatch")
            if row.evidence_content_digest != previous.evidence_content_digest:
                raise ValueError("evidence context evidence/content rebind")
        history.append(row)
        self._content_digests[row.evidence_id] = row.evidence_content_digest
        return row

    def current(self, evidence_id: str) -> EvidenceContextBindingRevision | None:
        history = self._revisions.get(str(evidence_id), ())
        return history[-1] if history else None

    def required_qualifiers(self, evidence_id: str) -> tuple[tuple[str, str], ...]:
        current = self.current(str(evidence_id))
        return current.qualifiers if current is not None else ()

    def applies(self, evidence_id: str, truth_context: TruthContext) -> bool:
        if not isinstance(truth_context, TruthContext):
            raise TypeError("evidence context applicability requires TruthContext")
        return truth_context.matches(self.required_qualifiers(str(evidence_id)))

    def projection_state(self, evidence_ids: tuple[str, ...]) -> dict[str, Any]:
        requested = tuple(
            sorted({_explicit(value, "evidence context projection id") for value in evidence_ids})
        )
        rows: list[dict[str, Any]] = []
        for evidence_id in requested:
            current = self.current(evidence_id)
            if current is None:
                rows.append({"evidence_id": evidence_id, "status": "global"})
            else:
                rows.append(
                    {
                        "evidence_id": evidence_id,
                        "status": "bound",
                        "evidence_content_digest": current.evidence_content_digest,
                        "revision": current.revision,
                        "binding_digest": current.digest,
                        "qualifiers": _qualifier_state(current.qualifiers),
                    }
                )
        return {
            "protocol": EVIDENCE_CONTEXT_PROJECTION_PROTOCOL,
            "requested_evidence_ids": list(requested),
            "evidence": rows,
        }

    def projection_digest(self, evidence_ids: tuple[str, ...]) -> str:
        return canonical_digest(self.projection_state(tuple(evidence_ids)))

    def revisions(self) -> tuple[EvidenceContextBindingRevision, ...]:
        return tuple(
            row
            for evidence_id in sorted(self._revisions)
            for row in self._revisions[evidence_id]
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": EVIDENCE_CONTEXT_PROTOCOL,
            "revisions": [row.to_state() for row in self.revisions()],
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        evidence: EvidenceLedger,
    ) -> "EvidenceContextBindingRegistry":
        _unexpected(state, {"protocol", "revisions"}, "evidence context registry")
        if str(state.get("protocol", "")) != EVIDENCE_CONTEXT_PROTOCOL:
            raise ValueError("unsupported evidence context registry protocol")
        registry = cls()
        seen: set[tuple[str, int]] = set()
        for raw in state.get("revisions", ()):
            row = EvidenceContextBindingRevision.from_state(raw, evidence=evidence)
            key = (row.evidence_id, row.revision)
            if key in seen:
                raise ValueError("duplicate evidence context revision")
            seen.add(key)
            registry.register(row, evidence=evidence)
        return registry


__all__ = (
    "PARENT_COMPONENT_ID",
    "EVIDENCE_CONTEXT_PROTOCOL",
    "EVIDENCE_CONTEXT_PROJECTION_PROTOCOL",
    "EvidenceContextBindingRevision",
    "EvidenceContextBindingRegistry",
)
