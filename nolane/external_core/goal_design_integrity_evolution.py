"""Deterministic authority for Goal/Design integrity-contract evolution.

An exact predecessor digest proves lineage, not permission to rewrite intent.
This protocol adds a provider-neutral, content-addressed evolution receipt that
binds the predecessor, successor, deterministic semantic delta, provenance,
freshness and calibrated confidence. Runtime restore can therefore re-verify
revision authority after restart without trusting serialized pointers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .goal_design import stable_digest
from .goal_design_integrity import GoalIntegrityContract

__version__ = "0.1.0"

EVOLUTION_RECEIPT_SCHEMA_VERSION = 1
EXPLICIT_EVOLUTION_TRUST = "explicit_evolution_authority"
LEGACY_UNATTESTED_TRUST = "legacy_unattested"
_MAX_TEXT = 4096
_MAX_REF = 512
_MAX_REFS = 64


def _text(name: str, value: Any, *, limit: int = _MAX_TEXT) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    if len(normalized) > limit:
        raise ValueError(f"{name} exceeds bounded field limit")
    return normalized


def _refs(name: str, values: Iterable[str], *, required: bool = False) -> tuple[str, ...]:
    normalized = tuple(sorted({_text(name, value, limit=_MAX_REF) for value in values}))
    if len(normalized) > _MAX_REFS:
        raise ValueError(f"{name} exceeds bounded reference count")
    if required and not normalized:
        raise ValueError(f"{name} requires at least one reference")
    return normalized


def _digest_map(items: Iterable[Any], identity_field: str) -> dict[str, str]:
    return {
        _text(identity_field, getattr(item, identity_field), limit=_MAX_REF): str(item.digest)
        for item in items
    }


@dataclass(frozen=True)
class GoalIntegrityEvolutionDelta:
    """Canonical structural delta between two immutable integrity contracts."""

    goal_id: str
    predecessor_digest: str
    successor_digest: str
    added_clause_ids: tuple[str, ...]
    removed_clause_ids: tuple[str, ...]
    changed_clause_ids: tuple[str, ...]
    added_metric_ids: tuple[str, ...]
    removed_metric_ids: tuple[str, ...]
    changed_metric_ids: tuple[str, ...]

    @property
    def digest(self) -> str:
        return stable_digest(
            {
                "goal_integrity_evolution_delta": {
                    "goal_id": self.goal_id,
                    "predecessor_digest": self.predecessor_digest,
                    "successor_digest": self.successor_digest,
                    "added_clause_ids": self.added_clause_ids,
                    "removed_clause_ids": self.removed_clause_ids,
                    "changed_clause_ids": self.changed_clause_ids,
                    "added_metric_ids": self.added_metric_ids,
                    "removed_metric_ids": self.removed_metric_ids,
                    "changed_metric_ids": self.changed_metric_ids,
                }
            }
        )


def assess_goal_integrity_evolution(
    predecessor: GoalIntegrityContract,
    successor: GoalIntegrityContract,
) -> GoalIntegrityEvolutionDelta:
    """Return the same deterministic delta for identical sealed contracts."""

    if predecessor.goal_id != successor.goal_id:
        raise ValueError("Goal/Design integrity evolution cannot cross goal authority")
    if predecessor.digest == successor.digest:
        raise ValueError("Goal/Design integrity evolution requires a changed contract")

    old_clauses = _digest_map(predecessor.clauses, "clause_id")
    new_clauses = _digest_map(successor.clauses, "clause_id")
    old_metrics = _digest_map(predecessor.metric_bindings, "metric_id")
    new_metrics = _digest_map(successor.metric_bindings, "metric_id")

    def delta(old: Mapping[str, str], new: Mapping[str, str]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        added = tuple(sorted(set(new) - set(old)))
        removed = tuple(sorted(set(old) - set(new)))
        changed = tuple(sorted(key for key in set(old) & set(new) if old[key] != new[key]))
        return added, removed, changed

    added_clauses, removed_clauses, changed_clauses = delta(old_clauses, new_clauses)
    added_metrics, removed_metrics, changed_metrics = delta(old_metrics, new_metrics)
    return GoalIntegrityEvolutionDelta(
        goal_id=predecessor.goal_id,
        predecessor_digest=predecessor.digest,
        successor_digest=successor.digest,
        added_clause_ids=added_clauses,
        removed_clause_ids=removed_clauses,
        changed_clause_ids=changed_clauses,
        added_metric_ids=added_metrics,
        removed_metric_ids=removed_metrics,
        changed_metric_ids=changed_metrics,
    )


@dataclass(frozen=True)
class GoalIntegrityEvolutionReceipt:
    """Tamper-evident authority permitting exactly one contract transition."""

    receipt_id: str
    goal_id: str
    predecessor_digest: str
    successor_digest: str
    delta_digest: str
    authority_ref: str
    reason: str
    source_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    freshness_ref: str
    confidence_milli: int
    trust_label: str = EXPLICIT_EVOLUTION_TRUST

    def __post_init__(self) -> None:
        for field in (
            "receipt_id",
            "goal_id",
            "predecessor_digest",
            "successor_digest",
            "delta_digest",
            "authority_ref",
            "freshness_ref",
        ):
            object.__setattr__(
                self,
                field,
                _text(field, getattr(self, field), limit=_MAX_REF),
            )
        object.__setattr__(self, "reason", _text("reason", self.reason))
        object.__setattr__(self, "source_refs", _refs("source_ref", self.source_refs, required=True))
        object.__setattr__(self, "evidence_refs", _refs("evidence_ref", self.evidence_refs, required=True))
        confidence = int(self.confidence_milli)
        if confidence < 0 or confidence > 1000:
            raise ValueError("confidence_milli must be between 0 and 1000")
        object.__setattr__(self, "confidence_milli", confidence)
        trust = _text("trust_label", self.trust_label, limit=_MAX_REF)
        if trust != EXPLICIT_EVOLUTION_TRUST:
            raise ValueError("unsupported Goal/Design integrity evolution trust label")
        object.__setattr__(self, "trust_label", trust)


def _receipt_payload(receipt: GoalIntegrityEvolutionReceipt) -> dict[str, Any]:
    return {
        "schema_version": EVOLUTION_RECEIPT_SCHEMA_VERSION,
        "goal_id": receipt.goal_id,
        "predecessor_digest": receipt.predecessor_digest,
        "successor_digest": receipt.successor_digest,
        "delta_digest": receipt.delta_digest,
        "authority_ref": receipt.authority_ref,
        "reason": receipt.reason,
        "source_refs": receipt.source_refs,
        "evidence_refs": receipt.evidence_refs,
        "freshness_ref": receipt.freshness_ref,
        "confidence_milli": receipt.confidence_milli,
        "trust_label": receipt.trust_label,
    }


def expected_goal_integrity_evolution_receipt_id(receipt: GoalIntegrityEvolutionReceipt) -> str:
    return stable_digest({"goal_integrity_evolution_receipt": _receipt_payload(receipt)})


def mint_goal_integrity_evolution_receipt(
    *,
    predecessor: GoalIntegrityContract,
    successor: GoalIntegrityContract,
    authority_ref: str,
    reason: str,
    source_refs: Iterable[str],
    evidence_refs: Iterable[str],
    freshness_ref: str,
    confidence_milli: int = 1000,
) -> GoalIntegrityEvolutionReceipt:
    """Mint explicit authority for one exact, deterministic contract revision."""

    delta = assess_goal_integrity_evolution(predecessor, successor)
    provisional = GoalIntegrityEvolutionReceipt(
        receipt_id="pending",
        goal_id=predecessor.goal_id,
        predecessor_digest=predecessor.digest,
        successor_digest=successor.digest,
        delta_digest=delta.digest,
        authority_ref=authority_ref,
        reason=reason,
        source_refs=tuple(source_refs),
        evidence_refs=tuple(evidence_refs),
        freshness_ref=freshness_ref,
        confidence_milli=confidence_milli,
    )
    return GoalIntegrityEvolutionReceipt(
        **{
            **provisional.__dict__,
            "receipt_id": expected_goal_integrity_evolution_receipt_id(provisional),
        }
    )


def verify_goal_integrity_evolution_receipt(
    receipt: GoalIntegrityEvolutionReceipt,
    *,
    predecessor: GoalIntegrityContract,
    successor: GoalIntegrityContract,
) -> GoalIntegrityEvolutionDelta:
    """Fail closed unless the receipt authorizes exactly this transition."""

    delta = assess_goal_integrity_evolution(predecessor, successor)
    if receipt.goal_id != predecessor.goal_id:
        raise ValueError("Goal/Design evolution receipt goal does not bind the transition")
    if receipt.predecessor_digest != predecessor.digest:
        raise ValueError("Goal/Design evolution receipt predecessor mismatch")
    if receipt.successor_digest != successor.digest:
        raise ValueError("Goal/Design evolution receipt successor mismatch")
    if receipt.delta_digest != delta.digest:
        raise ValueError("Goal/Design evolution receipt delta mismatch")
    expected = expected_goal_integrity_evolution_receipt_id(receipt)
    if receipt.receipt_id != expected:
        raise ValueError("Goal/Design evolution receipt identity digest mismatch")
    return delta


def goal_integrity_evolution_receipt_to_state(
    receipt: GoalIntegrityEvolutionReceipt,
) -> dict[str, Any]:
    return {"receipt_id": receipt.receipt_id, **_receipt_payload(receipt)}


def goal_integrity_evolution_receipt_from_state(
    state: Mapping[str, Any],
) -> GoalIntegrityEvolutionReceipt:
    if int(state.get("schema_version", EVOLUTION_RECEIPT_SCHEMA_VERSION)) != EVOLUTION_RECEIPT_SCHEMA_VERSION:
        raise ValueError("unsupported Goal/Design integrity evolution receipt schema")
    return GoalIntegrityEvolutionReceipt(
        receipt_id=str(state["receipt_id"]),
        goal_id=str(state["goal_id"]),
        predecessor_digest=str(state["predecessor_digest"]),
        successor_digest=str(state["successor_digest"]),
        delta_digest=str(state["delta_digest"]),
        authority_ref=str(state["authority_ref"]),
        reason=str(state["reason"]),
        source_refs=tuple(str(value) for value in state.get("source_refs", ())),
        evidence_refs=tuple(str(value) for value in state.get("evidence_refs", ())),
        freshness_ref=str(state["freshness_ref"]),
        confidence_milli=int(state["confidence_milli"]),
        trust_label=str(state.get("trust_label", EXPLICIT_EVOLUTION_TRUST)),
    )


__all__ = [
    "EVOLUTION_RECEIPT_SCHEMA_VERSION",
    "EXPLICIT_EVOLUTION_TRUST",
    "LEGACY_UNATTESTED_TRUST",
    "GoalIntegrityEvolutionDelta",
    "GoalIntegrityEvolutionReceipt",
    "assess_goal_integrity_evolution",
    "expected_goal_integrity_evolution_receipt_id",
    "goal_integrity_evolution_receipt_from_state",
    "goal_integrity_evolution_receipt_to_state",
    "mint_goal_integrity_evolution_receipt",
    "verify_goal_integrity_evolution_receipt",
]
