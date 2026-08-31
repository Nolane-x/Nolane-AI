from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .knowledge_justification_truth import (
    KnowledgeJustificationBasis,
    KnowledgeJustificationRegistry,
)
from .knowledge_truth import KnowledgeClaim, KnowledgeLedger


PARENT_COMPONENT_ID = "external.knowledge"
TRUTH_PROTOCOL = "truth-knowledge-justification-undercutter-v7"
PROJECTION_PROTOCOL = "truth-knowledge-justification-undercutter-projection-v7"


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
class JustificationUndercutterRevision:
    undercutter_id: str
    target_claim_id: str
    target_claim_digest: str
    target_justification_id: str
    target_basis_digest: str
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
        undercutter_id: str,
        target_claim_id: str,
        target_claim_digest: str,
        target_justification_id: str,
        target_basis_digest: str,
        revision: int,
        predecessor_digest: str,
        evidence_ids: tuple[str, ...],
        parent_claim_ids: tuple[str, ...],
        enabled: bool,
    ) -> "JustificationUndercutterRevision":
        undercutter_id = _explicit(undercutter_id, "undercutter id")
        target_claim_id = _explicit(target_claim_id, "undercutter target claim id")
        target_claim_digest = _explicit(target_claim_digest, "undercutter target claim digest")
        target_justification_id = _explicit(
            target_justification_id, "undercutter target justification id"
        )
        target_basis_digest = _explicit(target_basis_digest, "undercutter target basis digest")
        revision = int(revision)
        predecessor_digest = str(predecessor_digest).strip()
        evidence_ids = _ids(tuple(evidence_ids), "undercutter evidence ids")
        parent_claim_ids = _ids(tuple(parent_claim_ids), "undercutter parent claim ids")
        if not evidence_ids and not parent_claim_ids:
            raise ValueError("undercutter basis must contain evidence or parent claims")
        if target_claim_id in parent_claim_ids:
            raise ValueError("undercutter cannot depend on its target claim")
        if revision < 1:
            raise ValueError("undercutter revision must be positive")
        if revision == 1 and predecessor_digest:
            raise ValueError("first undercutter revision cannot declare predecessor")
        if revision > 1 and not predecessor_digest:
            raise ValueError("later undercutter revision requires predecessor")
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "undercutter_id": undercutter_id,
            "target_claim_id": target_claim_id,
            "target_claim_digest": target_claim_digest,
            "target_justification_id": target_justification_id,
            "target_basis_digest": target_basis_digest,
            "revision": revision,
            "predecessor_digest": predecessor_digest,
            "evidence_ids": list(evidence_ids),
            "parent_claim_ids": list(parent_claim_ids),
            "enabled": bool(enabled),
        }
        return cls(
            undercutter_id,
            target_claim_id,
            target_claim_digest,
            target_justification_id,
            target_basis_digest,
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
        undercutter_id: str,
        claim: KnowledgeClaim,
        target_basis: KnowledgeJustificationBasis,
        revision: int = 1,
        predecessor_digest: str = "",
        evidence_ids: tuple[str, ...] = (),
        parent_claim_ids: tuple[str, ...] = (),
        enabled: bool = True,
    ) -> "JustificationUndercutterRevision":
        if not isinstance(claim, KnowledgeClaim):
            raise TypeError("undercutter revision requires canonical KnowledgeClaim")
        if not isinstance(target_basis, KnowledgeJustificationBasis):
            raise TypeError("undercutter revision requires KnowledgeJustificationBasis")
        if (
            target_basis.claim_id != claim.claim_id
            or target_basis.claim_digest != claim.content_digest
        ):
            raise ValueError("undercutter target basis does not belong to canonical claim")
        return cls._create_bound(
            undercutter_id=undercutter_id,
            target_claim_id=claim.claim_id,
            target_claim_digest=claim.content_digest,
            target_justification_id=target_basis.justification_id,
            target_basis_digest=target_basis.digest,
            revision=revision,
            predecessor_digest=predecessor_digest,
            evidence_ids=evidence_ids,
            parent_claim_ids=parent_claim_ids,
            enabled=enabled,
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "undercutter_id": self.undercutter_id,
            "target_claim_id": self.target_claim_id,
            "target_claim_digest": self.target_claim_digest,
            "target_justification_id": self.target_justification_id,
            "target_basis_digest": self.target_basis_digest,
            "revision": self.revision,
            "predecessor_digest": self.predecessor_digest,
            "evidence_ids": list(self.evidence_ids),
            "parent_claim_ids": list(self.parent_claim_ids),
            "enabled": self.enabled,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "JustificationUndercutterRevision":
        _unexpected(
            state,
            {
                "protocol",
                "undercutter_id",
                "target_claim_id",
                "target_claim_digest",
                "target_justification_id",
                "target_basis_digest",
                "revision",
                "predecessor_digest",
                "evidence_ids",
                "parent_claim_ids",
                "enabled",
                "digest",
            },
            "knowledge undercutter revision",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported knowledge undercutter protocol")
        row = cls._create_bound(
            undercutter_id=str(state["undercutter_id"]),
            target_claim_id=str(state["target_claim_id"]),
            target_claim_digest=str(state["target_claim_digest"]),
            target_justification_id=str(state["target_justification_id"]),
            target_basis_digest=str(state["target_basis_digest"]),
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            parent_claim_ids=tuple(str(value) for value in state.get("parent_claim_ids", ())),
            enabled=bool(state["enabled"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("knowledge undercutter revision digest mismatch")
        return row


class JustificationUndercutterRegistry:
    """Append-only exact-basis undercutters beneath ``external.knowledge``."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[JustificationUndercutterRevision]] = {}

    def revisions(self, undercutter_id: str) -> tuple[JustificationUndercutterRevision, ...]:
        return tuple(self._revisions.get(str(undercutter_id), ()))

    def current(self, undercutter_id: str) -> JustificationUndercutterRevision | None:
        rows = self.revisions(str(undercutter_id))
        return rows[-1] if rows else None

    def current_revisions(
        self,
        target_claim_id: str | None = None,
    ) -> tuple[JustificationUndercutterRevision, ...]:
        rows = tuple(history[-1] for history in self._revisions.values() if history)
        if target_claim_id is not None:
            rows = tuple(row for row in rows if row.target_claim_id == str(target_claim_id))
        return tuple(sorted(rows, key=lambda row: row.undercutter_id))

    @staticmethod
    def _basis_map(
        claim_id: str,
        *,
        knowledge: KnowledgeLedger,
        justifications: KnowledgeJustificationRegistry,
    ) -> dict[str, KnowledgeJustificationBasis]:
        return {
            basis.justification_id: basis
            for basis in justifications.effective_justifications(
                str(claim_id), knowledge=knowledge
            )
        }

    @staticmethod
    def _historical_basis_exists(
        row: JustificationUndercutterRevision,
        *,
        claim: KnowledgeClaim,
        justifications: KnowledgeJustificationRegistry,
    ) -> bool:
        legacy = justifications.legacy_basis(claim)
        if (
            row.target_justification_id == legacy.justification_id
            and row.target_basis_digest == legacy.digest
        ):
            return True
        for revision in justifications.revisions(row.target_justification_id):
            basis = revision.basis()
            if (
                basis.claim_id == row.target_claim_id
                and basis.claim_digest == row.target_claim_digest
                and basis.digest == row.target_basis_digest
            ):
                return True
        return False

    def _validate_binding(
        self,
        row: JustificationUndercutterRevision,
        *,
        knowledge: KnowledgeLedger,
        justifications: KnowledgeJustificationRegistry,
        require_live_basis: bool,
        require_historical_basis: bool = False,
    ) -> None:
        try:
            claim = knowledge.get(row.target_claim_id)
        except KeyError as exc:
            raise ValueError("undercutter references unknown canonical claim") from exc
        if claim.content_digest != row.target_claim_digest:
            raise ValueError("undercutter cannot rebind canonical claim digest")
        for parent_id in row.parent_claim_ids:
            try:
                knowledge.get(parent_id)
            except KeyError as exc:
                raise ValueError(f"unknown undercutter parent claim: {parent_id}") from exc
        if require_live_basis:
            basis = self._basis_map(
                claim.claim_id,
                knowledge=knowledge,
                justifications=justifications,
            ).get(row.target_justification_id)
            if basis is None or basis.digest != row.target_basis_digest:
                raise ValueError("undercutter target justification is not currently effective")
        if require_historical_basis and not self._historical_basis_exists(
            row,
            claim=claim,
            justifications=justifications,
        ):
            raise ValueError("undercutter target justification basis has no canonical history")

    def targeting_basis(
        self,
        basis: KnowledgeJustificationBasis,
    ) -> tuple[JustificationUndercutterRevision, ...]:
        if not isinstance(basis, KnowledgeJustificationBasis):
            raise TypeError("targeting_basis requires KnowledgeJustificationBasis")
        rows = tuple(
            row
            for row in self.current_revisions(basis.claim_id)
            if row.enabled
            and row.target_justification_id == basis.justification_id
            and row.target_basis_digest == basis.digest
            and row.target_claim_digest == basis.claim_digest
        )
        return tuple(sorted(rows, key=lambda row: row.undercutter_id))

    def _effective_parent_ids(
        self,
        claim_id: str,
        *,
        knowledge: KnowledgeLedger,
        justifications: KnowledgeJustificationRegistry,
    ) -> tuple[str, ...]:
        parents: set[str] = set()
        bases = justifications.effective_justifications(str(claim_id), knowledge=knowledge)
        for basis in bases:
            parents.update(basis.parent_claim_ids)
            for attack in self.targeting_basis(basis):
                parents.update(attack.parent_claim_ids)
        return tuple(sorted(parents))

    def _assert_acyclic(
        self,
        *,
        knowledge: KnowledgeLedger,
        justifications: KnowledgeJustificationRegistry,
    ) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(claim_id: str) -> None:
            if claim_id in visiting:
                raise ValueError("defeasible justification dependency graph contains a cycle")
            if claim_id in visited:
                return
            visiting.add(claim_id)
            for parent_id in self._effective_parent_ids(
                claim_id,
                knowledge=knowledge,
                justifications=justifications,
            ):
                visit(parent_id)
            visiting.remove(claim_id)
            visited.add(claim_id)

        for claim in knowledge.claims():
            visit(claim.claim_id)

    def _register(
        self,
        row: JustificationUndercutterRevision,
        *,
        knowledge: KnowledgeLedger,
        justifications: KnowledgeJustificationRegistry,
        allow_historical_target: bool,
    ) -> JustificationUndercutterRevision:
        if not isinstance(row, JustificationUndercutterRevision):
            raise TypeError("undercutter registry accepts JustificationUndercutterRevision only")
        if not isinstance(knowledge, KnowledgeLedger):
            raise TypeError("undercutter registry requires canonical KnowledgeLedger")
        if not isinstance(justifications, KnowledgeJustificationRegistry):
            raise TypeError("undercutter registry requires KnowledgeJustificationRegistry")

        history = self._revisions.setdefault(row.undercutter_id, [])
        self._validate_binding(
            row,
            knowledge=knowledge,
            justifications=justifications,
            require_live_basis=not history and not allow_historical_target,
            require_historical_basis=not history and allow_historical_target,
        )
        if not history:
            if row.revision != 1:
                self._revisions.pop(row.undercutter_id, None)
                raise ValueError("undercutter revision sequence must start at 1")
            history.append(row)
            try:
                self._assert_acyclic(
                    knowledge=knowledge,
                    justifications=justifications,
                )
            except Exception:
                history.pop()
                self._revisions.pop(row.undercutter_id, None)
                raise
            return row

        current = history[-1]
        binding = (
            row.target_claim_id,
            row.target_claim_digest,
            row.target_justification_id,
            row.target_basis_digest,
        )
        current_binding = (
            current.target_claim_id,
            current.target_claim_digest,
            current.target_justification_id,
            current.target_basis_digest,
        )
        if binding != current_binding:
            raise ValueError("undercutter lineage cannot rebind target basis")
        if row.revision == current.revision:
            if row != current:
                raise ValueError("undercutter revision collision")
            return current
        if row.revision != current.revision + 1:
            raise ValueError("undercutter revision sequence must advance exactly once")
        if row.predecessor_digest != current.digest:
            raise ValueError("undercutter predecessor mismatch")
        history.append(row)
        try:
            self._assert_acyclic(
                knowledge=knowledge,
                justifications=justifications,
            )
        except Exception:
            history.pop()
            raise
        return row

    def register(
        self,
        row: JustificationUndercutterRevision,
        *,
        knowledge: KnowledgeLedger,
        justifications: KnowledgeJustificationRegistry,
    ) -> JustificationUndercutterRevision:
        return self._register(
            row,
            knowledge=knowledge,
            justifications=justifications,
            allow_historical_target=False,
        )

    def evidence_ids_for_claims(self, claim_ids: tuple[str, ...]) -> tuple[str, ...]:
        ids = _ids(tuple(claim_ids), "undercutter scope claim ids")
        evidence_ids: set[str] = set()
        for row in self.current_revisions():
            if row.target_claim_id in ids:
                evidence_ids.update(row.evidence_ids)
        return tuple(sorted(evidence_ids))

    def parent_claim_ids_for_claims(self, claim_ids: tuple[str, ...]) -> tuple[str, ...]:
        ids = _ids(tuple(claim_ids), "undercutter scope claim ids")
        parents: set[str] = set()
        for row in self.current_revisions():
            if row.enabled and row.target_claim_id in ids:
                parents.update(row.parent_claim_ids)
        return tuple(sorted(parents))

    def projection_state(
        self,
        claim_ids: tuple[str, ...],
        *,
        knowledge: KnowledgeLedger,
    ) -> dict[str, Any]:
        ids = _ids(tuple(claim_ids), "undercutter projection claim ids")
        if not ids:
            raise ValueError("undercutter projection requires at least one claim")
        for claim_id in ids:
            knowledge.get(claim_id)
        rows = [
            row.to_state()
            for row in self.current_revisions()
            if row.target_claim_id in ids
        ]
        return {
            "protocol": PROJECTION_PROTOCOL,
            "claim_ids": list(ids),
            "undercutters": rows,
        }

    def projection_digest(
        self,
        claim_ids: tuple[str, ...],
        *,
        knowledge: KnowledgeLedger,
    ) -> str:
        return canonical_digest(self.projection_state(tuple(claim_ids), knowledge=knowledge))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "revisions": [
                row.to_state()
                for undercutter_id in sorted(self._revisions)
                for row in self._revisions[undercutter_id]
            ],
        }

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        knowledge: KnowledgeLedger,
        justifications: KnowledgeJustificationRegistry,
    ) -> "JustificationUndercutterRegistry":
        _unexpected(state, {"protocol", "revisions"}, "knowledge undercutter registry")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported knowledge undercutter protocol")
        parsed: list[JustificationUndercutterRevision] = []
        seen: set[tuple[str, int]] = set()
        for value in state.get("revisions", ()):
            row = JustificationUndercutterRevision.from_state(value)
            key = (row.undercutter_id, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized undercutter revision")
            seen.add(key)
            parsed.append(row)

        registry = cls()
        for row in sorted(parsed, key=lambda item: (item.undercutter_id, item.revision)):
            registry._register(
                row,
                knowledge=knowledge,
                justifications=justifications,
                allow_historical_target=True,
            )
        return registry


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "PROJECTION_PROTOCOL",
    "JustificationUndercutterRevision",
    "JustificationUndercutterRegistry",
)
