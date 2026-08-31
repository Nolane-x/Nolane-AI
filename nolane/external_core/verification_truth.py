from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .evidence_truth import EvidenceChannel, EvidenceLedger

PARENT_COMPONENT_ID = "external.verification"
TRUTH_PROTOCOL = "truth-verification-ledger-v1"
SCOPED_BINDING_MODE = "dependency-scope-v2"
SCOPED_PROJECTION_PROTOCOL = "truth-verification-scope-v2"
RELATION_SCOPED_BINDING_MODE = "relation-aware-scope-v3"
RELATION_SCOPED_PROJECTION_PROTOCOL = "truth-verification-relation-scope-v3"


def _explicit(value: str | None, field: str) -> str:
    value = "" if value is None else str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _evidence_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError("verification evidence ids must be explicit and unique")
    return rows


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
    binding_mode: str = "global-v1"
    scope_digest: str = ""

    @classmethod
    def create(cls, *, receipt_id: str, claim_id: str, verifier_id: str, source_family: str,
               channel: EvidenceChannel, passed: bool, knowledge_digest: str | None = None,
               epistemic_digest: str | None = None, scope_digest: str | None = None,
               binding_mode: str | None = None,
               evidence_ids: tuple[str, ...] = ()) -> "TruthVerificationReceipt":
        receipt_id = _explicit(receipt_id, "receipt_id")
        claim_id = _explicit(claim_id, "claim_id")
        verifier_id = _explicit(verifier_id, "verifier_id")
        source_family = _explicit(source_family, "source_family")
        evidence_ids = _evidence_ids(tuple(evidence_ids))
        channel = EvidenceChannel(channel)
        passed = bool(passed)

        mode = "" if binding_mode is None else str(binding_mode).strip()
        scope = "" if scope_digest is None else str(scope_digest).strip()
        knowledge = "" if knowledge_digest is None else str(knowledge_digest).strip()
        epistemic = "" if epistemic_digest is None else str(epistemic_digest).strip()
        if mode or scope:
            selected_mode = mode or SCOPED_BINDING_MODE
            if selected_mode not in {SCOPED_BINDING_MODE, RELATION_SCOPED_BINDING_MODE}:
                raise ValueError("unsupported verification binding mode")
            if not scope:
                raise ValueError("scoped verification scope digest must be explicit")
            if knowledge or epistemic:
                raise ValueError("scoped verification cannot mix global state bindings")
            payload = {
                "receipt_id": receipt_id,
                "claim_id": claim_id,
                "verifier_id": verifier_id,
                "source_family": source_family,
                "channel": channel.value,
                "passed": passed,
                "binding_mode": selected_mode,
                "scope_digest": scope,
                "evidence_ids": list(evidence_ids),
            }
            return cls(
                receipt_id, claim_id, verifier_id, source_family, channel, passed,
                "", "", evidence_ids, canonical_digest(payload), selected_mode, scope,
            )

        knowledge = _explicit(knowledge_digest, "knowledge_digest")
        epistemic = _explicit(epistemic_digest, "epistemic_digest")
        payload = {
            "receipt_id": receipt_id,
            "claim_id": claim_id,
            "verifier_id": verifier_id,
            "source_family": source_family,
            "channel": channel.value,
            "passed": passed,
            "knowledge_digest": knowledge,
            "epistemic_digest": epistemic,
            "evidence_ids": list(evidence_ids),
        }
        return cls(
            receipt_id, claim_id, verifier_id, source_family, channel, passed,
            knowledge, epistemic, evidence_ids, canonical_digest(payload), "global-v1", "",
        )

    @property
    def is_dependency_scoped(self) -> bool:
        return self.binding_mode == SCOPED_BINDING_MODE

    @property
    def is_relation_scoped(self) -> bool:
        return self.binding_mode == RELATION_SCOPED_BINDING_MODE

    @property
    def is_scoped(self) -> bool:
        return self.is_dependency_scoped or self.is_relation_scoped

    def payload(self) -> dict[str, Any]:
        if self.is_scoped:
            return {
                "receipt_id": self.receipt_id,
                "claim_id": self.claim_id,
                "verifier_id": self.verifier_id,
                "source_family": self.source_family,
                "channel": self.channel.value,
                "passed": self.passed,
                "binding_mode": self.binding_mode,
                "scope_digest": self.scope_digest,
                "evidence_ids": list(self.evidence_ids),
            }
        return {
            "receipt_id": self.receipt_id,
            "claim_id": self.claim_id,
            "verifier_id": self.verifier_id,
            "source_family": self.source_family,
            "channel": self.channel.value,
            "passed": self.passed,
            "knowledge_digest": self.knowledge_digest,
            "epistemic_digest": self.epistemic_digest,
            "evidence_ids": list(self.evidence_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthVerificationReceipt":
        has_scope_keys = "binding_mode" in state or "scope_digest" in state
        if has_scope_keys:
            mode = str(state.get("binding_mode", ""))
            if mode not in {SCOPED_BINDING_MODE, RELATION_SCOPED_BINDING_MODE}:
                raise ValueError("unsupported verification binding mode")
            if "knowledge_digest" in state or "epistemic_digest" in state:
                raise ValueError("scoped verification state cannot contain global bindings")
            row = cls.create(
                receipt_id=str(state["receipt_id"]), claim_id=str(state["claim_id"]),
                verifier_id=str(state["verifier_id"]), source_family=str(state["source_family"]),
                channel=EvidenceChannel(str(state["channel"])), passed=bool(state["passed"]),
                binding_mode=mode, scope_digest=str(state["scope_digest"]),
                evidence_ids=tuple(str(x) for x in state.get("evidence_ids", ())),
            )
        else:
            row = cls.create(
                receipt_id=str(state["receipt_id"]), claim_id=str(state["claim_id"]),
                verifier_id=str(state["verifier_id"]), source_family=str(state["source_family"]),
                channel=EvidenceChannel(str(state["channel"])), passed=bool(state["passed"]),
                knowledge_digest=str(state["knowledge_digest"]), epistemic_digest=str(state["epistemic_digest"]),
                evidence_ids=tuple(str(x) for x in state.get("evidence_ids", ())),
            )
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

    Raw receipts remain available for audit. V1 binds complete Knowledge/Epistemic state, A8 v2
    binds a dependency-scope digest, and A10 v3 binds a relation-aware scope digest. Every scoped
    selector is exact-mode so one protocol generation cannot masquerade as another.
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
        return tuple(
            row for row in self.receipts(claim_id)
            if not row.is_scoped
            and row.knowledge_digest == str(knowledge_digest)
            and row.epistemic_digest == str(epistemic_digest)
        )

    def scoped_receipts(self, claim_id: str, *, scope_digest: str) -> tuple[TruthVerificationReceipt, ...]:
        scope_digest = str(scope_digest)
        return tuple(
            row for row in self.receipts(claim_id)
            if row.is_dependency_scoped and row.scope_digest == scope_digest
        )

    def relation_scoped_receipts(self, claim_id: str, *, scope_digest: str) -> tuple[TruthVerificationReceipt, ...]:
        scope_digest = str(scope_digest)
        return tuple(
            row for row in self.receipts(claim_id)
            if row.is_relation_scoped and row.scope_digest == scope_digest
        )

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

    @classmethod
    def _coverage(cls, rows: tuple[TruthVerificationReceipt, ...], *, evidence: EvidenceLedger) -> TruthVerificationCoverage:
        valid: list[TruthVerificationReceipt] = []
        invalid: list[TruthVerificationReceipt] = []
        issues: list[str] = []
        for row in rows:
            issue = cls._receipt_provenance_issue(row, evidence)
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

    def coverage(self, claim_id: str, *, knowledge_digest: str, epistemic_digest: str,
                 evidence: EvidenceLedger) -> TruthVerificationCoverage:
        rows = self.bound_receipts(
            str(claim_id), knowledge_digest=str(knowledge_digest), epistemic_digest=str(epistemic_digest),
        )
        return self._coverage(rows, evidence=evidence)

    def coverage_scoped(self, claim_id: str, *, scope_digest: str,
                        evidence: EvidenceLedger) -> TruthVerificationCoverage:
        return self._coverage(
            self.scoped_receipts(str(claim_id), scope_digest=str(scope_digest)), evidence=evidence,
        )

    def coverage_relation_scoped(self, claim_id: str, *, scope_digest: str,
                                 evidence: EvidenceLedger) -> TruthVerificationCoverage:
        return self._coverage(
            self.relation_scoped_receipts(str(claim_id), scope_digest=str(scope_digest)), evidence=evidence,
        )

    def scoped_digest(self, claim_id: str, *, scope_digest: str) -> str:
        rows = self.scoped_receipts(str(claim_id), scope_digest=str(scope_digest))
        return canonical_digest({
            "protocol": SCOPED_PROJECTION_PROTOCOL,
            "claim_id": str(claim_id),
            "scope_digest": str(scope_digest),
            "receipts": [row.to_state() for row in rows],
        })

    def relation_scoped_digest(self, claim_id: str, *, scope_digest: str) -> str:
        rows = self.relation_scoped_receipts(str(claim_id), scope_digest=str(scope_digest))
        return canonical_digest({
            "protocol": RELATION_SCOPED_PROJECTION_PROTOCOL,
            "claim_id": str(claim_id),
            "scope_digest": str(scope_digest),
            "receipts": [row.to_state() for row in rows],
        })

    def independent_passing_channels(self, claim_id: str, *, knowledge_digest: str, epistemic_digest: str) -> int:
        """Compatibility metric over raw v1 receipts; strict Assurance uses validated coverage()."""
        return len({
            row.source_family for row in self.bound_receipts(
                claim_id, knowledge_digest=knowledge_digest, epistemic_digest=epistemic_digest,
            ) if row.passed
        })

    def distinct_passing_channel_kinds(self, claim_id: str, *, knowledge_digest: str, epistemic_digest: str) -> int:
        """Compatibility metric over raw v1 receipts; strict Assurance uses validated coverage()."""
        return len({
            row.channel for row in self.bound_receipts(
                claim_id, knowledge_digest=knowledge_digest, epistemic_digest=epistemic_digest,
            ) if row.passed
        })

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
        seen: set[str] = set()
        for value in state.get("receipts", ()):
            row = TruthVerificationReceipt.from_state(value)
            if row.receipt_id in seen:
                raise ValueError("duplicate serialized verification receipt id")
            seen.add(row.receipt_id)
            ledger.record(row)
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID", "TRUTH_PROTOCOL", "SCOPED_BINDING_MODE", "SCOPED_PROJECTION_PROTOCOL",
    "RELATION_SCOPED_BINDING_MODE", "RELATION_SCOPED_PROJECTION_PROTOCOL",
    "TruthVerificationReceipt", "TruthVerificationCoverage", "TruthVerificationLedger",
)
