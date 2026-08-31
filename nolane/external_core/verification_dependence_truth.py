from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .epistemic_dependence_truth import (
    DEPENDENCE_BINDING_MODE,
    DependenceTruthScope,
)
from .evidence_dependence_truth import SourceDependenceRegistry
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceChannel, EvidenceLedger
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.verification"
TRUTH_PROTOCOL = (
    "truth-verification-dependence-defeasible-justification-provenance-"
    "lineage-temporal-v8"
)
PROJECTION_PROTOCOL = (
    "truth-verification-dependence-defeasible-justification-provenance-projection-v8"
)
_COMPONENT_PROTOCOL = "truth-verification-dependence-component-v8"


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
class DependenceTruthVerificationReceipt:
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
    source_dependence_digest: str
    digest: str
    binding_mode: str = DEPENDENCE_BINDING_MODE

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
        source_dependence_digest: str,
    ) -> "DependenceTruthVerificationReceipt":
        receipt_id = _explicit(receipt_id, "dependence verification receipt id")
        claim_id = _explicit(claim_id, "dependence verification claim id")
        verifier_id = _explicit(verifier_id, "dependence verifier id")
        scope_digest = _explicit(scope_digest, "dependence scope digest")
        temporal_context_digest = _explicit(
            temporal_context_digest,
            "dependence verification temporal context digest",
        )
        context = TemporalContext.create(as_of=as_of)
        if context.digest != temporal_context_digest:
            raise ValueError("dependence verification temporal context digest mismatch")
        evidence_ids = _ids(tuple(evidence_ids), "dependence verification evidence ids")
        source_provenance_digest = _explicit(
            source_provenance_digest,
            "dependence verifier provenance digest",
        )
        source_dependence_digest = _explicit(
            source_dependence_digest,
            "dependence verifier source-dependence digest",
        )
        channel = EvidenceChannel(channel)
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": DEPENDENCE_BINDING_MODE,
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
            "source_dependence_digest": source_dependence_digest,
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
            source_dependence_digest,
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
            "source_dependence_digest": self.source_dependence_digest,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "DependenceTruthVerificationReceipt":
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
                "source_dependence_digest",
                "digest",
            },
            "dependence verification receipt",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported dependence verification protocol")
        if str(state.get("binding_mode", "")) != DEPENDENCE_BINDING_MODE:
            raise ValueError("unsupported dependence verification binding mode")
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
            source_dependence_digest=str(state["source_dependence_digest"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("dependence verification receipt digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class DependenceTruthVerificationCoverage:
    receipts: tuple[DependenceTruthVerificationReceipt, ...]
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


class DependenceTruthVerificationLedger:
    """Dedicated v8 verification ledger with common-basis independence collapse."""

    def __init__(self) -> None:
        self._receipts: dict[str, DependenceTruthVerificationReceipt] = {}

    def record(
        self,
        row: DependenceTruthVerificationReceipt,
    ) -> DependenceTruthVerificationReceipt:
        if not isinstance(row, DependenceTruthVerificationReceipt):
            raise TypeError("dependence verification ledger accepts v8 receipts only")
        old = self._receipts.get(row.receipt_id)
        if old is not None and old != row:
            raise ValueError("dependence verification receipt id collision")
        self._receipts[row.receipt_id] = row
        return row

    def receipts(
        self,
        claim_id: str | None = None,
    ) -> tuple[DependenceTruthVerificationReceipt, ...]:
        rows = tuple(self._receipts.values())
        if claim_id is not None:
            rows = tuple(row for row in rows if row.claim_id == str(claim_id))
        return tuple(sorted(rows, key=lambda row: row.receipt_id))

    @staticmethod
    def receipt_is_current(
        receipt: DependenceTruthVerificationReceipt,
        *,
        scope: DependenceTruthScope,
        temporal_context: TemporalContext,
    ) -> bool:
        if not isinstance(receipt, DependenceTruthVerificationReceipt):
            return False
        if not isinstance(scope, DependenceTruthScope):
            return False
        if not isinstance(temporal_context, TemporalContext):
            return False
        return (
            receipt.binding_mode == DEPENDENCE_BINDING_MODE
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
        scope: DependenceTruthScope,
        temporal_context: TemporalContext,
    ) -> tuple[DependenceTruthVerificationReceipt, ...]:
        return tuple(
            row
            for row in self.receipts(str(claim_id))
            if self.receipt_is_current(row, scope=scope, temporal_context=temporal_context)
        )

    @staticmethod
    def _validity_issue(
        row: DependenceTruthVerificationReceipt,
        *,
        evidence: EvidenceLedger,
        evidence_temporal: TemporalEvidenceView,
        temporal_context: TemporalContext,
        source_provenance: SourceProvenanceRegistry,
        source_dependence: SourceDependenceRegistry,
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

    @staticmethod
    def _component_keys(
        rows: tuple[DependenceTruthVerificationReceipt, ...],
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
        scope: DependenceTruthScope,
        temporal_context: TemporalContext,
        evidence: EvidenceLedger,
        evidence_temporal: TemporalEvidenceView,
        source_provenance: SourceProvenanceRegistry,
        source_dependence: SourceDependenceRegistry,
    ) -> DependenceTruthVerificationCoverage:
        rows = self.current_receipts(
            str(claim_id),
            scope=scope,
            temporal_context=temporal_context,
        )
        valid: list[DependenceTruthVerificationReceipt] = []
        invalid: list[DependenceTruthVerificationReceipt] = []
        issues: list[str] = []
        for row in rows:
            issue = self._validity_issue(
                row,
                evidence=evidence,
                evidence_temporal=evidence_temporal,
                temporal_context=temporal_context,
                source_provenance=source_provenance,
                source_dependence=source_dependence,
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

        eligible: list[DependenceTruthVerificationReceipt] = []
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
        return DependenceTruthVerificationCoverage(
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
        scope: DependenceTruthScope,
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
                "binding_mode": DEPENDENCE_BINDING_MODE,
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
    def from_state(cls, state: Mapping[str, Any]) -> "DependenceTruthVerificationLedger":
        _unexpected(state, {"protocol", "receipts"}, "dependence verification ledger")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported dependence verification protocol")
        ledger = cls()
        seen: set[str] = set()
        for value in state.get("receipts", ()):
            row = DependenceTruthVerificationReceipt.from_state(value)
            if row.receipt_id in seen:
                raise ValueError("duplicate serialized dependence verification receipt")
            seen.add(row.receipt_id)
            ledger.record(row)
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "PROJECTION_PROTOCOL",
    "DependenceTruthVerificationReceipt",
    "DependenceTruthVerificationCoverage",
    "DependenceTruthVerificationLedger",
)
