from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .epistemic_context_truth import CONTEXT_BINDING_MODE, ContextTruthScope
from .evidence_context_truth import EvidenceContextBindingRegistry
from .evidence_dependence_truth import SourceDependenceRegistry
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceChannel, EvidenceLedger
from .knowledge_context_truth import ClaimContextBindingRegistry, TruthContext
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.verification"
TRUTH_PROTOCOL = (
    "truth-verification-context-dependence-defeasible-justification-provenance-"
    "lineage-temporal-v9"
)
PROJECTION_PROTOCOL = (
    "truth-verification-context-dependence-defeasible-justification-provenance-projection-v9"
)
_COMPONENT_PROTOCOL = "truth-verification-context-dependence-component-v9"


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
class ContextTruthVerificationReceipt:
    receipt_id: str
    claim_id: str
    verifier_id: str
    channel: EvidenceChannel
    passed: bool
    scope_digest: str
    truth_context_digest: str
    temporal_context_digest: str
    as_of: str
    evidence_ids: tuple[str, ...]
    source_provenance_digest: str
    source_dependence_digest: str
    evidence_context_digest: str
    digest: str
    binding_mode: str = CONTEXT_BINDING_MODE

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
        truth_context_digest: str,
        temporal_context_digest: str,
        as_of: str,
        evidence_ids: tuple[str, ...],
        source_provenance_digest: str,
        source_dependence_digest: str,
        evidence_context_digest: str,
    ) -> "ContextTruthVerificationReceipt":
        receipt_id = _explicit(receipt_id, "context verification receipt id")
        claim_id = _explicit(claim_id, "context verification claim id")
        verifier_id = _explicit(verifier_id, "context verifier id")
        scope_digest = _explicit(scope_digest, "context verification scope digest")
        truth_context_digest = _explicit(
            truth_context_digest,
            "context verification truth-context digest",
        )
        temporal_context_digest = _explicit(
            temporal_context_digest,
            "context verification temporal-context digest",
        )
        temporal = TemporalContext.create(as_of=as_of)
        if temporal.digest != temporal_context_digest:
            raise ValueError("context verification temporal context digest mismatch")
        evidence_ids = _ids(tuple(evidence_ids), "context verification evidence ids")
        source_provenance_digest = _explicit(
            source_provenance_digest,
            "context verifier provenance digest",
        )
        source_dependence_digest = _explicit(
            source_dependence_digest,
            "context verifier source-dependence digest",
        )
        evidence_context_digest = _explicit(
            evidence_context_digest,
            "context verifier evidence-context digest",
        )
        channel = EvidenceChannel(channel)
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": CONTEXT_BINDING_MODE,
            "receipt_id": receipt_id,
            "claim_id": claim_id,
            "verifier_id": verifier_id,
            "channel": channel.value,
            "passed": bool(passed),
            "scope_digest": scope_digest,
            "truth_context_digest": truth_context_digest,
            "temporal_context_digest": temporal_context_digest,
            "as_of": temporal.as_of,
            "evidence_ids": list(evidence_ids),
            "source_provenance_digest": source_provenance_digest,
            "source_dependence_digest": source_dependence_digest,
            "evidence_context_digest": evidence_context_digest,
        }
        return cls(
            receipt_id,
            claim_id,
            verifier_id,
            channel,
            bool(passed),
            scope_digest,
            truth_context_digest,
            temporal_context_digest,
            temporal.as_of,
            evidence_ids,
            source_provenance_digest,
            source_dependence_digest,
            evidence_context_digest,
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
            "truth_context_digest": self.truth_context_digest,
            "temporal_context_digest": self.temporal_context_digest,
            "as_of": self.as_of,
            "evidence_ids": list(self.evidence_ids),
            "source_provenance_digest": self.source_provenance_digest,
            "source_dependence_digest": self.source_dependence_digest,
            "evidence_context_digest": self.evidence_context_digest,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ContextTruthVerificationReceipt":
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
                "truth_context_digest",
                "temporal_context_digest",
                "as_of",
                "evidence_ids",
                "source_provenance_digest",
                "source_dependence_digest",
                "evidence_context_digest",
                "digest",
            },
            "context verification receipt",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported context verification protocol")
        if str(state.get("binding_mode", "")) != CONTEXT_BINDING_MODE:
            raise ValueError("unsupported context verification binding mode")
        row = cls.create(
            receipt_id=str(state["receipt_id"]),
            claim_id=str(state["claim_id"]),
            verifier_id=str(state["verifier_id"]),
            channel=EvidenceChannel(str(state["channel"])),
            passed=bool(state["passed"]),
            scope_digest=str(state["scope_digest"]),
            truth_context_digest=str(state["truth_context_digest"]),
            temporal_context_digest=str(state["temporal_context_digest"]),
            as_of=str(state["as_of"]),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            source_provenance_digest=str(state["source_provenance_digest"]),
            source_dependence_digest=str(state["source_dependence_digest"]),
            evidence_context_digest=str(state["evidence_context_digest"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("context verification receipt digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class ContextTruthVerificationCoverage:
    receipts: tuple[ContextTruthVerificationReceipt, ...]
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


class ContextTruthVerificationLedger:
    """Dedicated A15 verifier ledger; context is applicability, never independence."""

    def __init__(self) -> None:
        self._receipts: dict[str, ContextTruthVerificationReceipt] = {}

    def record(self, row: ContextTruthVerificationReceipt) -> ContextTruthVerificationReceipt:
        if not isinstance(row, ContextTruthVerificationReceipt):
            raise TypeError("context verification ledger accepts v9 receipts only")
        old = self._receipts.get(row.receipt_id)
        if old is not None and old != row:
            raise ValueError("context verification receipt id collision")
        self._receipts[row.receipt_id] = row
        return row

    def receipts(
        self,
        claim_id: str | None = None,
    ) -> tuple[ContextTruthVerificationReceipt, ...]:
        rows = tuple(self._receipts.values())
        if claim_id is not None:
            rows = tuple(row for row in rows if row.claim_id == str(claim_id))
        return tuple(sorted(rows, key=lambda row: row.receipt_id))

    @staticmethod
    def receipt_is_current(
        receipt: ContextTruthVerificationReceipt,
        *,
        scope: ContextTruthScope,
        truth_context: TruthContext,
        temporal_context: TemporalContext,
    ) -> bool:
        if not isinstance(receipt, ContextTruthVerificationReceipt):
            return False
        if not isinstance(scope, ContextTruthScope):
            return False
        if not isinstance(truth_context, TruthContext):
            return False
        if not isinstance(temporal_context, TemporalContext):
            return False
        return (
            receipt.binding_mode == CONTEXT_BINDING_MODE
            and scope.binding_mode == CONTEXT_BINDING_MODE
            and receipt.claim_id == scope.target_claim_id
            and receipt.scope_digest == scope.digest
            and scope.truth_context == truth_context
            and receipt.truth_context_digest == truth_context.digest
            and receipt.truth_context_digest == scope.truth_context.digest
            and receipt.temporal_context_digest == temporal_context.digest
            and receipt.temporal_context_digest == scope.temporal_context_digest
            and receipt.as_of == temporal_context.as_of
            and receipt.as_of == scope.as_of
        )

    def current_receipts(
        self,
        claim_id: str,
        *,
        scope: ContextTruthScope,
        truth_context: TruthContext,
        temporal_context: TemporalContext,
    ) -> tuple[ContextTruthVerificationReceipt, ...]:
        return tuple(
            row
            for row in self.receipts(str(claim_id))
            if self.receipt_is_current(
                row,
                scope=scope,
                truth_context=truth_context,
                temporal_context=temporal_context,
            )
        )

    @staticmethod
    def _scope_context_issue(
        scope: ContextTruthScope,
        *,
        truth_context: TruthContext,
        claim_context: ClaimContextBindingRegistry,
        evidence_context: EvidenceContextBindingRegistry,
    ) -> str | None:
        if scope.truth_context != truth_context:
            return "verification_truth_context_mismatch"
        if scope.claim_context_digest != claim_context.projection_digest(scope.scope_claim_ids):
            return "verification_claim_context_stale"
        if scope.evidence_context_digest != evidence_context.projection_digest(scope.evidence_ids):
            return "verification_scope_evidence_context_stale"
        return None

    @staticmethod
    def _validity_issue(
        row: ContextTruthVerificationReceipt,
        *,
        truth_context: TruthContext,
        evidence: EvidenceLedger,
        evidence_temporal: TemporalEvidenceView,
        temporal_context: TemporalContext,
        source_provenance: SourceProvenanceRegistry,
        source_dependence: SourceDependenceRegistry,
        evidence_context: EvidenceContextBindingRegistry,
    ) -> str | None:
        if source_provenance.current(row.verifier_id) is None:
            return "verification_source_provenance_missing"
        if row.source_provenance_digest != source_provenance.projection_digest((row.verifier_id,)):
            return "verification_source_provenance_stale"
        if source_dependence.current(row.verifier_id) is None:
            return "verification_source_dependence_missing"
        if row.source_dependence_digest != source_dependence.projection_digest((row.verifier_id,)):
            return "verification_source_dependence_stale"
        if not row.evidence_ids:
            return "unbound_verification_evidence"
        if row.evidence_context_digest != evidence_context.projection_digest(row.evidence_ids):
            return "verification_evidence_context_stale"
        for evidence_id in row.evidence_ids:
            if not evidence_context.applies(evidence_id, truth_context):
                return "verification_evidence_context_mismatch"
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

    @staticmethod
    def _component_keys(
        rows: tuple[ContextTruthVerificationReceipt, ...],
        *,
        source_provenance: SourceProvenanceRegistry,
        source_dependence: SourceDependenceRegistry,
    ) -> tuple[str, ...]:
        if not rows:
            return ()

        parent = list(range(len(rows)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            root_left = find(left)
            root_right = find(right)
            if root_left == root_right:
                return
            if root_left < root_right:
                parent[root_right] = root_left
            else:
                parent[root_left] = root_right

        controller_keys = [source_provenance.independence_key(row.verifier_id) for row in rows]
        basis_sets = [set(source_dependence.basis_ids(row.verifier_id)) for row in rows]
        for left in range(len(rows)):
            for right in range(left + 1, len(rows)):
                same_controller = (
                    controller_keys[left] is not None
                    and controller_keys[left] == controller_keys[right]
                )
                shared_basis = bool(basis_sets[left] & basis_sets[right])
                if same_controller or shared_basis:
                    union(left, right)

        groups: dict[int, list[int]] = {}
        for index in range(len(rows)):
            groups.setdefault(find(index), []).append(index)

        keys: list[str] = []
        for indices in groups.values():
            controllers = sorted(
                {
                    str(controller_keys[index])
                    for index in indices
                    if controller_keys[index] is not None
                }
            )
            bases = sorted(
                {
                    basis
                    for index in indices
                    for basis in basis_sets[index]
                }
            )
            keys.append(
                canonical_digest(
                    {
                        "protocol": _COMPONENT_PROTOCOL,
                        "controller_keys": controllers,
                        "basis_ids": bases,
                    }
                )
            )
        return tuple(sorted(keys))

    def coverage(
        self,
        claim_id: str,
        *,
        scope: ContextTruthScope,
        truth_context: TruthContext,
        temporal_context: TemporalContext,
        evidence: EvidenceLedger,
        evidence_temporal: TemporalEvidenceView,
        source_provenance: SourceProvenanceRegistry,
        source_dependence: SourceDependenceRegistry,
        claim_context: ClaimContextBindingRegistry,
        evidence_context: EvidenceContextBindingRegistry,
    ) -> ContextTruthVerificationCoverage:
        if not isinstance(scope, ContextTruthScope):
            raise TypeError("context verification requires ContextTruthScope")
        if not isinstance(truth_context, TruthContext):
            raise TypeError("context verification requires TruthContext")
        if not isinstance(claim_context, ClaimContextBindingRegistry):
            raise TypeError("context verification requires ClaimContextBindingRegistry")
        if not isinstance(evidence_context, EvidenceContextBindingRegistry):
            raise TypeError("context verification requires EvidenceContextBindingRegistry")

        rows = self.current_receipts(
            str(claim_id),
            scope=scope,
            truth_context=truth_context,
            temporal_context=temporal_context,
        )
        scope_issue = self._scope_context_issue(
            scope,
            truth_context=truth_context,
            claim_context=claim_context,
            evidence_context=evidence_context,
        )
        valid: list[ContextTruthVerificationReceipt] = []
        invalid: list[ContextTruthVerificationReceipt] = []
        issues: list[str] = []
        for row in rows:
            issue = scope_issue or self._validity_issue(
                row,
                truth_context=truth_context,
                evidence=evidence,
                evidence_temporal=evidence_temporal,
                temporal_context=temporal_context,
                source_provenance=source_provenance,
                source_dependence=source_dependence,
                evidence_context=evidence_context,
            )
            if issue is None:
                valid.append(row)
            else:
                invalid.append(row)
                issues.append(issue)

        passing = tuple(row for row in valid if row.passed)
        negative = tuple(sorted(row.receipt_id for row in valid if not row.passed))

        origin_controller_ids: set[str] = set()
        decision_basis_ids: set[str] = set()
        decision_dependence_complete = True
        for source_id in scope.decision_source_ids:
            try:
                origin_controller_ids.update(source_provenance.root_controllers(source_id))
            except KeyError:
                pass
            if source_dependence.current(source_id) is None:
                decision_dependence_complete = False
                issues.append("decision_source_dependence_missing")
            else:
                decision_basis_ids.update(source_dependence.basis_ids(source_id))

        eligible: list[ContextTruthVerificationReceipt] = []
        non_independent: list[str] = []
        for row in passing:
            key = source_provenance.independence_key(row.verifier_id)
            bases = set(source_dependence.basis_ids(row.verifier_id))
            if (
                not decision_dependence_complete
                or key is None
                or key in origin_controller_ids
                or bool(bases & decision_basis_ids)
            ):
                non_independent.append(row.receipt_id)
            else:
                eligible.append(row)

        independence_keys = self._component_keys(
            tuple(eligible),
            source_provenance=source_provenance,
            source_dependence=source_dependence,
        )
        return ContextTruthVerificationCoverage(
            receipts=rows,
            valid_receipt_ids=tuple(sorted(row.receipt_id for row in valid)),
            invalid_receipt_ids=tuple(sorted(row.receipt_id for row in invalid)),
            negative_receipt_ids=negative,
            non_independent_receipt_ids=tuple(sorted(non_independent)),
            passing_independence_keys=independence_keys,
            passing_channels=tuple(
                sorted({row.channel for row in passing}, key=lambda value: value.value)
            ),
            issues=tuple(dict.fromkeys(issues)),
        )

    def scoped_digest(
        self,
        claim_id: str,
        *,
        scope: ContextTruthScope,
        truth_context: TruthContext,
        temporal_context: TemporalContext,
    ) -> str:
        rows = self.current_receipts(
            str(claim_id),
            scope=scope,
            truth_context=truth_context,
            temporal_context=temporal_context,
        )
        return canonical_digest(
            {
                "protocol": PROJECTION_PROTOCOL,
                "binding_mode": CONTEXT_BINDING_MODE,
                "claim_id": str(claim_id),
                "scope_digest": scope.digest,
                "truth_context_digest": truth_context.digest,
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
    def from_state(cls, state: Mapping[str, Any]) -> "ContextTruthVerificationLedger":
        _unexpected(state, {"protocol", "receipts"}, "context verification ledger")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported context verification protocol")
        ledger = cls()
        seen: set[str] = set()
        for value in state.get("receipts", ()):
            row = ContextTruthVerificationReceipt.from_state(value)
            if row.receipt_id in seen:
                raise ValueError("duplicate serialized context verification receipt")
            seen.add(row.receipt_id)
            ledger.record(row)
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "PROJECTION_PROTOCOL",
    "ContextTruthVerificationReceipt",
    "ContextTruthVerificationCoverage",
    "ContextTruthVerificationLedger",
)
