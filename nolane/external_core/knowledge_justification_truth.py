from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .knowledge_truth import KnowledgeClaim, KnowledgeLedger


PARENT_COMPONENT_ID = "external.knowledge"
TRUTH_PROTOCOL = "truth-knowledge-justification-v6"
PROJECTION_PROTOCOL = "truth-knowledge-justification-projection-v6"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be explicit and unique")
    return rows


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class KnowledgeJustificationBasis:
    justification_id: str
    claim_id: str
    claim_digest: str
    evidence_ids: tuple[str, ...]
    parent_claim_ids: tuple[str, ...]
    kind: str
    digest: str

    @classmethod
    def create(
        cls,
        *,
        justification_id: str,
        claim_id: str,
        claim_digest: str,
        evidence_ids: tuple[str, ...],
        parent_claim_ids: tuple[str, ...],
        kind: str,
    ) -> "KnowledgeJustificationBasis":
        justification_id = _explicit(justification_id, "justification basis id")
        claim_id = _explicit(claim_id, "justification basis claim id")
        claim_digest = _explicit(claim_digest, "justification basis claim digest")
        evidence_ids = _ids(tuple(evidence_ids), "justification basis evidence ids")
        parent_claim_ids = _ids(tuple(parent_claim_ids), "justification basis parent claim ids")
        kind = _explicit(kind, "justification basis kind")
        if kind not in {"legacy", "explicit"}:
            raise ValueError("unsupported justification basis kind")
        if claim_id in parent_claim_ids:
            raise ValueError("justification basis cannot depend on its own claim")
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "justification_id": justification_id,
            "claim_id": claim_id,
            "claim_digest": claim_digest,
            "evidence_ids": list(evidence_ids),
            "parent_claim_ids": list(parent_claim_ids),
            "kind": kind,
        }
        return cls(
            justification_id,
            claim_id,
            claim_digest,
            evidence_ids,
            parent_claim_ids,
            kind,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "justification_id": self.justification_id,
            "claim_id": self.claim_id,
            "claim_digest": self.claim_digest,
            "evidence_ids": list(self.evidence_ids),
            "parent_claim_ids": list(self.parent_claim_ids),
            "kind": self.kind,
            "digest": self.digest,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeJustificationRevision:
    justification_id: str
    claim_id: str
    claim_digest: str
    revision: int
    predecessor_digest: str
    evidence_ids: tuple[str, ...]
    parent_claim_ids: tuple[str, ...]
    enabled: bool
    digest: str

    @classmethod
    def _create_bound(
        cls,
        *,
        justification_id: str,
        claim_id: str,
        claim_digest: str,
        revision: int,
        predecessor_digest: str,
        evidence_ids: tuple[str, ...],
        parent_claim_ids: tuple[str, ...],
        enabled: bool,
    ) -> "KnowledgeJustificationRevision":
        justification_id = _explicit(justification_id, "justification id")
        claim_id = _explicit(claim_id, "justification claim id")
        claim_digest = _explicit(claim_digest, "justification claim digest")
        revision = int(revision)
        predecessor_digest = str(predecessor_digest).strip()
        evidence_ids = _ids(tuple(evidence_ids), "justification evidence ids")
        parent_claim_ids = _ids(tuple(parent_claim_ids), "justification parent claim ids")
        if claim_id in parent_claim_ids:
            raise ValueError("justification cannot depend on its own claim")
        if revision < 1:
            raise ValueError("justification revision must be positive")
        if revision == 1 and predecessor_digest:
            raise ValueError("first justification revision cannot declare predecessor")
        if revision > 1 and not predecessor_digest:
            raise ValueError("later justification revision requires predecessor")
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "justification_id": justification_id,
            "claim_id": claim_id,
            "claim_digest": claim_digest,
            "revision": revision,
            "predecessor_digest": predecessor_digest,
            "evidence_ids": list(evidence_ids),
            "parent_claim_ids": list(parent_claim_ids),
            "enabled": bool(enabled),
        }
        return cls(
            justification_id,
            claim_id,
            claim_digest,
            revision,
            predecessor_digest,
            evidence_ids,
            parent_claim_ids,
            bool(enabled),
            canonical_digest(payload),
        )

    @classmethod
    def create(
        cls,
        *,
        justification_id: str,
        claim: KnowledgeClaim,
        revision: int = 1,
        predecessor_digest: str = "",
        evidence_ids: tuple[str, ...] = (),
        parent_claim_ids: tuple[str, ...] = (),
        enabled: bool = True,
    ) -> "KnowledgeJustificationRevision":
        if not isinstance(claim, KnowledgeClaim):
            raise TypeError("justification revision requires canonical KnowledgeClaim")
        return cls._create_bound(
            justification_id=justification_id,
            claim_id=claim.claim_id,
            claim_digest=claim.content_digest,
            revision=revision,
            predecessor_digest=predecessor_digest,
            evidence_ids=evidence_ids,
            parent_claim_ids=parent_claim_ids,
            enabled=enabled,
        )

    def basis(self) -> KnowledgeJustificationBasis:
        return KnowledgeJustificationBasis.create(
            justification_id=self.justification_id,
            claim_id=self.claim_id,
            claim_digest=self.claim_digest,
            evidence_ids=self.evidence_ids,
            parent_claim_ids=self.parent_claim_ids,
            kind="explicit",
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "justification_id": self.justification_id,
            "claim_id": self.claim_id,
            "claim_digest": self.claim_digest,
            "revision": self.revision,
            "predecessor_digest": self.predecessor_digest,
            "evidence_ids": list(self.evidence_ids),
            "parent_claim_ids": list(self.parent_claim_ids),
            "enabled": self.enabled,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "KnowledgeJustificationRevision":
        _unexpected(
            state,
            {
                "protocol",
                "justification_id",
                "claim_id",
                "claim_digest",
                "revision",
                "predecessor_digest",
                "evidence_ids",
                "parent_claim_ids",
                "enabled",
                "digest",
            },
            "knowledge justification revision",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported knowledge justification protocol")
        row = cls._create_bound(
            justification_id=str(state["justification_id"]),
            claim_id=str(state["claim_id"]),
            claim_digest=str(state["claim_digest"]),
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            parent_claim_ids=tuple(str(value) for value in state.get("parent_claim_ids", ())),
            enabled=bool(state["enabled"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("knowledge justification revision digest mismatch")
        return row


class KnowledgeJustificationRegistry:
    """Append-only alternative derivation sidecar under ``external.knowledge``."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[KnowledgeJustificationRevision]] = {}

    @staticmethod
    def legacy_basis(claim: KnowledgeClaim) -> KnowledgeJustificationBasis:
        seed = canonical_digest(
            {
                "protocol": TRUTH_PROTOCOL,
                "kind": "legacy",
                "claim_id": claim.claim_id,
                "claim_digest": claim.content_digest,
                "evidence_ids": list(claim.evidence_ids),
                "parent_claim_ids": list(claim.parent_claim_ids),
            }
        )
        return KnowledgeJustificationBasis.create(
            justification_id=f"legacy-justification-{seed[:24]}",
            claim_id=claim.claim_id,
            claim_digest=claim.content_digest,
            evidence_ids=claim.evidence_ids,
            parent_claim_ids=claim.parent_claim_ids,
            kind="legacy",
        )

    def revisions(self, justification_id: str) -> tuple[KnowledgeJustificationRevision, ...]:
        return tuple(self._revisions.get(str(justification_id), ()))

    def current(self, justification_id: str) -> KnowledgeJustificationRevision | None:
        rows = self.revisions(justification_id)
        return rows[-1] if rows else None

    def current_revisions(self, claim_id: str | None = None) -> tuple[KnowledgeJustificationRevision, ...]:
        rows = tuple(history[-1] for history in self._revisions.values() if history)
        if claim_id is not None:
            rows = tuple(row for row in rows if row.claim_id == str(claim_id))
        return tuple(sorted(rows, key=lambda row: row.justification_id))

    def _validate_binding(self, row: KnowledgeJustificationRevision, *, knowledge: KnowledgeLedger) -> None:
        try:
            claim = knowledge.get(row.claim_id)
        except KeyError as exc:
            raise ValueError("justification references unknown canonical claim") from exc
        if claim.content_digest != row.claim_digest:
            raise ValueError("justification cannot rebind canonical claim digest")
        for parent_id in row.parent_claim_ids:
            try:
                knowledge.get(parent_id)
            except KeyError as exc:
                raise ValueError(f"unknown justification parent claim: {parent_id}") from exc

    def _validate_duplicate_basis(self, row: KnowledgeJustificationRevision, *, knowledge: KnowledgeLedger) -> None:
        if not row.enabled:
            return
        claim = knowledge.get(row.claim_id)
        legacy = self.legacy_basis(claim)
        basis_key = (row.evidence_ids, row.parent_claim_ids)
        if basis_key == (legacy.evidence_ids, legacy.parent_claim_ids):
            raise ValueError("explicit justification duplicates legacy justification basis")
        for current in self.current_revisions(row.claim_id):
            if current.justification_id == row.justification_id or not current.enabled:
                continue
            if basis_key == (current.evidence_ids, current.parent_claim_ids):
                raise ValueError("duplicate live justification basis")

    def effective_justifications(
        self,
        claim_id: str,
        *,
        knowledge: KnowledgeLedger,
    ) -> tuple[KnowledgeJustificationBasis, ...]:
        claim = knowledge.get(str(claim_id))
        rows = [self.legacy_basis(claim)]
        rows.extend(
            row.basis()
            for row in self.current_revisions(claim.claim_id)
            if row.enabled
        )
        return tuple(sorted(rows, key=lambda row: row.justification_id))

    def _effective_parent_ids(self, claim_id: str, *, knowledge: KnowledgeLedger) -> tuple[str, ...]:
        parents: set[str] = set()
        for row in self.effective_justifications(str(claim_id), knowledge=knowledge):
            parents.update(row.parent_claim_ids)
        return tuple(sorted(parents))

    def _assert_acyclic(self, *, knowledge: KnowledgeLedger) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(claim_id: str) -> None:
            if claim_id in visiting:
                raise ValueError("effective justification dependency graph contains a cycle")
            if claim_id in visited:
                return
            visiting.add(claim_id)
            for parent_id in self._effective_parent_ids(claim_id, knowledge=knowledge):
                visit(parent_id)
            visiting.remove(claim_id)
            visited.add(claim_id)

        for claim in knowledge.claims():
            visit(claim.claim_id)

    def register(
        self,
        row: KnowledgeJustificationRevision,
        *,
        knowledge: KnowledgeLedger,
    ) -> KnowledgeJustificationRevision:
        if not isinstance(row, KnowledgeJustificationRevision):
            raise TypeError("justification registry accepts KnowledgeJustificationRevision only")
        if not isinstance(knowledge, KnowledgeLedger):
            raise TypeError("justification registry requires canonical KnowledgeLedger")
        self._validate_binding(row, knowledge=knowledge)
        history = self._revisions.setdefault(row.justification_id, [])
        if not history:
            if row.revision != 1:
                raise ValueError("justification revision sequence must start at 1")
            self._validate_duplicate_basis(row, knowledge=knowledge)
            history.append(row)
            try:
                self._assert_acyclic(knowledge=knowledge)
            except Exception:
                history.pop()
                if not history:
                    self._revisions.pop(row.justification_id, None)
                raise
            return row

        current = history[-1]
        if row.claim_id != current.claim_id or row.claim_digest != current.claim_digest:
            raise ValueError("justification lineage cannot rebind canonical claim")
        if row.revision == current.revision:
            if row != current:
                raise ValueError("justification revision collision")
            return current
        if row.revision != current.revision + 1:
            raise ValueError("justification revision sequence must advance exactly once")
        if row.predecessor_digest != current.digest:
            raise ValueError("justification predecessor mismatch")
        self._validate_duplicate_basis(row, knowledge=knowledge)
        history.append(row)
        try:
            self._assert_acyclic(knowledge=knowledge)
        except Exception:
            history.pop()
            raise
        return row

    def lineage_claim_ids(self, claim_id: str, *, knowledge: KnowledgeLedger) -> tuple[str, ...]:
        target = knowledge.get(str(claim_id))
        seen: set[str] = set()
        pending = [target.claim_id]
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            knowledge.get(current)
            seen.add(current)
            pending.extend(self._effective_parent_ids(current, knowledge=knowledge))
        return tuple(sorted(seen))

    def evidence_ids_for_claims(
        self,
        claim_ids: tuple[str, ...],
        *,
        knowledge: KnowledgeLedger,
    ) -> tuple[str, ...]:
        ids = _ids(tuple(claim_ids), "justification scope claim ids")
        if not ids:
            raise ValueError("justification scope claim ids must not be empty")
        evidence_ids: set[str] = set()
        for claim_id in ids:
            for row in self.effective_justifications(claim_id, knowledge=knowledge):
                evidence_ids.update(row.evidence_ids)
        return tuple(sorted(evidence_ids))

    def projection_state(
        self,
        claim_ids: tuple[str, ...],
        *,
        knowledge: KnowledgeLedger,
    ) -> dict[str, Any]:
        ids = _ids(tuple(claim_ids), "justification projection claim ids")
        if not ids:
            raise ValueError("justification projection requires at least one claim")
        claims = []
        for claim_id in ids:
            claim = knowledge.get(claim_id)
            claims.append(
                {
                    "claim_id": claim.claim_id,
                    "claim_digest": claim.content_digest,
                    "legacy_basis": self.legacy_basis(claim).to_state(),
                    "current_explicit_revisions": [
                        row.to_state() for row in self.current_revisions(claim.claim_id)
                    ],
                }
            )
        return {"protocol": PROJECTION_PROTOCOL, "claims": claims}

    def projection_digest(
        self,
        claim_ids: tuple[str, ...],
        *,
        knowledge: KnowledgeLedger,
    ) -> str:
        return canonical_digest(self.projection_state(claim_ids, knowledge=knowledge))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "revisions": [
                row.to_state()
                for justification_id in sorted(self._revisions)
                for row in self._revisions[justification_id]
            ],
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        knowledge: KnowledgeLedger,
    ) -> "KnowledgeJustificationRegistry":
        _unexpected(state, {"protocol", "revisions"}, "knowledge justification registry")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported knowledge justification protocol")
        parsed: list[KnowledgeJustificationRevision] = []
        seen: set[tuple[str, int]] = set()
        for value in state.get("revisions", ()):
            row = KnowledgeJustificationRevision.from_state(value)
            key = (row.justification_id, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized justification revision")
            seen.add(key)
            parsed.append(row)
        registry = cls()
        for row in sorted(parsed, key=lambda value: (value.justification_id, value.revision)):
            registry.register(row, knowledge=knowledge)
        return registry


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "PROJECTION_PROTOCOL",
    "KnowledgeJustificationBasis",
    "KnowledgeJustificationRevision",
    "KnowledgeJustificationRegistry",
)
