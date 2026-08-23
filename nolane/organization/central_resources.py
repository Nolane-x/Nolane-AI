from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

MIGRATED_FROM = "cogcoder.organization.central_resources"


def _positive_int(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if value <= 0:
        raise ValueError(f"{label} must be positive")
    return value


def _reason_evidence(reason: str, evidence_refs: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    reason = str(reason).strip()
    evidence = tuple(str(x).strip() for x in evidence_refs if str(x).strip())
    if not reason:
        raise ValueError("resource mutation reason must be explicit")
    if not evidence:
        raise ValueError("resource mutation requires evidence refs")
    return reason, evidence


@dataclass(frozen=True, slots=True)
class ResourceAllocationReceipt:
    allocation_id: str
    beneficiary: str
    resource: str
    amount: int
    reason: str
    evidence_refs: tuple[str, ...]
    before_available: int
    after_available: int

    def to_state(self) -> dict[str, Any]:
        return {
            "allocation_id": self.allocation_id,
            "beneficiary": self.beneficiary,
            "resource": self.resource,
            "amount": self.amount,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "before_available": self.before_available,
            "after_available": self.after_available,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ResourceAllocationReceipt":
        return cls(
            allocation_id=str(state["allocation_id"]),
            beneficiary=str(state["beneficiary"]),
            resource=str(state["resource"]),
            amount=int(state["amount"]),
            reason=str(state["reason"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            before_available=int(state["before_available"]),
            after_available=int(state["after_available"]),
        )


@dataclass(frozen=True, slots=True)
class ResourceReleaseReceipt:
    release_id: str
    allocation_id: str
    beneficiary: str
    resource: str
    amount: int
    reason: str
    evidence_refs: tuple[str, ...]
    before_leased: int
    after_leased: int
    before_available: int
    after_available: int

    def to_state(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "allocation_id": self.allocation_id,
            "beneficiary": self.beneficiary,
            "resource": self.resource,
            "amount": self.amount,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "before_leased": self.before_leased,
            "after_leased": self.after_leased,
            "before_available": self.before_available,
            "after_available": self.after_available,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ResourceReleaseReceipt":
        return cls(
            release_id=str(state["release_id"]),
            allocation_id=str(state["allocation_id"]),
            beneficiary=str(state["beneficiary"]),
            resource=str(state["resource"]),
            amount=int(state["amount"]),
            reason=str(state["reason"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            before_leased=int(state["before_leased"]),
            after_leased=int(state["after_leased"]),
            before_available=int(state["before_available"]),
            after_available=int(state["after_available"]),
        )


@dataclass(frozen=True, slots=True)
class _LeaseState:
    allocation_id: str
    beneficiary: str
    resource: str
    allocated_amount: int
    remaining_amount: int

    def to_state(self) -> dict[str, Any]:
        return {
            "allocation_id": self.allocation_id,
            "beneficiary": self.beneficiary,
            "resource": self.resource,
            "allocated_amount": self.allocated_amount,
            "remaining_amount": self.remaining_amount,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "_LeaseState":
        return cls(
            str(state["allocation_id"]),
            str(state["beneficiary"]),
            str(state["resource"]),
            int(state["allocated_amount"]),
            int(state["remaining_amount"]),
        )


class CentralResourceArbiter:
    def __init__(self, capacity: Mapping[str, int]) -> None:
        rows: dict[str, int] = {}
        for key, raw in capacity.items():
            name = str(key).strip()
            if not name:
                raise ValueError("resource name must be non-empty")
            rows[name] = _positive_int(raw, f"capacity[{name}]")
        if not rows:
            raise ValueError("at least one resource capacity is required")
        self._capacity = dict(sorted(rows.items()))
        self._available = dict(self._capacity)
        self._leases: dict[str, _LeaseState] = {}
        self._allocation_receipts: list[ResourceAllocationReceipt] = []
        self._release_receipts: list[ResourceReleaseReceipt] = []
        self._allocation_counter = 0
        self._release_counter = 0

    def available(self, resource: str) -> int:
        try:
            return self._available[str(resource)]
        except KeyError as exc:
            raise KeyError(f"unknown resource: {resource}") from exc

    def leased_to(self, beneficiary: str, resource: str) -> int:
        self.available(resource)
        return sum(
            row.remaining_amount
            for row in self._leases.values()
            if row.beneficiary == str(beneficiary) and row.resource == str(resource)
        )

    def allocate(
        self,
        *,
        beneficiary: str,
        resource: str,
        amount: int,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> ResourceAllocationReceipt:
        beneficiary = str(beneficiary).strip()
        resource = str(resource).strip()
        if not beneficiary:
            raise ValueError("resource beneficiary must be explicit")
        amount = _positive_int(amount, "allocation amount")
        reason, evidence = _reason_evidence(reason, evidence_refs)
        before = self.available(resource)
        if amount > before:
            raise ValueError(f"allocation exceeds available {resource}: requested {amount}, available {before}")
        counter = self._allocation_counter + 1
        allocation_id = f"alloc-{counter:08d}"
        after = before - amount
        lease = _LeaseState(allocation_id, beneficiary, resource, amount, amount)
        receipt = ResourceAllocationReceipt(
            allocation_id,
            beneficiary,
            resource,
            amount,
            reason,
            evidence,
            before,
            after,
        )
        self._allocation_counter = counter
        self._available[resource] = after
        self._leases[allocation_id] = lease
        self._allocation_receipts.append(receipt)
        return receipt

    def release(
        self,
        allocation_id: str,
        *,
        amount: int,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> ResourceReleaseReceipt:
        try:
            lease = self._leases[str(allocation_id)]
        except KeyError as exc:
            raise KeyError(f"unknown allocation id: {allocation_id}") from exc
        amount = _positive_int(amount, "release amount")
        reason, evidence = _reason_evidence(reason, evidence_refs)
        if amount > lease.remaining_amount:
            raise ValueError("release exceeds remaining leased amount")
        before_leased = lease.remaining_amount
        after_leased = before_leased - amount
        before_available = self._available[lease.resource]
        after_available = before_available + amount
        if after_available > self._capacity[lease.resource]:
            raise ValueError("release would exceed configured resource capacity")
        counter = self._release_counter + 1
        receipt = ResourceReleaseReceipt(
            f"release-{counter:08d}",
            lease.allocation_id,
            lease.beneficiary,
            lease.resource,
            amount,
            reason,
            evidence,
            before_leased,
            after_leased,
            before_available,
            after_available,
        )
        self._release_counter = counter
        self._available[lease.resource] = after_available
        self._leases[lease.allocation_id] = replace(lease, remaining_amount=after_leased)
        self._release_receipts.append(receipt)
        return receipt

    def to_state(self) -> dict[str, Any]:
        return {
            "capacity": dict(self._capacity),
            "available": dict(self._available),
            "leases": [self._leases[k].to_state() for k in sorted(self._leases)],
            "allocation_receipts": [x.to_state() for x in self._allocation_receipts],
            "release_receipts": [x.to_state() for x in self._release_receipts],
            "allocation_counter": self._allocation_counter,
            "release_counter": self._release_counter,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CentralResourceArbiter":
        arbiter = cls({str(k): int(v) for k, v in state.get("capacity", {}).items()})
        available = {str(k): int(v) for k, v in state.get("available", {}).items()}
        if set(available) != set(arbiter._capacity):
            raise ValueError("resource available-state keys must match capacity keys")
        for key, value in available.items():
            if value < 0 or value > arbiter._capacity[key]:
                raise ValueError("resource available state is out of bounds")
        arbiter._available = available
        for raw in state.get("leases", ()):
            row = _LeaseState.from_state(raw)
            if row.allocation_id in arbiter._leases or row.resource not in arbiter._capacity:
                raise ValueError("invalid resource lease state")
            if row.remaining_amount < 0 or row.remaining_amount > row.allocated_amount:
                raise ValueError("lease remaining amount is invalid")
            arbiter._leases[row.allocation_id] = row
        arbiter._allocation_receipts = [
            ResourceAllocationReceipt.from_state(x) for x in state.get("allocation_receipts", ())
        ]
        arbiter._release_receipts = [
            ResourceReleaseReceipt.from_state(x) for x in state.get("release_receipts", ())
        ]
        arbiter._allocation_counter = int(
            state.get("allocation_counter", len(arbiter._allocation_receipts))
        )
        arbiter._release_counter = int(
            state.get("release_counter", len(arbiter._release_receipts))
        )
        if (
            arbiter._allocation_counter < len(arbiter._allocation_receipts)
            or arbiter._release_counter < len(arbiter._release_receipts)
        ):
            raise ValueError("resource receipt counter is not canonical")
        calculated = dict(arbiter._capacity)
        for lease in arbiter._leases.values():
            calculated[lease.resource] -= lease.remaining_amount
        if calculated != arbiter._available:
            raise ValueError("resource accounting state is inconsistent")
        return arbiter


__all__ = (
    "CentralResourceArbiter",
    "ResourceAllocationReceipt",
    "ResourceReleaseReceipt",
    "MIGRATED_FROM",
)
