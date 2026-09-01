from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .knowledge_truth import KnowledgeClaim, KnowledgeLedger


PARENT_COMPONENT_ID = "external.knowledge"
CONTEXT_PROTOCOL = "truth-applicability-context-v9"
CLAIM_CONTEXT_PROTOCOL = "truth-knowledge-applicability-context-v9"
CLAIM_CONTEXT_PROJECTION_PROTOCOL = "truth-knowledge-applicability-context-projection-v9"


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
class TruthContext:
    qualifiers: tuple[tuple[str, str], ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        qualifiers: tuple[tuple[str, str], ...] = (),
    ) -> "TruthContext":
        rows = _qualifiers(
            tuple(qualifiers),
            allow_empty=True,
            field="truth context qualifiers",
        )
        payload = {
            "protocol": CONTEXT_PROTOCOL,
            "qualifiers": _qualifier_state(rows),
        }
        return cls(rows, canonical_digest(payload))

    def matches(self, required: tuple[tuple[str, str], ...]) -> bool:
        required_rows = _qualifiers(
            tuple(required),
            allow_empty=True,
            field="required truth context qualifiers",
        )
        actual = dict(self.qualifiers)
        return all(actual.get(key) == value for key, value in required_rows)

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": CONTEXT_PROTOCOL,
            "qualifiers": _qualifier_state(self.qualifiers),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthContext":
        _unexpected(state, {"protocol", "qualifiers", "digest"}, "truth context")
        if str(state.get("protocol", "")) != CONTEXT_PROTOCOL:
            raise ValueError("unsupported truth context protocol")
        row = cls.create(
            qualifiers=tuple(
                (str(value[0]), str(value[1]))
                for value in state.get("qualifiers", ())
            )
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("truth context digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class ClaimContextBindingRevision:
    claim_id: str
    claim_content_digest: str
    revision: int
    predecessor_digest: str
    qualifiers: tuple[tuple[str, str], ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        claim: KnowledgeClaim,
        revision: int = 1,
        predecessor_digest: str = "",
        qualifiers: tuple[tuple[str, str], ...],
    ) -> "ClaimContextBindingRevision":
        if not isinstance(claim, KnowledgeClaim):
            raise TypeError("claim context binding requires exact KnowledgeClaim")
        revision = int(revision)
        if revision < 1:
            raise ValueError("claim context revision must be positive")
        predecessor = str(predecessor_digest).strip()
        rows = _qualifiers(
            tuple(qualifiers),
            allow_empty=False,
            field="claim context qualifiers",
        )
        payload = {
            "protocol": CLAIM_CONTEXT_PROTOCOL,
            "claim_id": _explicit(claim.claim_id, "claim context claim id"),
            "claim_content_digest": _explicit(
                claim.content_digest,
                "claim context content digest",
            ),
            "revision": revision,
            "predecessor_digest": predecessor,
            "qualifiers": _qualifier_state(rows),
        }
        return cls(
            payload["claim_id"],
            payload["claim_content_digest"],
            revision,
            predecessor,
            rows,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": CLAIM_CONTEXT_PROTOCOL,
            "claim_id": self.claim_id,
            "claim_content_digest": self.claim_content_digest,
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
        knowledge: KnowledgeLedger,
    ) -> "ClaimContextBindingRevision":
        _unexpected(
            state,
            {
                "protocol",
                "claim_id",
                "claim_content_digest",
                "revision",
                "predecessor_digest",
                "qualifiers",
                "digest",
            },
            "claim context revision",
        )
        if str(state.get("protocol", "")) != CLAIM_CONTEXT_PROTOCOL:
            raise ValueError("unsupported claim context protocol")
        claim = knowledge.get(str(state["claim_id"]))
        if str(state["claim_content_digest"]) != claim.content_digest:
            raise ValueError("claim context content digest mismatch")
        row = cls.create(
            claim=claim,
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            qualifiers=tuple(
                (str(value[0]), str(value[1]))
                for value in state.get("qualifiers", ())
            ),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("claim context revision digest mismatch")
        return row


class ClaimContextBindingRegistry:
    """Append-only applicability bindings for immutable KnowledgeClaim identities."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[ClaimContextBindingRevision]] = {}
        self._content_digests: dict[str, str] = {}

    def register(
        self,
        row: ClaimContextBindingRevision,
        *,
        knowledge: KnowledgeLedger,
    ) -> ClaimContextBindingRevision:
        if not isinstance(row, ClaimContextBindingRevision):
            raise TypeError("claim context registry accepts claim context revisions only")
        claim = knowledge.get(row.claim_id)
        if claim.content_digest != row.claim_content_digest:
            raise ValueError("claim context content digest mismatch")
        bound = self._content_digests.get(row.claim_id)
        if bound is not None and bound != row.claim_content_digest:
            raise ValueError("claim context claim/content rebind")
        history = self._revisions.setdefault(row.claim_id, [])
        if not history:
            if row.revision != 1:
                raise ValueError("claim context revision must start at 1")
            if row.predecessor_digest:
                raise ValueError("claim context first revision cannot have predecessor")
        else:
            previous = history[-1]
            if row.revision != previous.revision + 1:
                raise ValueError("claim context revision must advance exactly once")
            if row.predecessor_digest != previous.digest:
                raise ValueError("claim context predecessor digest mismatch")
            if row.claim_content_digest != previous.claim_content_digest:
                raise ValueError("claim context claim/content rebind")
        history.append(row)
        self._content_digests[row.claim_id] = row.claim_content_digest
        return row

    def current(self, claim_id: str) -> ClaimContextBindingRevision | None:
        history = self._revisions.get(str(claim_id), ())
        return history[-1] if history else None

    def required_qualifiers(self, claim_id: str) -> tuple[tuple[str, str], ...]:
        current = self.current(str(claim_id))
        return current.qualifiers if current is not None else ()

    def applies(self, claim_id: str, truth_context: TruthContext) -> bool:
        if not isinstance(truth_context, TruthContext):
            raise TypeError("claim context applicability requires TruthContext")
        return truth_context.matches(self.required_qualifiers(str(claim_id)))

    def projection_state(self, claim_ids: tuple[str, ...]) -> dict[str, Any]:
        requested = tuple(sorted({_explicit(value, "claim context projection id") for value in claim_ids}))
        claims: list[dict[str, Any]] = []
        for claim_id in requested:
            current = self.current(claim_id)
            if current is None:
                claims.append({"claim_id": claim_id, "status": "global"})
            else:
                claims.append(
                    {
                        "claim_id": claim_id,
                        "status": "bound",
                        "claim_content_digest": current.claim_content_digest,
                        "revision": current.revision,
                        "binding_digest": current.digest,
                        "qualifiers": _qualifier_state(current.qualifiers),
                    }
                )
        return {
            "protocol": CLAIM_CONTEXT_PROJECTION_PROTOCOL,
            "requested_claim_ids": list(requested),
            "claims": claims,
        }

    def projection_digest(self, claim_ids: tuple[str, ...]) -> str:
        return canonical_digest(self.projection_state(tuple(claim_ids)))

    def revisions(self) -> tuple[ClaimContextBindingRevision, ...]:
        return tuple(
            row
            for claim_id in sorted(self._revisions)
            for row in self._revisions[claim_id]
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": CLAIM_CONTEXT_PROTOCOL,
            "revisions": [row.to_state() for row in self.revisions()],
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        knowledge: KnowledgeLedger,
    ) -> "ClaimContextBindingRegistry":
        _unexpected(state, {"protocol", "revisions"}, "claim context registry")
        if str(state.get("protocol", "")) != CLAIM_CONTEXT_PROTOCOL:
            raise ValueError("unsupported claim context registry protocol")
        registry = cls()
        seen: set[tuple[str, int]] = set()
        for raw in state.get("revisions", ()):
            row = ClaimContextBindingRevision.from_state(raw, knowledge=knowledge)
            key = (row.claim_id, row.revision)
            if key in seen:
                raise ValueError("duplicate claim context revision")
            seen.add(key)
            registry.register(row, knowledge=knowledge)
        return registry


__all__ = (
    "PARENT_COMPONENT_ID",
    "CONTEXT_PROTOCOL",
    "CLAIM_CONTEXT_PROTOCOL",
    "CLAIM_CONTEXT_PROJECTION_PROTOCOL",
    "TruthContext",
    "ClaimContextBindingRevision",
    "ClaimContextBindingRegistry",
)
