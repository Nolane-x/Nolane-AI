from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .epistemic_defeasible_truth import (
    DEFEASIBLE_BINDING_MODE,
    DefeasibleTruthScope,
)
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceChannel, EvidenceLedger
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.verification"
TRUTH_PROTOCOL = "truth-verification-defeasible-justification-provenance-lineage-temporal-v7"
PROJECTION_PROTOCOL = "truth-verification-defeasible-justification-provenance-projection-v7"


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
class DefeasibleTruthVerificationReceipt:
    receipt_id: str
    claim_id: str
    verifier_id: str
    channel: EvidenceChannel
    passed: bool
    scope_digest: str
    temporal_context_digest: str
    as_of: str
    evidence_ids: tuple[str, ...]
    source_provenance_digest: str
    digest: str
    binding_mode: str = DEFEASIBLE_BINDING_MODE

    @classmethod
    def create(
        cls,
        *,
        receipt_id: str,
        claim_id: str,
        verifier_id: str,
        channel: EvidenceChannel,
        passed: bool,
        scope_digest: str,
        temporal_context_digest: str,
        as_of: str,
        evidence_ids: tuple[str, ...],
        source_provenance_digest: str,
    ) -> "DefeasibleTruthVerificationReceipt":
        receipt_id = _explicit(receipt_id, "defeasible verification receipt id")
        claim_id = _explicit(claim_id, "defeasible verification claim id")
        verifier_id = _explicit(verifier_id, "defeasible verifier id")
        scope_digest = _explicit(scope_digest, "defeasible scope digest")
        temporal_context_digest = _explicit(
            temporal_context_digest,
            "defeasible verification temporal context digest",
        )
        context = TemporalContext.create(as_of=as_of)
        if context.digest != temporal_context_digest:
            raise ValueError("defeasible verification temporal context digest mismatch")
        evidence_ids = _ids(tuple(evidence_ids), "defeasible verification evidence ids")
        source_provenance_digest = _explicit(
            source_provenance_digest,
            "defeasible verifier provenance digest",
        )
        channel = EvidenceChannel(channel)
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": DEFEASIBLE_BINDING_MODE,
            "receipt_id": receipt_id,
            "claim_id": claim_id,
            "verifier_id": verifier_id,
            "channel": channel.value,
            "passed": bool(passed),
            "scope_digest": scope_digest,
            "temporal_context_digest": temporal_context_digest,
            "as_of": context.as_of,
            "evidence_ids": list(evidence_ids),
            "source_provenance_digest": source_provenance_digest,
        }
        return cls(
            receipt_id,
            claim_id,
            verifier_id,
            channel,
            bool(passed),
            scope_digest,
            temporal_context_digest,
            context.as_of,
            evidence_ids,
            source_provenance_digest,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": self.binding_mode,
            "receipt_id": self.receipt_id,
            "claim_id": self.claim_id,
            "verifier_id": self.verifier_id,
            "channel": self.channel.value,
            "passed": self.passed,
            "scope_digest": self.scope_digest,
            "temporal_context_digest": self.temporal_context_digest,
            "as_of": self.as_of,
            "evidence_ids": list(self.evidence_ids),
            "source_provenance_digest": self.source_provenance_digest,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "DefeasibleTruthVerificationReceipt":
        _unexpected(
            state,
            {
                "protocol",
                "binding_mode",
                "receipt_id",
                "claim_id",
                "verifier_id",
                "channel",
                "passed",
                "scope_digest",
                "temporal_context_digest",
                "as_of",
                "evidence_ids",
                "source_provenance_digest",
                "digest",
            },
            "defeasible verification receipt",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported defeasible verification protocol")
        if str(state.get("binding_mode", "")) != DEFEASIBLE_BINDING_MODE:
            raise ValueError("unsupported defeasible verification binding mode")
        row = cls.create(
            receipt_id=str(state["receipt_id"]),
            claim_id=str(state["claim_id"]),
            verifier_id=str(state["verifier_id"]),
            channel=EvidenceChannel(str(state["channel"])),
            passed=bool(state["passed"]),
            scope_digest=str(state["scope_digest"]),
            temporal_context_digest=str(state["temporal_context_digest"]),
            as_of=str(state["as_of"]),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            source_provenance_digest=str(state["source_provenance_digest"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("defeasible verification receipt digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class DefeasibleTruthVerificationCoverage:
    receipts: tuple[DefeasibleTruthVerificationReceipt, ...]
    valid_receipt_ids: tuple[str, ...]
    invalid_receipt_ids: tuple[str, ...]
    negative_receipt_ids: tuple[str, ...]
    non_independent_receipt_ids: tuple[str, ...]
    passing_independence_keys: tuple[str, ...]
    passing_channels: tuple[EvidenceChannel, ...]
    issues: tuple[str, ...]

    @property
    def independent_source_count(self) -> int:
        return len(self.passing_independence_keys)

    @property
    def channel_count(self) -> int:
        return len(self.passing_channels)


class DefeasibleTruthVerificationLedger:
    """Dedicated v7 verification ledger bound to exact defeasible truth state."""

    def __init__(self) -> None:
        self._receipts: dict[str, DefeasibleTruthVerificationReceipt] = {}

    def record(
        self,
        row: DefeasibleTruthVerificationReceipt,
    ) -> DefeasibleTruthVerificationReceipt:
        if not isinstance(row, DefeasibleTruthVerificationReceipt):
            raise TypeError("defeasible verification ledger accepts v7 receipts only")
        old = self._receipts.get(row.receipt_id)
        if old is not None and old != row:
            raise ValueError("defeasible verification receipt id collision")
        self._receipts[row.receipt_id] = row
        return row

    def receipts(
        self,
        claim_id: str | None = None,
    ) -> tuple[DefeasibleTruthVerificationReceipt, ...]:
        rows = tuple(self._receipts.values())
        if claim_id is not None:
            rows = tuple(row for row in rows if row.claim_id == str(claim_id))
        return tuple(sorted(rows, key=lambda row: row.receipt_id))

    @staticmethod
    def receipt_is_current(
        receipt: DefeasibleTruthVerificationReceipt,
        *,
        scope: DefeasibleTruthScope,
        temporal_context: TemporalContext,
    ) -> bool:
        if not isinstance(receipt, DefeasibleTruthVerificationReceipt):
            return False
        if not isinstance(scope, DefeasibleTruthScope):
            return False
        if not isinstance(temporal_context, TemporalContext):
            return False
        return (
            receipt.binding_mode == DEFEASIBLE_BINDING_MODE
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
        scope: DefeasibleTruthScope,
        temporal_context: TemporalContext,
    ) -> tuple[DefeasibleTruthVerificationReceipt, ...]:
        return tuple(
            row
            for row in self.receipts(str(claim_id))
            if self.receipt_is_current(row, scope=scope, temporal_context=temporal_context)
        )

    @staticmethod
    def _provenance_issue(
        row: DefeasibleTruthVerificationReceipt,
        *,
        evidence: EvidenceLedger,
        evidence_temporal: TemporalEvidenceView,
        temporal_context: TemporalContext,
        source_provenance: SourceProvenanceRegistry,
    ) -> str | None:
        if source_provenance.current(row.verifier_id) is None:
            return "verification_source_provenance_missing"
        if row.source_provenance_digest != source_provenance.projection_digest((row.verifier_id,)):
            return "verification_source_provenance_stale"
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
                or item.channel is not row.channel
            ):
                return "verification_provenance_mismatch"
        return None

    def coverage(
        self,
        claim_id: str,
        *,
        scope: DefeasibleTruthScope,
        temporal_context: TemporalContext,
        evidence: EvidenceLedger,
        evidence_temporal: TemporalEvidenceView,
        source_provenance: SourceProvenanceRegistry,
    ) -> DefeasibleTruthVerificationCoverage:
        rows = self.current_receipts(
            str(claim_id),
            scope=scope,
            temporal_context=temporal_context,
        )
        valid: list[DefeasibleTruthVerificationReceipt] = []
        invalid: list[DefeasibleTruthVerificationReceipt] = []
        issues: list[str] = []
        for row in rows:
            issue = self._provenance_issue(
                row,
                evidence=evidence,
                evidence_temporal=evidence_temporal,
                temporal_context=temporal_context,
                source_provenance=source_provenance,
            )
            if issue is None:
                valid.append(row)
            else:
                invalid.append(row)
                issues.append(issue)

        passing = tuple(row for row in valid if row.passed)
        negative = tuple(sorted(row.receipt_id for row in valid if not row.passed))
        origin_controller_ids: set[str] = set()
        for source_id in scope.decision_source_ids:
            try:
                origin_controller_ids.update(source_provenance.root_controllers(source_id))
            except KeyError:
                continue

        independence_keys: set[str] = set()
        non_independent: list[str] = []
        for row in passing:
            key = source_provenance.independence_key(row.verifier_id)
            if key is None or key in origin_controller_ids:
                non_independent.append(row.receipt_id)
            else:
                independence_keys.add(key)

        return DefeasibleTruthVerificationCoverage(
            receipts=rows,
            valid_receipt_ids=tuple(sorted(row.receipt_id for row in valid)),
            invalid_receipt_ids=tuple(sorted(row.receipt_id for row in invalid)),
            negative_receipt_ids=negative,
            non_independent_receipt_ids=tuple(sorted(non_independent)),
            passing_independence_keys=tuple(sorted(independence_keys)),
            passing_channels=tuple(
                sorted({row.channel for row in passing}, key=lambda value: value.value)
            ),
            issues=tuple(dict.fromkeys(issues)),
        )

    def scoped_digest(
        self,
        claim_id: str,
        *,
        scope: DefeasibleTruthScope,
        temporal_context: TemporalContext,
    ) -> str:
        rows = self.current_receipts(
            str(claim_id),
            scope=scope,
            temporal_context=temporal_context,
        )
        return canonical_digest(
            {
                "protocol": PROJECTION_PROTOCOL,
                "binding_mode": DEFEASIBLE_BINDING_MODE,
                "claim_id": str(claim_id),
                "scope_digest": scope.digest,
                "temporal_context_digest": temporal_context.digest,
                "as_of": temporal_context.as_of,
                "receipts": [row.to_state() for row in rows],
            }
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "receipts": [row.to_state() for row in self.receipts()],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "DefeasibleTruthVerificationLedger":
        _unexpected(state, {"protocol", "receipts"}, "defeasible verification ledger")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported defeasible verification protocol")
        ledger = cls()
        seen: set[str] = set()
        for value in state.get("receipts", ()):
            row = DefeasibleTruthVerificationReceipt.from_state(value)
            if row.receipt_id in seen:
                raise ValueError("duplicate serialized defeasible verification receipt")
            seen.add(row.receipt_id)
            ledger.record(row)
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "PROJECTION_PROTOCOL",
    "DefeasibleTruthVerificationReceipt",
    "DefeasibleTruthVerificationCoverage",
    "DefeasibleTruthVerificationLedger",
)
