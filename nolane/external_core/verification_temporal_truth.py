from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .epistemic_temporal_truth import TemporalTruthRelationAwareScope
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceChannel, EvidenceLedger
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.verification"
TRUTH_PROTOCOL = "truth-verification-relation-temporal-v4"
TEMPORAL_BINDING_MODE = "relation-aware-temporal-v4"
PROJECTION_PROTOCOL = "truth-verification-relation-temporal-projection-v4"


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
        raise ValueError(f"unexpected {kind} binding field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class TemporalTruthVerificationReceipt:
    receipt_id: str
    claim_id: str
    verifier_id: str
    source_family: str
    channel: EvidenceChannel
    passed: bool
    scope_digest: str
    temporal_context_digest: str
    as_of: str
    evidence_ids: tuple[str, ...]
    digest: str
    binding_mode: str = TEMPORAL_BINDING_MODE

    @classmethod
    def create(
        cls,
        *,
        receipt_id: str,
        claim_id: str,
        verifier_id: str,
        source_family: str,
        channel: EvidenceChannel,
        passed: bool,
        scope_digest: str,
        temporal_context_digest: str,
        as_of: str,
        evidence_ids: tuple[str, ...] = (),
    ) -> "TemporalTruthVerificationReceipt":
        receipt_id = _explicit(receipt_id, "temporal receipt_id")
        claim_id = _explicit(claim_id, "temporal claim_id")
        verifier_id = _explicit(verifier_id, "temporal verifier_id")
        source_family = _explicit(source_family, "temporal source_family")
        scope_digest = _explicit(scope_digest, "temporal scope_digest")
        temporal_context_digest = _explicit(temporal_context_digest, "temporal_context_digest")
        context = TemporalContext.create(as_of=as_of)
        evidence_ids = _ids(tuple(evidence_ids), "temporal verification evidence ids")
        channel = EvidenceChannel(channel)
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": TEMPORAL_BINDING_MODE,
            "receipt_id": receipt_id,
            "claim_id": claim_id,
            "verifier_id": verifier_id,
            "source_family": source_family,
            "channel": channel.value,
            "passed": bool(passed),
            "scope_digest": scope_digest,
            "temporal_context_digest": temporal_context_digest,
            "as_of": context.as_of,
            "evidence_ids": list(evidence_ids),
        }
        return cls(
            receipt_id,
            claim_id,
            verifier_id,
            source_family,
            channel,
            bool(passed),
            scope_digest,
            temporal_context_digest,
            context.as_of,
            evidence_ids,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": self.binding_mode,
            "receipt_id": self.receipt_id,
            "claim_id": self.claim_id,
            "verifier_id": self.verifier_id,
            "source_family": self.source_family,
            "channel": self.channel.value,
            "passed": self.passed,
            "scope_digest": self.scope_digest,
            "temporal_context_digest": self.temporal_context_digest,
            "as_of": self.as_of,
            "evidence_ids": list(self.evidence_ids),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TemporalTruthVerificationReceipt":
        allowed = {
            "protocol", "binding_mode", "receipt_id", "claim_id", "verifier_id", "source_family",
            "channel", "passed", "scope_digest", "temporal_context_digest", "as_of", "evidence_ids", "digest",
        }
        _unexpected(state, allowed, "temporal verification")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported temporal verification protocol")
        if str(state.get("binding_mode", "")) != TEMPORAL_BINDING_MODE:
            raise ValueError("unsupported temporal verification binding mode")
        row = cls.create(
            receipt_id=str(state["receipt_id"]),
            claim_id=str(state["claim_id"]),
            verifier_id=str(state["verifier_id"]),
            source_family=str(state["source_family"]),
            channel=EvidenceChannel(str(state["channel"])),
            passed=bool(state["passed"]),
            scope_digest=str(state["scope_digest"]),
            temporal_context_digest=str(state["temporal_context_digest"]),
            as_of=str(state["as_of"]),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("temporal verification receipt digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class TemporalTruthVerificationCoverage:
    receipts: tuple[TemporalTruthVerificationReceipt, ...]
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


class TemporalTruthVerificationLedger:
    """Append-only verification receipts exact-bound to A9 relation-aware temporal scope v4."""

    def __init__(self) -> None:
        self._receipts: dict[str, TemporalTruthVerificationReceipt] = {}

    def record(self, row: TemporalTruthVerificationReceipt) -> TemporalTruthVerificationReceipt:
        if not isinstance(row, TemporalTruthVerificationReceipt):
            raise TypeError("temporal verification ledger accepts v4 receipts only")
        old = self._receipts.get(row.receipt_id)
        if old is not None and old != row:
            raise ValueError("temporal verification receipt id collision")
        self._receipts[row.receipt_id] = row
        return row

    def receipts(self, claim_id: str | None = None) -> tuple[TemporalTruthVerificationReceipt, ...]:
        rows = tuple(self._receipts.values())
        if claim_id is not None:
            rows = tuple(row for row in rows if row.claim_id == str(claim_id))
        return tuple(sorted(rows, key=lambda row: row.receipt_id))

    def receipt_is_current(
        self,
        receipt: TemporalTruthVerificationReceipt,
        *,
        scope: TemporalTruthRelationAwareScope,
        temporal_context: TemporalContext,
    ) -> bool:
        if not isinstance(receipt, TemporalTruthVerificationReceipt):
            return False
        if not isinstance(scope, TemporalTruthRelationAwareScope) or not isinstance(temporal_context, TemporalContext):
            return False
        return (
            receipt.binding_mode == TEMPORAL_BINDING_MODE
            and receipt.claim_id == scope.target_claim_id
            and receipt.scope_digest == scope.digest
            and receipt.temporal_context_digest == temporal_context.digest
            and receipt.temporal_context_digest == scope.temporal_context_digest
            and receipt.as_of == temporal_context.as_of
            and receipt.as_of == scope.as_of
        )

    def current_receipts(
        self,
        claim_id: str,
        *,
        scope: TemporalTruthRelationAwareScope,
        temporal_context: TemporalContext,
    ) -> tuple[TemporalTruthVerificationReceipt, ...]:
        return tuple(
            row for row in self.receipts(str(claim_id))
            if self.receipt_is_current(row, scope=scope, temporal_context=temporal_context)
        )

    @staticmethod
    def _provenance_issue(
        row: TemporalTruthVerificationReceipt,
        *,
        evidence: EvidenceLedger,
        evidence_temporal: TemporalEvidenceView,
        temporal_context: TemporalContext,
    ) -> str | None:
        if not row.evidence_ids:
            return "unbound_verification_evidence"
        for evidence_id in row.evidence_ids:
            state = evidence_temporal.state_at(
                evidence_id,
                evidence=evidence,
                temporal_context=temporal_context,
            )
            if state != "active":
                return f"verification_temporal_provenance_{state}"
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

    def coverage(
        self,
        claim_id: str,
        *,
        scope: TemporalTruthRelationAwareScope,
        temporal_context: TemporalContext,
        evidence: EvidenceLedger,
        evidence_temporal: TemporalEvidenceView,
    ) -> TemporalTruthVerificationCoverage:
        rows = self.current_receipts(
            str(claim_id),
            scope=scope,
            temporal_context=temporal_context,
        )
        valid: list[TemporalTruthVerificationReceipt] = []
        invalid: list[TemporalTruthVerificationReceipt] = []
        issues: list[str] = []
        for row in rows:
            issue = self._provenance_issue(
                row,
                evidence=evidence,
                evidence_temporal=evidence_temporal,
                temporal_context=temporal_context,
            )
            if issue is None:
                valid.append(row)
            else:
                invalid.append(row)
                issues.append(issue)
        passing = tuple(row for row in valid if row.passed)
        negative = tuple(sorted(row.receipt_id for row in valid if not row.passed))
        return TemporalTruthVerificationCoverage(
            receipts=rows,
            valid_receipt_ids=tuple(sorted(row.receipt_id for row in valid)),
            invalid_receipt_ids=tuple(sorted(row.receipt_id for row in invalid)),
            negative_receipt_ids=negative,
            passing_source_families=tuple(sorted({row.source_family for row in passing})),
            passing_channels=tuple(sorted({row.channel for row in passing}, key=lambda value: value.value)),
            issues=tuple(dict.fromkeys(issues)),
        )

    def scoped_digest(
        self,
        claim_id: str,
        *,
        scope: TemporalTruthRelationAwareScope,
        temporal_context: TemporalContext,
    ) -> str:
        rows = self.current_receipts(
            str(claim_id),
            scope=scope,
            temporal_context=temporal_context,
        )
        return canonical_digest({
            "protocol": PROJECTION_PROTOCOL,
            "binding_mode": TEMPORAL_BINDING_MODE,
            "claim_id": str(claim_id),
            "scope_digest": scope.digest,
            "temporal_context_digest": temporal_context.digest,
            "as_of": temporal_context.as_of,
            "receipts": [row.to_state() for row in rows],
        })

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "receipts": [row.to_state() for row in self.receipts()],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TemporalTruthVerificationLedger":
        _unexpected(state, {"protocol", "receipts"}, "temporal verification ledger")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported temporal verification ledger protocol")
        ledger = cls()
        seen: set[str] = set()
        for value in state.get("receipts", ()):
            row = TemporalTruthVerificationReceipt.from_state(value)
            if row.receipt_id in seen:
                raise ValueError("duplicate serialized temporal verification receipt")
            seen.add(row.receipt_id)
            ledger.record(row)
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "TEMPORAL_BINDING_MODE",
    "PROJECTION_PROTOCOL",
    "TemporalTruthVerificationReceipt",
    "TemporalTruthVerificationCoverage",
    "TemporalTruthVerificationLedger",
)
