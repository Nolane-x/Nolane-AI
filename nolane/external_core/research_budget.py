from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


class ResearchBudgetCategory(str, Enum):
    EXPLORE = "explore"
    FALSIFY = "falsify"
    VERIFY = "verify"
    REPLICATE = "replicate"
    INTEGRATE = "integrate"


_CATEGORIES = tuple(category.value for category in ResearchBudgetCategory)


@dataclass(frozen=True, slots=True)
class ResearchBudgetReceipt:
    receipt_id: str
    sequence: int
    category: ResearchBudgetCategory
    units: int
    reason: str
    evidence_refs: tuple[str, ...]
    previous_receipt_digest: str
    remaining_category_units: int
    remaining_total_units: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "category": self.category.value,
            "units": self.units,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "previous_receipt_digest": self.previous_receipt_digest,
            "remaining_category_units": self.remaining_category_units,
            "remaining_total_units": self.remaining_total_units,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        category: ResearchBudgetCategory | str,
        units: int,
        reason: str,
        evidence_refs: tuple[str, ...],
        previous_receipt_digest: str,
        remaining_category_units: int,
        remaining_total_units: int,
    ) -> "ResearchBudgetReceipt":
        seq = _non_negative_int(sequence, "sequence")
        if seq < 1:
            raise ValueError("research budget receipt sequence must start at one")
        spend_units = _non_negative_int(units, "units")
        if spend_units < 1:
            raise ValueError("research budget spend units must be positive")
        remaining_category = _non_negative_int(
            remaining_category_units, "remaining_category_units"
        )
        remaining_total = _non_negative_int(remaining_total_units, "remaining_total_units")
        evidence = _unique_explicit(evidence_refs, "research budget evidence ref")
        if not evidence:
            raise ValueError("research budget spend requires evidence refs")
        payload = {
            "sequence": seq,
            "category": ResearchBudgetCategory(category).value,
            "units": spend_units,
            "reason": _explicit(reason, "research budget spend reason"),
            "evidence_refs": list(evidence),
            "previous_receipt_digest": str(previous_receipt_digest),
            "remaining_category_units": remaining_category,
            "remaining_total_units": remaining_total,
        }
        digest = canonical_digest(payload)
        return cls(
            receipt_id="research-budget-spend-" + digest[:24],
            sequence=seq,
            category=ResearchBudgetCategory(payload["category"]),
            units=spend_units,
            reason=payload["reason"],
            evidence_refs=evidence,
            previous_receipt_digest=payload["previous_receipt_digest"],
            remaining_category_units=remaining_category,
            remaining_total_units=remaining_total,
            digest=digest,
        )


class ResearchBudget:
    """Finite research work allocation.

    Units are scheduling resources only. They are never epistemic confidence and
    cannot strengthen a Truth or Assurance disposition.
    """

    def __init__(self, *, total_units: int, allocations: Mapping[str, int]) -> None:
        total = _non_negative_int(total_units, "total_units")
        normalized: dict[ResearchBudgetCategory, int] = {}
        keys = {str(key) for key in allocations}
        if keys != set(_CATEGORIES):
            raise ValueError(
                "research budget categories must be exactly explore, falsify, verify, replicate, integrate"
            )
        for category in ResearchBudgetCategory:
            normalized[category] = _non_negative_int(
                allocations[category.value], f"allocation:{category.value}"
            )
        if sum(normalized.values()) != total:
            raise ValueError("research budget allocations must sum exactly to total_units")
        self.total_units = total
        self.allocations = normalized
        self._receipts: list[ResearchBudgetReceipt] = []
        self._spent: dict[ResearchBudgetCategory, int] = {
            category: 0 for category in ResearchBudgetCategory
        }

    @classmethod
    def create(cls, *, total_units: int, allocations: Mapping[str, int]) -> "ResearchBudget":
        return cls(total_units=total_units, allocations=allocations)

    @property
    def remaining_total_units(self) -> int:
        return self.total_units - sum(self._spent.values())

    def remaining_for(self, category: ResearchBudgetCategory | str) -> int:
        key = ResearchBudgetCategory(category)
        return self.allocations[key] - self._spent[key]

    @property
    def receipts(self) -> tuple[ResearchBudgetReceipt, ...]:
        return tuple(self._receipts)

    @property
    def digest(self) -> str:
        return canonical_digest(self._payload())

    def spend(
        self,
        *,
        category: ResearchBudgetCategory | str,
        units: int,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> ResearchBudgetReceipt:
        key = ResearchBudgetCategory(category)
        amount = _non_negative_int(units, "units")
        if amount < 1:
            raise ValueError("research budget spend units must be positive")
        if amount > self.remaining_for(key) or amount > self.remaining_total_units:
            raise ValueError("research budget category or total budget exhausted")
        previous = self._receipts[-1].digest if self._receipts else ""
        remaining_category = self.remaining_for(key) - amount
        remaining_total = self.remaining_total_units - amount
        row = ResearchBudgetReceipt.create(
            sequence=len(self._receipts) + 1,
            category=key,
            units=amount,
            reason=reason,
            evidence_refs=evidence_refs,
            previous_receipt_digest=previous,
            remaining_category_units=remaining_category,
            remaining_total_units=remaining_total,
        )
        self._spent[key] += amount
        self._receipts.append(row)
        return row

    def _payload(self) -> dict[str, Any]:
        return {
            "total_units": self.total_units,
            "allocations": {
                category.value: self.allocations[category]
                for category in ResearchBudgetCategory
            },
            "receipts": [row.to_state() for row in self._receipts],
        }

    def to_state(self) -> dict[str, Any]:
        payload = self._payload()
        return {**payload, "digest": canonical_digest(payload)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ResearchBudget":
        allocations_raw = state.get("allocations", {})
        if not isinstance(allocations_raw, Mapping):
            raise ValueError("research budget allocations must be an object")
        budget = cls.create(
            total_units=state["total_units"],
            allocations={str(key): value for key, value in allocations_raw.items()},
        )
        for raw in state.get("receipts", ()):
            if not isinstance(raw, Mapping):
                raise ValueError("research budget receipt state must be an object")
            replayed = budget.spend(
                category=str(raw["category"]),
                units=raw["units"],
                reason=str(raw["reason"]),
                evidence_refs=tuple(str(x) for x in raw.get("evidence_refs", ())),
            )
            if replayed.to_state() != dict(raw):
                raise ValueError("research budget receipt replay mismatch")
        expected_digest = budget.digest
        if str(state.get("digest", "")) != expected_digest:
            raise ValueError("research budget digest mismatch")
        return budget


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"research budget {label} must be an integer, not bool")
    if value < 0:
        raise ValueError(f"research budget {label} must be non-negative")
    return value


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


def _unique_explicit(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    rows = tuple(str(value) for value in values)
    if any(not value.strip() for value in rows):
        raise ValueError(f"{label} must be explicit")
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(rows))


__all__ = (
    "ResearchBudget",
    "ResearchBudgetCategory",
    "ResearchBudgetReceipt",
)
