from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .evidence_truth import EvidenceChannel, EvidenceLedger

PARENT_COMPONENT_ID = "external.verification"
TRUTH_PROTOCOL = "truth-verification-ledger-v1"


@dataclass(frozen=True, slots=True)
class TruthVerificationReceipt:
    receipt_id: str
    claim_id: str
    verifier_id: str
    source_family: str
    channel: EvidenceChannel
    passed: bool
    knowledge_digest: str
    epistemic_digest: str
    evidence_ids: tuple[str, ...]
    digest: str

    @classmethod
    def create(cls, *, receipt_id: str, claim_id: str, verifier_id: str, source_family: str,
               channel: EvidenceChannel, passed: bool, knowledge_digest: str, epistemic_digest: str,
               evidence_ids: tuple[str, ...] = ()) -> "TruthVerificationReceipt":
        payload = {"receipt_id": str(receipt_id).strip(), "claim_id": str(claim_id).strip(),
                   "verifier_id": str(verifier_id).strip(), "source_family": str(source_family).strip(),
                   "channel": EvidenceChannel(channel).value, "passed": bool(passed),
                   "knowledge_digest": str(knowledge_digest).strip(), "epistemic_digest": str(epistemic_digest).strip(),
                   "evidence_ids": list(tuple(str(x).strip() for x in evidence_ids))}
        if any(not payload[key] for key in ("receipt_id", "claim_id", "verifier_id", "source_family", "knowledge_digest", "epistemic_digest")):
            raise ValueError("verification identity and state binding must be explicit")
        if any(not x for x in payload["evidence_ids"]) or len(set(payload["evidence_ids"])) != len(payload["evidence_ids"]):
            raise ValueError("verification evidence ids must be explicit and unique")
        return cls(payload["receipt_id"], payload["claim_id"], payload["verifier_id"], payload["source_family"],
                   EvidenceChannel(payload["channel"]), payload["passed"], payload["knowledge_digest"],
                   payload["epistemic_digest"], tuple(payload["evidence_ids"]), canonical_digest(payload))

    def payload(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, "claim_id": self.claim_id, "verifier_id": self.verifier_id,
                "source_family": self.source_family, "channel": self.channel.value, "passed": self.passed,
                "knowledge_digest": self.knowledge_digest, "epistemic_digest": self.epistemic_digest,
                "evidence_ids": list(self.evidence_ids)}

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthVerificationReceipt":
        row = cls.create(receipt_id=str(state["receipt_id"]), claim_id=str(state["claim_id"]),
                         verifier_id=str(state["verifier_id"]), source_family=str(state["source_family"]),
                         channel=EvidenceChannel(str(state["channel"])), passed=bool(state["passed"]),
                         knowledge_digest=str(state["knowledge_digest"]), epistemic_digest=str(state["epistemic_digest"]),
                         evidence_ids=tuple(str(x) for x in state.get("evidence_ids", ())))
        if str(state["digest"]) != row.digest:
            raise ValueError("truth verification receipt digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class TruthVerificationCoverage:
    receipts: tuple[TruthVerificationReceipt, ...]
    valid_receipt_ids: tuple[str, ...]
    invalid_receipt_ids: tuple[str, ...]
    negative_receipt_ids: tuple[str, ...]
    passing_source_families: tuple[str, ...]
    passing_channels: tuple[EvidenceChannel, ...]
    issues: tuple[str, ...]

    @property
    def independent_source_count(self) -> int:
        return len(self.passing_source_families)

    @property
    def channel_count(self) -> int:
        return len(self.passing_channels)


class TruthVerificationLedger:
    """Append-only exact-state challenge protocol under ``external.verification``.

    Raw receipts remain available for audit, including incomplete/failed receipts. Only
    :meth:`coverage` establishes whether a receipt is provenance-grounded enough to count toward
    truth Assurance.
    """

    def __init__(self) -> None:
        self._receipts: dict[str, TruthVerificationReceipt] = {}

    def record(self, row: TruthVerificationReceipt) -> TruthVerificationReceipt:
        old = self._receipts.get(row.receipt_id)
        if old is not None and old != row:
            raise ValueError("receipt id collision")
        self._receipts[row.receipt_id] = row
        return row

    def receipts(self, claim_id: str | None = None) -> tuple[TruthVerificationReceipt, ...]:
        rows = tuple(self._receipts.values())
        if claim_id is not None:
            rows = tuple(row for row in rows if row.claim_id == str(claim_id))
        return tuple(sorted(rows, key=lambda row: row.receipt_id))

    def bound_receipts(self, claim_id: str, *, knowledge_digest: str, epistemic_digest: str) -> tuple[TruthVerificationReceipt, ...]:
        return tuple(row for row in self.receipts(claim_id)
                     if row.knowledge_digest == str(knowledge_digest) and row.epistemic_digest == str(epistemic_digest))

    @staticmethod
    def _receipt_provenance_issue(row: TruthVerificationReceipt, evidence: EvidenceLedger) -> str | None:
        if not row.evidence_ids:
            return "unbound_verification_evidence"
        for evidence_id in row.evidence_ids:
            if not evidence.is_active(evidence_id):
                return "verification_provenance_mismatch"
            try:
                item = evidence.get(evidence_id)
            except KeyError:
                return "verification_provenance_mismatch"
            if (
                item.subject_id != row.claim_id
                or item.source_id != row.verifier_id
                or item.source_family != row.source_family
                or item.channel is not row.channel
            ):
                return "verification_provenance_mismatch"
        return None

    def coverage(self, claim_id: str, *, knowledge_digest: str, epistemic_digest: str,
                 evidence: EvidenceLedger) -> TruthVerificationCoverage:
        rows = self.bound_receipts(
            str(claim_id), knowledge_digest=str(knowledge_digest), epistemic_digest=str(epistemic_digest),
        )
        valid: list[TruthVerificationReceipt] = []
        invalid: list[TruthVerificationReceipt] = []
        issues: list[str] = []
        for row in rows:
            issue = self._receipt_provenance_issue(row, evidence)
            if issue is None:
                valid.append(row)
            else:
                invalid.append(row)
                issues.append(issue)

        passing = tuple(row for row in valid if row.passed)
        negatives = tuple(row.receipt_id for row in rows if not row.passed)
        return TruthVerificationCoverage(
            receipts=rows,
            valid_receipt_ids=tuple(row.receipt_id for row in valid),
            invalid_receipt_ids=tuple(row.receipt_id for row in invalid),
            negative_receipt_ids=tuple(sorted(negatives)),
            passing_source_families=tuple(sorted({row.source_family for row in passing})),
            passing_channels=tuple(sorted({row.channel for row in passing}, key=lambda channel: channel.value)),
            issues=tuple(dict.fromkeys(issues)),
        )

    def independent_passing_channels(self, claim_id: str, *, knowledge_digest: str, epistemic_digest: str) -> int:
        """Compatibility metric over raw receipts; strict Assurance uses validated coverage()."""
        return len({row.source_family for row in self.bound_receipts(claim_id, knowledge_digest=knowledge_digest,
                                                                      epistemic_digest=epistemic_digest) if row.passed})

    def distinct_passing_channel_kinds(self, claim_id: str, *, knowledge_digest: str, epistemic_digest: str) -> int:
        """Compatibility metric over raw receipts; strict Assurance uses validated coverage()."""
        return len({row.channel for row in self.bound_receipts(claim_id, knowledge_digest=knowledge_digest,
                                                                epistemic_digest=epistemic_digest) if row.passed})

    def to_state(self) -> dict[str, Any]:
        return {"protocol": TRUTH_PROTOCOL, "receipts": [row.to_state() for row in self.receipts()]}

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthVerificationLedger":
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported truth verification protocol")
        ledger = cls()
        for value in state.get("receipts", ()):
            ledger.record(TruthVerificationReceipt.from_state(value))
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID", "TRUTH_PROTOCOL", "TruthVerificationReceipt",
    "TruthVerificationCoverage", "TruthVerificationLedger",
)
