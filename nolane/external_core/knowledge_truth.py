from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol

from nolane.core.canonical_digest import canonical_digest

PARENT_COMPONENT_ID = "external.knowledge"
TRUTH_PROTOCOL = "truth-knowledge-v1"
SCOPE_PROJECTION_PROTOCOL = "truth-knowledge-scope-v2"


class KnowledgeRisk(str, Enum):
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"
    CRITICAL = "critical"


class _EvidenceLedgerLike(Protocol):
    def is_active(self, evidence_id: str) -> bool: ...


def _uniq(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    out = tuple(sorted(str(v).strip() for v in values))
    if any(not v for v in out):
        raise ValueError(f"{field} entries must be explicit")
    if len(set(out)) != len(out):
        raise ValueError(f"{field} entries must be unique")
    return out


@dataclass(frozen=True, slots=True)
class KnowledgeClaim:
    claim_id: str
    subject: str
    relation: str
    object: str
    risk: KnowledgeRisk
    evidence_ids: tuple[str, ...]
    parent_claim_ids: tuple[str, ...]
    content_digest: str

    @classmethod
    def create(cls, *, claim_id: str, subject: str, relation: str, object: str,
               risk: KnowledgeRisk = KnowledgeRisk.STANDARD, evidence_ids: tuple[str, ...] = (),
               parent_claim_ids: tuple[str, ...] = ()) -> "KnowledgeClaim":
        fields = {
            "claim_id": str(claim_id).strip(), "subject": str(subject).strip(),
            "relation": str(relation).strip(), "object": str(object).strip(),
        }
        if any(not value for value in fields.values()):
            raise ValueError("knowledge claim identity and proposition fields must be explicit")
        evidence_ids = _uniq(tuple(evidence_ids), "evidence_ids")
        parent_claim_ids = _uniq(tuple(parent_claim_ids), "parent_claim_ids")
        if fields["claim_id"] in parent_claim_ids:
            raise ValueError("knowledge claim cannot depend on itself")
        payload = {
            **fields, "risk": KnowledgeRisk(risk).value,
            "evidence_ids": list(evidence_ids), "parent_claim_ids": list(parent_claim_ids),
        }
        return cls(
            fields["claim_id"], fields["subject"], fields["relation"], fields["object"],
            KnowledgeRisk(risk), evidence_ids, parent_claim_ids, canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id, "subject": self.subject, "relation": self.relation,
            "object": self.object, "risk": self.risk.value, "evidence_ids": list(self.evidence_ids),
            "parent_claim_ids": list(self.parent_claim_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "content_digest": self.content_digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "KnowledgeClaim":
        row = cls.create(
            claim_id=str(state["claim_id"]), subject=str(state["subject"]),
            relation=str(state["relation"]), object=str(state["object"]),
            risk=KnowledgeRisk(str(state["risk"])),
            evidence_ids=tuple(str(x) for x in state.get("evidence_ids", ())),
            parent_claim_ids=tuple(str(x) for x in state.get("parent_claim_ids", ())),
        )
        if str(state["content_digest"]) != row.content_digest:
            raise ValueError("knowledge claim content digest mismatch")
        return row


class KnowledgeLedger:
    """Immutable proposition/derivation truth protocol under ``external.knowledge``.

    The parent Knowledge component still owns retrieval/reusable knowledge fabric. This ledger only
    owns proposition identity and derivation lineage required by truth closure; it never decides
    epistemic truth.
    """

    def __init__(self) -> None:
        self._claims: dict[str, KnowledgeClaim] = {}

    def add(self, claim: KnowledgeClaim) -> KnowledgeClaim:
        previous = self._claims.get(claim.claim_id)
        if previous is not None:
            if previous != claim:
                raise ValueError("knowledge claim id collision")
            return previous
        missing = tuple(parent for parent in claim.parent_claim_ids if parent not in self._claims)
        if missing:
            raise ValueError(f"unknown parent knowledge claim(s): {','.join(missing)}")
        self._claims[claim.claim_id] = claim
        return claim

    def get(self, claim_id: str) -> KnowledgeClaim:
        try:
            return self._claims[str(claim_id)]
        except KeyError as exc:
            raise KeyError(f"unknown knowledge claim: {claim_id}") from exc

    def claims(self) -> tuple[KnowledgeClaim, ...]:
        return tuple(self._claims[key] for key in sorted(self._claims))

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def impacted_claim_ids(self, evidence: _EvidenceLedgerLike) -> tuple[str, ...]:
        impacted = {
            claim.claim_id for claim in self._claims.values()
            if any(not evidence.is_active(evidence_id) for evidence_id in claim.evidence_ids)
        }
        changed = True
        while changed:
            changed = False
            for claim in self._claims.values():
                if claim.claim_id not in impacted and any(parent in impacted for parent in claim.parent_claim_ids):
                    impacted.add(claim.claim_id)
                    changed = True
        return tuple(sorted(impacted))

    def lineage_claim_ids(self, claim_id: str) -> tuple[str, ...]:
        """Return the target plus every transitive parent in canonical order."""
        target = self.get(str(claim_id))
        seen: set[str] = set()
        pending = [target.claim_id]
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            claim = self.get(current)
            seen.add(claim.claim_id)
            pending.extend(claim.parent_claim_ids)
        return tuple(sorted(seen))

    def truth_scope_claim_ids(self, claim_id: str) -> tuple[str, ...]:
        """Derive the fixed-point lineage + competing-proposition neighborhood for a target."""
        scope = set(self.lineage_claim_ids(str(claim_id)))
        changed = True
        while changed:
            changed = False
            proposition_keys = {
                (self.get(current).subject, self.get(current).relation)
                for current in scope
            }
            competitors = {
                row.claim_id for row in self._claims.values()
                if (row.subject, row.relation) in proposition_keys
            }
            expanded = set(scope)
            for competitor in competitors:
                expanded.update(self.lineage_claim_ids(competitor))
            if expanded != scope:
                scope = expanded
                changed = True
        return tuple(sorted(scope))

    def evidence_ids_for_claims(self, claim_ids: tuple[str, ...]) -> tuple[str, ...]:
        ids = _uniq(tuple(claim_ids), "scope claim ids")
        if not ids:
            raise ValueError("scope claim ids must not be empty")
        evidence_ids: set[str] = set()
        for claim_id in ids:
            evidence_ids.update(self.get(claim_id).evidence_ids)
        return tuple(sorted(evidence_ids))

    def scoped_state(self, claim_ids: tuple[str, ...]) -> dict[str, Any]:
        ids = _uniq(tuple(claim_ids), "scope claim ids")
        if not ids:
            raise ValueError("scope claim ids must not be empty")
        rows = [self.get(claim_id).to_state() for claim_id in ids]
        return {"protocol": SCOPE_PROJECTION_PROTOCOL, "claims": rows}

    def scoped_digest(self, claim_ids: tuple[str, ...]) -> str:
        return canonical_digest(self.scoped_state(claim_ids))

    def to_state(self) -> dict[str, Any]:
        return {"protocol": TRUTH_PROTOCOL, "claims": [row.to_state() for row in self.claims()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "KnowledgeLedger":
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported knowledge protocol")

        parsed: dict[str, KnowledgeClaim] = {}
        seen: set[str] = set()
        for value in state.get("claims", ()):
            row = KnowledgeClaim.from_state(value)
            if row.claim_id in seen:
                raise ValueError("duplicate serialized knowledge claim id")
            seen.add(row.claim_id)
            parsed[row.claim_id] = row

        missing = sorted({
            parent
            for row in parsed.values()
            for parent in row.parent_claim_ids
            if parent not in parsed
        })
        if missing:
            raise ValueError(f"unknown parent knowledge claim(s): {','.join(missing)}")

        ledger = cls()
        pending = dict(parsed)
        while pending:
            ready = [
                row for row in pending.values()
                if all(parent in ledger._claims for parent in row.parent_claim_ids)
            ]
            if not ready:
                raise ValueError("knowledge derivation graph contains a cycle")
            for row in sorted(ready, key=lambda item: item.claim_id):
                ledger.add(row)
                pending.pop(row.claim_id)
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID", "TRUTH_PROTOCOL", "SCOPE_PROJECTION_PROTOCOL", "KnowledgeRisk",
    "KnowledgeClaim", "KnowledgeLedger",
)
