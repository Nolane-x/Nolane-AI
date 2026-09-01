from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord


@dataclass(frozen=True, slots=True)
class LearningEvidenceLease:
    sequence: int
    lease_id: str
    subject_kind: str
    subject_id: str
    operation_class: str
    producer_agent_id: str
    verifier_agent_id: str
    evidence: EvidenceRecord
    subject_digest: str
    single_use: bool
    event_anchor_id: str | None
    digest: str

    def __post_init__(self) -> None:
        if int(self.sequence) <= 0:
            raise ValueError("learning evidence lease sequence must be positive")
        for label, value in (
            ("lease id", self.lease_id),
            ("subject kind", self.subject_kind),
            ("subject id", self.subject_id),
            ("operation class", self.operation_class),
            ("producer agent", self.producer_agent_id),
            ("verifier agent", self.verifier_agent_id),
            ("subject digest", self.subject_digest),
        ):
            if not str(value).strip():
                raise ValueError(f"learning evidence lease {label} must be explicit")
        if self.event_anchor_id is not None and not str(self.event_anchor_id).strip():
            raise ValueError("learning evidence lease event anchor must be non-empty when supplied")
        if self.verifier_agent_id != self.evidence.verifier_agent_id:
            raise ValueError("learning evidence lease verifier must match evidence verifier")

    @property
    def evidence_id(self) -> str:
        return self.evidence.evidence_id

    @property
    def evidence_digest(self) -> str:
        return canonical_digest(self.evidence.to_state())

    def binding_payload(self) -> dict[str, Any]:
        return {
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "operation_class": self.operation_class,
            "producer_agent_id": self.producer_agent_id,
            "verifier_agent_id": self.verifier_agent_id,
            "evidence": self.evidence.to_state(),
            "subject_digest": self.subject_digest,
            "single_use": self.single_use,
            "event_anchor_id": self.event_anchor_id,
        }

    def payload(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "lease_id": self.lease_id,
            **self.binding_payload(),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "LearningEvidenceLease":
        row = cls(
            sequence=int(state["sequence"]),
            lease_id=str(state["lease_id"]),
            subject_kind=str(state["subject_kind"]),
            subject_id=str(state["subject_id"]),
            operation_class=str(state["operation_class"]),
            producer_agent_id=str(state["producer_agent_id"]),
            verifier_agent_id=str(state["verifier_agent_id"]),
            evidence=EvidenceRecord.from_state(state["evidence"]),
            subject_digest=str(state["subject_digest"]),
            single_use=bool(state.get("single_use", True)),
            event_anchor_id=None if state.get("event_anchor_id") is None else str(state["event_anchor_id"]),
            digest=str(state["digest"]),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("learning evidence lease digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class LearningEvidenceUseReceipt:
    sequence: int
    receipt_id: str
    lease_id: str
    subject_kind: str
    subject_id: str
    operation_class: str
    producer_agent_id: str
    verifier_agent_id: str
    evidence_id: str
    evidence_digest: str
    subject_digest: str
    use_ref: str
    digest: str

    def __post_init__(self) -> None:
        if int(self.sequence) <= 0:
            raise ValueError("learning evidence use sequence must be positive")
        for label, value in (
            ("receipt id", self.receipt_id),
            ("lease id", self.lease_id),
            ("subject kind", self.subject_kind),
            ("subject id", self.subject_id),
            ("operation class", self.operation_class),
            ("producer agent", self.producer_agent_id),
            ("verifier agent", self.verifier_agent_id),
            ("evidence id", self.evidence_id),
            ("evidence digest", self.evidence_digest),
            ("subject digest", self.subject_digest),
            ("use ref", self.use_ref),
        ):
            if not str(value).strip():
                raise ValueError(f"learning evidence use {label} must be explicit")

    def payload(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "receipt_id": self.receipt_id,
            "lease_id": self.lease_id,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "operation_class": self.operation_class,
            "producer_agent_id": self.producer_agent_id,
            "verifier_agent_id": self.verifier_agent_id,
            "evidence_id": self.evidence_id,
            "evidence_digest": self.evidence_digest,
            "subject_digest": self.subject_digest,
            "use_ref": self.use_ref,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "LearningEvidenceUseReceipt":
        row = cls(
            sequence=int(state["sequence"]),
            receipt_id=str(state["receipt_id"]),
            lease_id=str(state["lease_id"]),
            subject_kind=str(state["subject_kind"]),
            subject_id=str(state["subject_id"]),
            operation_class=str(state["operation_class"]),
            producer_agent_id=str(state["producer_agent_id"]),
            verifier_agent_id=str(state["verifier_agent_id"]),
            evidence_id=str(state["evidence_id"]),
            evidence_digest=str(state["evidence_digest"]),
            subject_digest=str(state["subject_digest"]),
            use_ref=str(state["use_ref"]),
            digest=str(state["digest"]),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("learning evidence use receipt digest mismatch")
        return row


class LearningEvidenceAuthority:
    """B-owned semantic authority that binds external evidence to one exact learning operation."""

    def __init__(
        self,
        *,
        leases: tuple[LearningEvidenceLease, ...] = (),
        uses: tuple[LearningEvidenceUseReceipt, ...] = (),
        lease_counter: int = 0,
        use_counter: int = 0,
    ) -> None:
        self._leases: dict[str, LearningEvidenceLease] = {}
        self._binding_index: dict[str, str] = {}
        self._uses: dict[str, LearningEvidenceUseReceipt] = {}
        self._uses_by_lease: dict[str, list[LearningEvidenceUseReceipt]] = {}
        self._lease_counter = int(lease_counter)
        self._use_counter = int(use_counter)

        for lease in sorted(leases, key=lambda row: row.sequence):
            self._restore_lease(lease)
        for receipt in sorted(uses, key=lambda row: row.sequence):
            self._restore_use(receipt)
        self._validate_ledger_shape()

    @staticmethod
    def _clean(evidence: EvidenceRecord) -> bool:
        return bool(evidence.passed) and int(evidence.false_accepts) == 0 and int(evidence.regressions) == 0

    @classmethod
    def _validate_semantic_authority(cls, *, producer_agent_id: str, evidence: EvidenceRecord) -> None:
        if not cls._clean(evidence):
            raise PermissionError("positive learning authority requires clean evidence")
        if evidence.verifier_agent_id == str(producer_agent_id):
            raise PermissionError("positive learning authority requires an independent verifier")

    @staticmethod
    def _normalize_required(value: str, label: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError(f"learning evidence {label} must be explicit")
        return normalized

    @staticmethod
    def _binding_payload(
        *,
        subject_kind: str,
        subject_id: str,
        operation_class: str,
        producer_agent_id: str,
        evidence: EvidenceRecord,
        subject_digest: str,
        single_use: bool,
        event_anchor_id: str | None,
    ) -> dict[str, Any]:
        return {
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "operation_class": operation_class,
            "producer_agent_id": producer_agent_id,
            "verifier_agent_id": evidence.verifier_agent_id,
            "evidence": evidence.to_state(),
            "subject_digest": subject_digest,
            "single_use": bool(single_use),
            "event_anchor_id": event_anchor_id,
        }

    @staticmethod
    def _canonical_lease_id(binding_payload: Mapping[str, Any]) -> str:
        return "learning-evidence-" + canonical_digest(dict(binding_payload))[:24]

    def issue(
        self,
        *,
        subject_kind: str,
        subject_id: str,
        operation_class: str,
        producer_agent_id: str,
        evidence: EvidenceRecord,
        subject_digest: str,
        single_use: bool = True,
        event_anchor_id: str | None = None,
    ) -> LearningEvidenceLease:
        subject_kind = self._normalize_required(subject_kind, "subject kind")
        subject_id = self._normalize_required(subject_id, "subject id")
        operation_class = self._normalize_required(operation_class, "operation class")
        producer_agent_id = self._normalize_required(producer_agent_id, "producer agent")
        subject_digest = self._normalize_required(subject_digest, "subject digest")
        if event_anchor_id is not None:
            event_anchor_id = self._normalize_required(event_anchor_id, "event anchor")
        self._validate_semantic_authority(producer_agent_id=producer_agent_id, evidence=evidence)
        binding = self._binding_payload(
            subject_kind=subject_kind,
            subject_id=subject_id,
            operation_class=operation_class,
            producer_agent_id=producer_agent_id,
            evidence=evidence,
            subject_digest=subject_digest,
            single_use=single_use,
            event_anchor_id=event_anchor_id,
        )
        binding_digest = canonical_digest(binding)
        lease_id = self._canonical_lease_id(binding)
        existing_id = self._binding_index.get(binding_digest)
        if existing_id is not None:
            existing = self._leases[existing_id]
            if existing.lease_id != lease_id or existing.binding_payload() != binding:
                raise ValueError("learning evidence canonical binding cannot be rebound")
            return existing
        if lease_id in self._leases:
            raise ValueError("learning evidence lease id collision or rebinding")
        self._lease_counter += 1
        payload = {"sequence": self._lease_counter, "lease_id": lease_id, **binding}
        lease = LearningEvidenceLease(
            sequence=self._lease_counter,
            lease_id=lease_id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            operation_class=operation_class,
            producer_agent_id=producer_agent_id,
            verifier_agent_id=evidence.verifier_agent_id,
            evidence=evidence,
            subject_digest=subject_digest,
            single_use=bool(single_use),
            event_anchor_id=event_anchor_id,
            digest=canonical_digest(payload),
        )
        self._leases[lease_id] = lease
        self._binding_index[binding_digest] = lease_id
        return lease

    def lease(self, lease_id: str) -> LearningEvidenceLease:
        try:
            return self._leases[str(lease_id)]
        except KeyError as exc:
            raise KeyError(f"unknown learning evidence lease: {lease_id}") from exc

    def uses_for(self, lease_id: str) -> tuple[LearningEvidenceUseReceipt, ...]:
        self.lease(lease_id)
        return tuple(self._uses_by_lease.get(str(lease_id), ()))

    @staticmethod
    def _matches(
        lease: LearningEvidenceLease,
        *,
        subject_kind: str,
        subject_id: str,
        operation_class: str,
        producer_agent_id: str,
        evidence: EvidenceRecord,
        subject_digest: str,
    ) -> bool:
        return (
            lease.subject_kind == str(subject_kind)
            and lease.subject_id == str(subject_id)
            and lease.operation_class == str(operation_class)
            and lease.producer_agent_id == str(producer_agent_id)
            and lease.verifier_agent_id == evidence.verifier_agent_id
            and lease.evidence_id == evidence.evidence_id
            and lease.evidence_digest == canonical_digest(evidence.to_state())
            and lease.subject_digest == str(subject_digest)
        )

    def require(
        self,
        lease_id: str,
        *,
        subject_kind: str,
        subject_id: str,
        operation_class: str,
        producer_agent_id: str,
        evidence: EvidenceRecord,
        subject_digest: str,
    ) -> LearningEvidenceLease:
        lease = self.lease(lease_id)
        if not self._matches(
            lease,
            subject_kind=subject_kind,
            subject_id=subject_id,
            operation_class=operation_class,
            producer_agent_id=producer_agent_id,
            evidence=evidence,
            subject_digest=subject_digest,
        ):
            raise PermissionError("learning evidence lease does not authorize exact learning operation")
        self._validate_semantic_authority(producer_agent_id=lease.producer_agent_id, evidence=lease.evidence)
        if lease.single_use and self._uses_by_lease.get(lease.lease_id):
            raise PermissionError("single-use learning evidence lease is already consumed")
        return lease

    def consume(
        self,
        lease_id: str,
        *,
        subject_kind: str,
        subject_id: str,
        operation_class: str,
        producer_agent_id: str,
        evidence: EvidenceRecord,
        subject_digest: str,
        use_ref: str,
    ) -> LearningEvidenceUseReceipt:
        lease = self.require(
            lease_id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            operation_class=operation_class,
            producer_agent_id=producer_agent_id,
            evidence=evidence,
            subject_digest=subject_digest,
        )
        use_ref = self._normalize_required(use_ref, "use ref")
        if any(row.use_ref == use_ref for row in self._uses.values()):
            raise ValueError("learning evidence use ref cannot be rebound or replayed")
        self._use_counter += 1
        receipt_id = f"learning-evidence-use-{self._use_counter:08d}"
        payload = {
            "sequence": self._use_counter,
            "receipt_id": receipt_id,
            "lease_id": lease.lease_id,
            "subject_kind": lease.subject_kind,
            "subject_id": lease.subject_id,
            "operation_class": lease.operation_class,
            "producer_agent_id": lease.producer_agent_id,
            "verifier_agent_id": lease.verifier_agent_id,
            "evidence_id": lease.evidence_id,
            "evidence_digest": lease.evidence_digest,
            "subject_digest": lease.subject_digest,
            "use_ref": use_ref,
        }
        receipt = LearningEvidenceUseReceipt(**payload, digest=canonical_digest(payload))
        self._uses[receipt_id] = receipt
        self._uses_by_lease.setdefault(lease.lease_id, []).append(receipt)
        return receipt

    def _restore_lease(self, lease: LearningEvidenceLease) -> None:
        if lease.lease_id in self._leases:
            raise ValueError("duplicate learning evidence lease id")
        self._validate_semantic_authority(producer_agent_id=lease.producer_agent_id, evidence=lease.evidence)
        binding = lease.binding_payload()
        canonical_id = self._canonical_lease_id(binding)
        if lease.lease_id != canonical_id:
            raise ValueError("learning evidence lease id is not canonical for binding")
        binding_digest = canonical_digest(binding)
        if binding_digest in self._binding_index:
            raise ValueError("duplicate learning evidence canonical binding")
        self._leases[lease.lease_id] = lease
        self._binding_index[binding_digest] = lease.lease_id

    def _restore_use(self, receipt: LearningEvidenceUseReceipt) -> None:
        if receipt.receipt_id in self._uses:
            raise ValueError("duplicate learning evidence use receipt id")
        lease = self.lease(receipt.lease_id)
        if (
            receipt.subject_kind != lease.subject_kind
            or receipt.subject_id != lease.subject_id
            or receipt.operation_class != lease.operation_class
            or receipt.producer_agent_id != lease.producer_agent_id
            or receipt.verifier_agent_id != lease.verifier_agent_id
            or receipt.evidence_id != lease.evidence_id
            or receipt.evidence_digest != lease.evidence_digest
            or receipt.subject_digest != lease.subject_digest
        ):
            raise ValueError("learning evidence use receipt does not match exact lease binding")
        if any(row.use_ref == receipt.use_ref for row in self._uses.values()):
            raise ValueError("duplicate learning evidence use ref")
        prior = self._uses_by_lease.setdefault(lease.lease_id, [])
        if lease.single_use and prior:
            raise ValueError("single-use learning evidence lease has multiple use receipts")
        prior.append(receipt)
        self._uses[receipt.receipt_id] = receipt

    def _validate_ledger_shape(self) -> None:
        lease_sequences = sorted(row.sequence for row in self._leases.values())
        if self._lease_counter < 0 or lease_sequences != list(range(1, self._lease_counter + 1)):
            raise ValueError("learning evidence lease ledger must be gapless and match counter")
        use_sequences = sorted(row.sequence for row in self._uses.values())
        if self._use_counter < 0 or use_sequences != list(range(1, self._use_counter + 1)):
            raise ValueError("learning evidence use ledger must be gapless and match counter")
        expected_receipt_ids = {f"learning-evidence-use-{sequence:08d}" for sequence in use_sequences}
        if set(self._uses) != expected_receipt_ids:
            raise ValueError("learning evidence use receipt ids must match canonical sequence")

    def to_state(self) -> dict[str, Any]:
        return {
            "leases": [row.to_state() for row in sorted(self._leases.values(), key=lambda value: value.sequence)],
            "uses": [row.to_state() for row in sorted(self._uses.values(), key=lambda value: value.sequence)],
            "lease_counter": self._lease_counter,
            "use_counter": self._use_counter,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "LearningEvidenceAuthority":
        leases = tuple(LearningEvidenceLease.from_state(row) for row in state.get("leases", ()))
        uses = tuple(LearningEvidenceUseReceipt.from_state(row) for row in state.get("uses", ()))
        return cls(
            leases=leases,
            uses=uses,
            lease_counter=int(state.get("lease_counter", len(leases))),
            use_counter=int(state.get("use_counter", len(uses))),
        )


__all__ = ("LearningEvidenceLease", "LearningEvidenceUseReceipt", "LearningEvidenceAuthority")
