from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.software_engineering"
COMPONENT_VERSION = "0.1.0"


class EngineeringEvidenceKind(str, Enum):
    COMPILE = "compile"
    TEST = "test"
    STATIC = "static"
    REPRODUCTION = "reproduction"
    ROOT_CAUSE = "root_cause"
    VISUAL = "visual"
    RESPONSIVE = "responsive"
    ACCESSIBILITY = "accessibility"
    INTERACTION = "interaction"
    SECURITY = "security"
    PERFORMANCE = "performance"
    REVIEW = "review"


class EngineeringPhase(str, Enum):
    PROPOSED = "proposed"
    CLAIMS_BOUND = "claims_bound"
    PRECONDITIONS_VERIFIED = "preconditions_verified"
    APPLIED = "applied"
    OUTCOME_OBSERVED = "outcome_observed"
    POSTCONDITIONS_VERIFIED = "postconditions_verified"
    CANDIDATE_READY = "candidate_ready"
    QUARANTINED = "quarantined"
    ROLLED_BACK = "rolled_back"


class EngineeringDecision(str, Enum):
    CANDIDATE_READY = "candidate_ready"
    BLOCKED = "blocked"
    QUARANTINED = "quarantined"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _refs(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


@dataclass(frozen=True, slots=True)
class EngineeringEvidenceAttestation:
    attestation_id: str
    subject_ref: str
    subject_digest: str
    producer_agent_id: str
    verifier_agent_id: str
    verifier_region: str
    kind: EngineeringEvidenceKind
    passed: bool
    evidence_refs: tuple[str, ...]
    source_revision: str
    environment_digest: str
    dependencies: tuple[str, ...]
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.attestation_id, "attestation id"),
            (self.subject_ref, "subject ref"),
            (self.subject_digest, "subject digest"),
            (self.producer_agent_id, "producer agent"),
            (self.verifier_agent_id, "verifier agent"),
            (self.verifier_region, "verifier region"),
            (self.source_revision, "source revision"),
            (self.environment_digest, "environment digest"),
            (self.digest, "attestation digest"),
        ):
            _text(value, field=field)
        if not self.evidence_refs:
            raise ValueError("engineering evidence requires evidence refs")
        if self.passed and self.verifier_agent_id == self.producer_agent_id:
            raise PermissionError("successful engineering evidence forbids self-verification")
        if self.passed and self.verifier_region != "verification-testing":
            raise PermissionError("successful engineering evidence requires verification-testing authority")

    def payload(self) -> dict[str, Any]:
        return {
            "subject_ref": self.subject_ref,
            "subject_digest": self.subject_digest,
            "producer_agent_id": self.producer_agent_id,
            "verifier_agent_id": self.verifier_agent_id,
            "verifier_region": self.verifier_region,
            "kind": self.kind.value,
            "passed": self.passed,
            "evidence_refs": list(self.evidence_refs),
            "source_revision": self.source_revision,
            "environment_digest": self.environment_digest,
            "dependencies": list(self.dependencies),
        }

    def to_state(self) -> dict[str, Any]:
        return {"attestation_id": self.attestation_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringEvidenceAttestation":
        row = cls(
            attestation_id=_text(state["attestation_id"], field="attestation id"),
            subject_ref=_text(state["subject_ref"], field="subject ref"),
            subject_digest=_text(state["subject_digest"], field="subject digest"),
            producer_agent_id=_text(state["producer_agent_id"], field="producer agent"),
            verifier_agent_id=_text(state["verifier_agent_id"], field="verifier agent"),
            verifier_region=_text(state["verifier_region"], field="verifier region"),
            kind=EngineeringEvidenceKind(str(state["kind"])),
            passed=bool(state["passed"]),
            evidence_refs=_refs(tuple(state.get("evidence_refs", ()))),
            source_revision=_text(state["source_revision"], field="source revision"),
            environment_digest=_text(state["environment_digest"], field="environment digest"),
            dependencies=_refs(tuple(state.get("dependencies", ()))),
            digest=_text(state["digest"], field="attestation digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.attestation_id != f"eng-evidence-{expected[:20]}":
            raise ValueError("engineering evidence digest/id mismatch")
        return row


class EngineeringEvidenceLedger:
    """Content-addressed verification evidence with dependency-aware revocation."""

    def __init__(self) -> None:
        self._rows: dict[str, EngineeringEvidenceAttestation] = {}
        self._revocations: dict[str, str] = {}

    def attestations(self) -> tuple[EngineeringEvidenceAttestation, ...]:
        return tuple(self._rows[key] for key in sorted(self._rows))

    def get(self, attestation_id: str) -> EngineeringEvidenceAttestation:
        try:
            return self._rows[str(attestation_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering evidence: {attestation_id}") from exc

    def record(
        self,
        *,
        subject_ref: str,
        subject_digest: str,
        producer_agent_id: str,
        verifier_agent_id: str,
        verifier_region: str,
        kind: EngineeringEvidenceKind,
        passed: bool,
        evidence_refs: tuple[str, ...],
        source_revision: str,
        environment_digest: str,
        dependencies: tuple[str, ...] = (),
    ) -> EngineeringEvidenceAttestation:
        refs = _refs(evidence_refs)
        if not refs:
            raise ValueError("engineering evidence requires evidence refs")
        payload = {
            "subject_ref": _text(subject_ref, field="subject ref"),
            "subject_digest": _text(subject_digest, field="subject digest"),
            "producer_agent_id": _text(producer_agent_id, field="producer agent"),
            "verifier_agent_id": _text(verifier_agent_id, field="verifier agent"),
            "verifier_region": _text(verifier_region, field="verifier region"),
            "kind": EngineeringEvidenceKind(kind).value,
            "passed": bool(passed),
            "evidence_refs": list(refs),
            "source_revision": _text(source_revision, field="source revision"),
            "environment_digest": _text(environment_digest, field="environment digest"),
            "dependencies": list(_refs(dependencies)),
        }
        digest = canonical_digest(payload)
        row = EngineeringEvidenceAttestation(
            attestation_id=f"eng-evidence-{digest[:20]}",
            subject_ref=payload["subject_ref"],
            subject_digest=payload["subject_digest"],
            producer_agent_id=payload["producer_agent_id"],
            verifier_agent_id=payload["verifier_agent_id"],
            verifier_region=payload["verifier_region"],
            kind=EngineeringEvidenceKind(payload["kind"]),
            passed=payload["passed"],
            evidence_refs=tuple(payload["evidence_refs"]),
            source_revision=payload["source_revision"],
            environment_digest=payload["environment_digest"],
            dependencies=tuple(payload["dependencies"]),
            digest=digest,
        )
        existing = self._rows.get(row.attestation_id)
        if existing is not None and existing != row:
            raise ValueError("engineering evidence id cannot be rebound")
        self._rows[row.attestation_id] = row
        return existing or row

    def revoke(self, source_ref: str, *, reason: str) -> tuple[str, ...]:
        source = _text(source_ref, field="revocation source")
        why = _text(reason, field="revocation reason")
        old_reason = self._revocations.get(source)
        if old_reason is not None and old_reason != why:
            raise ValueError("revocation history cannot be rebound")
        self._revocations.setdefault(source, why)

        affected: set[str] = set()
        frontier = [source]
        visited: set[str] = set()
        while frontier:
            revoked = frontier.pop()
            if revoked in visited:
                continue
            visited.add(revoked)
            for row in self._rows.values():
                if row.attestation_id in affected:
                    continue
                if revoked == row.attestation_id or revoked in row.dependencies:
                    affected.add(row.attestation_id)
                    self._revocations.setdefault(row.attestation_id, why)
                    frontier.append(row.attestation_id)
        return tuple(sorted(affected))

    def is_revoked(self, reference: str) -> bool:
        return str(reference) in self._revocations

    def _lineage_live(self, identity: str, visiting: set[str]) -> bool:
        if identity in visiting or self.is_revoked(identity):
            return False
        row = self._rows.get(identity)
        if row is None:
            return not self.is_revoked(identity)
        if not row.passed:
            return False
        visiting.add(identity)
        try:
            return all(
                not self.is_revoked(dependency)
                and (dependency not in self._rows or self._lineage_live(dependency, visiting))
                for dependency in row.dependencies
            )
        finally:
            visiting.remove(identity)

    def is_valid(
        self,
        attestation_id: str,
        *,
        subject_ref: str,
        subject_digest: str,
        source_revision: str,
    ) -> bool:
        try:
            row = self.get(attestation_id)
        except KeyError:
            return False
        return (
            row.passed
            and row.subject_ref == str(subject_ref)
            and row.subject_digest == str(subject_digest)
            and row.source_revision == str(source_revision)
            and self._lineage_live(row.attestation_id, set())
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "attestations": [row.to_state() for row in self.attestations()],
            "revocations": [
                {"reference": reference, "reason": self._revocations[reference]}
                for reference in sorted(self._revocations)
            ],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringEvidenceLedger":
        ledger = cls()
        for value in state.get("attestations", ()):
            row = EngineeringEvidenceAttestation.from_state(value)
            existing = ledger._rows.get(row.attestation_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound engineering evidence in snapshot")
            ledger._rows[row.attestation_id] = row
        for value in state.get("revocations", ()):
            reference = _text(value["reference"], field="revoked reference")
            reason = _text(value["reason"], field="revocation reason")
            old = ledger._revocations.get(reference)
            if old is not None and old != reason:
                raise ValueError("revocation reference cannot be rebound")
            ledger._revocations[reference] = reason

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(identity: str) -> None:
            if identity in visited:
                return
            if identity in visiting:
                raise ValueError("engineering evidence dependency cycle")
            visiting.add(identity)
            for dependency in ledger._rows[identity].dependencies:
                if dependency in ledger._rows:
                    visit(dependency)
            visiting.remove(identity)
            visited.add(identity)

        for identity in sorted(ledger._rows):
            visit(identity)
        return ledger


@dataclass(frozen=True, slots=True)
class EngineeringPatchTransaction:
    transaction_id: str
    patch_ref: str
    patch_digest: str
    source_revision: str
    rollback_artifact_ref: str
    phase: EngineeringPhase = EngineeringPhase.PROPOSED
    claim_refs: tuple[str, ...] = ()
    precondition_attestation_ids: tuple[str, ...] = ()
    application_ref: str | None = None
    outcome_evidence_refs: tuple[str, ...] = ()
    postcondition_attestation_ids: tuple[str, ...] = ()
    closure_receipt_id: str | None = None
    rollback_ref: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        for value, field in (
            (self.transaction_id, "transaction id"),
            (self.patch_ref, "patch ref"),
            (self.patch_digest, "patch digest"),
            (self.source_revision, "source revision"),
            (self.rollback_artifact_ref, "rollback artifact"),
        ):
            _text(value, field=field)
        if self.phase is not EngineeringPhase.PROPOSED and not self.claim_refs:
            raise ValueError("non-proposed transaction requires source claims")
        if self.phase in {
            EngineeringPhase.PRECONDITIONS_VERIFIED,
            EngineeringPhase.APPLIED,
            EngineeringPhase.OUTCOME_OBSERVED,
            EngineeringPhase.POSTCONDITIONS_VERIFIED,
            EngineeringPhase.CANDIDATE_READY,
        } and not self.precondition_attestation_ids:
            raise ValueError("verified transaction phase requires precondition attestations")
        if self.phase in {
            EngineeringPhase.APPLIED,
            EngineeringPhase.OUTCOME_OBSERVED,
            EngineeringPhase.POSTCONDITIONS_VERIFIED,
            EngineeringPhase.CANDIDATE_READY,
        } and not self.application_ref:
            raise ValueError("applied transaction phase requires application ref")
        if self.phase in {
            EngineeringPhase.OUTCOME_OBSERVED,
            EngineeringPhase.POSTCONDITIONS_VERIFIED,
            EngineeringPhase.CANDIDATE_READY,
        } and not self.outcome_evidence_refs:
            raise ValueError("observed transaction phase requires outcome evidence")
        if self.phase in {
            EngineeringPhase.POSTCONDITIONS_VERIFIED,
            EngineeringPhase.CANDIDATE_READY,
        } and not self.postcondition_attestation_ids:
            raise ValueError("postcondition transaction phase requires attestations")
        if self.phase is EngineeringPhase.CANDIDATE_READY and not self.closure_receipt_id:
            raise ValueError("candidate-ready transaction requires closure receipt")
        if self.phase is EngineeringPhase.QUARANTINED and not self.failure_reason:
            raise ValueError("quarantined transaction requires reason")
        if self.phase is EngineeringPhase.ROLLED_BACK and (not self.rollback_ref or not self.failure_reason):
            raise ValueError("rolled-back transaction requires rollback ref and reason")

    def to_state(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "source_revision": self.source_revision,
            "rollback_artifact_ref": self.rollback_artifact_ref,
            "phase": self.phase.value,
            "claim_refs": list(self.claim_refs),
            "precondition_attestation_ids": list(self.precondition_attestation_ids),
            "application_ref": self.application_ref,
            "outcome_evidence_refs": list(self.outcome_evidence_refs),
            "postcondition_attestation_ids": list(self.postcondition_attestation_ids),
            "closure_receipt_id": self.closure_receipt_id,
            "rollback_ref": self.rollback_ref,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringPatchTransaction":
        return cls(
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            source_revision=_text(state["source_revision"], field="source revision"),
            rollback_artifact_ref=_text(state["rollback_artifact_ref"], field="rollback artifact"),
            phase=EngineeringPhase(str(state.get("phase", EngineeringPhase.PROPOSED.value))),
            claim_refs=_refs(tuple(state.get("claim_refs", ()))),
            precondition_attestation_ids=_refs(tuple(state.get("precondition_attestation_ids", ()))),
            application_ref=None if state.get("application_ref") is None else _text(state["application_ref"], field="application ref"),
            outcome_evidence_refs=_refs(tuple(state.get("outcome_evidence_refs", ()))),
            postcondition_attestation_ids=_refs(tuple(state.get("postcondition_attestation_ids", ()))),
            closure_receipt_id=None if state.get("closure_receipt_id") is None else _text(state["closure_receipt_id"], field="closure receipt"),
            rollback_ref=None if state.get("rollback_ref") is None else _text(state["rollback_ref"], field="rollback ref"),
            failure_reason=None if state.get("failure_reason") is None else _text(state["failure_reason"], field="failure reason"),
        )


class PatchTransactionLedger:
    """Fail-closed patch mutation lifecycle adapted from Nolane World actions."""

    def __init__(self, evidence: EngineeringEvidenceLedger) -> None:
        self.evidence = evidence
        self._transactions: dict[str, EngineeringPatchTransaction] = {}
        self._counter = 0

    def transactions(self) -> tuple[EngineeringPatchTransaction, ...]:
        return tuple(self._transactions[key] for key in sorted(self._transactions))

    def get(self, transaction_id: str) -> EngineeringPatchTransaction:
        try:
            return self._transactions[str(transaction_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering patch transaction: {transaction_id}") from exc

    def _store(self, row: EngineeringPatchTransaction) -> EngineeringPatchTransaction:
        self._transactions[row.transaction_id] = row
        return row

    @staticmethod
    def _require_phase(row: EngineeringPatchTransaction, *allowed: EngineeringPhase) -> None:
        if row.phase not in allowed:
            choices = ", ".join(value.value for value in allowed)
            raise ValueError(f"transaction phase {row.phase.value} does not allow operation; expected {choices}")

    def begin(
        self,
        *,
        patch_ref: str,
        patch_digest: str,
        source_revision: str,
        rollback_artifact_ref: str,
    ) -> EngineeringPatchTransaction:
        self._counter += 1
        row = EngineeringPatchTransaction(
            transaction_id=f"eng-tx-{self._counter:08d}",
            patch_ref=_text(patch_ref, field="patch ref"),
            patch_digest=_text(patch_digest, field="patch digest"),
            source_revision=_text(source_revision, field="source revision"),
            rollback_artifact_ref=_text(rollback_artifact_ref, field="rollback artifact"),
        )
        self._transactions[row.transaction_id] = row
        return row

    def bind_claims(self, transaction_id: str, *, claim_refs: tuple[str, ...]) -> EngineeringPatchTransaction:
        old = self.get(transaction_id)
        self._require_phase(old, EngineeringPhase.PROPOSED)
        claims = _refs(claim_refs)
        if not claims:
            raise ValueError("patch transaction requires source claims")
        return self._store(replace(old, phase=EngineeringPhase.CLAIMS_BOUND, claim_refs=claims))

    def _validate_attestations(
        self,
        row: EngineeringPatchTransaction,
        attestation_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        identities = _refs(attestation_ids)
        if not identities:
            raise ValueError("transaction verification requires attestations")
        for identity in identities:
            if not self.evidence.is_valid(
                identity,
                subject_ref=row.patch_ref,
                subject_digest=row.patch_digest,
                source_revision=row.source_revision,
            ):
                raise PermissionError(f"invalid engineering attestation for transaction: {identity}")
        return identities

    def verify_preconditions(
        self, transaction_id: str, *, attestation_ids: tuple[str, ...]
    ) -> EngineeringPatchTransaction:
        old = self.get(transaction_id)
        self._require_phase(old, EngineeringPhase.CLAIMS_BOUND)
        identities = self._validate_attestations(old, attestation_ids)
        return self._store(replace(
            old,
            phase=EngineeringPhase.PRECONDITIONS_VERIFIED,
            precondition_attestation_ids=identities,
        ))

    def mark_applied(self, transaction_id: str, *, application_ref: str) -> EngineeringPatchTransaction:
        old = self.get(transaction_id)
        self._require_phase(old, EngineeringPhase.PRECONDITIONS_VERIFIED)
        return self._store(replace(
            old,
            phase=EngineeringPhase.APPLIED,
            application_ref=_text(application_ref, field="application ref"),
        ))

    def observe_outcome(
        self, transaction_id: str, *, evidence_refs: tuple[str, ...]
    ) -> EngineeringPatchTransaction:
        old = self.get(transaction_id)
        self._require_phase(old, EngineeringPhase.APPLIED)
        refs = _refs(evidence_refs)
        if not refs:
            raise ValueError("applied patch requires observed outcome evidence")
        return self._store(replace(
            old,
            phase=EngineeringPhase.OUTCOME_OBSERVED,
            outcome_evidence_refs=refs,
        ))

    def verify_postconditions(
        self, transaction_id: str, *, attestation_ids: tuple[str, ...]
    ) -> EngineeringPatchTransaction:
        old = self.get(transaction_id)
        self._require_phase(old, EngineeringPhase.OUTCOME_OBSERVED)
        identities = self._validate_attestations(old, attestation_ids)
        return self._store(replace(
            old,
            phase=EngineeringPhase.POSTCONDITIONS_VERIFIED,
            postcondition_attestation_ids=identities,
        ))

    def mark_candidate_ready(
        self, transaction_id: str, *, closure_receipt_id: str
    ) -> EngineeringPatchTransaction:
        old = self.get(transaction_id)
        self._require_phase(old, EngineeringPhase.POSTCONDITIONS_VERIFIED)
        return self._store(replace(
            old,
            phase=EngineeringPhase.CANDIDATE_READY,
            closure_receipt_id=_text(closure_receipt_id, field="closure receipt"),
        ))

    def quarantine(self, transaction_id: str, *, reason: str) -> EngineeringPatchTransaction:
        old = self.get(transaction_id)
        self._require_phase(
            old,
            EngineeringPhase.PRECONDITIONS_VERIFIED,
            EngineeringPhase.APPLIED,
            EngineeringPhase.OUTCOME_OBSERVED,
            EngineeringPhase.POSTCONDITIONS_VERIFIED,
        )
        return self._store(replace(
            old,
            phase=EngineeringPhase.QUARANTINED,
            failure_reason=_text(reason, field="quarantine reason"),
        ))

    def rollback(
        self, transaction_id: str, *, rollback_ref: str, reason: str
    ) -> EngineeringPatchTransaction:
        old = self.get(transaction_id)
        self._require_phase(
            old,
            EngineeringPhase.APPLIED,
            EngineeringPhase.OUTCOME_OBSERVED,
            EngineeringPhase.POSTCONDITIONS_VERIFIED,
            EngineeringPhase.QUARANTINED,
        )
        return self._store(replace(
            old,
            phase=EngineeringPhase.ROLLED_BACK,
            rollback_ref=_text(rollback_ref, field="rollback ref"),
            failure_reason=_text(reason, field="rollback reason"),
        ))

    def to_state(self) -> dict[str, Any]:
        return {
            "counter": self._counter,
            "transactions": [row.to_state() for row in self.transactions()],
        }

    @classmethod
    def from_state(
        cls, *, evidence: EngineeringEvidenceLedger, state: Mapping[str, Any]
    ) -> "PatchTransactionLedger":
        ledger = cls(evidence)
        for value in state.get("transactions", ()):
            row = EngineeringPatchTransaction.from_state(value)
            if row.transaction_id in ledger._transactions:
                raise ValueError("duplicate engineering transaction id")
            ledger._transactions[row.transaction_id] = row
        ledger._counter = int(state.get("counter", len(ledger._transactions)))
        maximum = 0
        for identity in ledger._transactions:
            try:
                maximum = max(maximum, int(identity.rsplit("-", 1)[1]))
            except Exception as exc:
                raise ValueError("non-canonical engineering transaction id") from exc
        if ledger._counter < maximum:
            raise ValueError("engineering transaction counter behind history")
        return ledger


@dataclass(frozen=True, slots=True)
class EngineeringClosureReceipt:
    receipt_id: str
    patch_ref: str
    patch_digest: str
    transaction_id: str
    source_revision: str
    coding_readiness_receipt_id: str
    coding_readiness_digest: str
    debug_resolution_id: str | None
    debug_resolution_digest: str | None
    ui_readiness_receipt_id: str | None
    ui_readiness_digest: str | None
    attestation_ids: tuple[str, ...]
    ready: bool
    decision: EngineeringDecision
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        if self.authority != "candidate_only":
            raise ValueError("engineering closure cannot hold promotion authority")
        if self.ready:
            if self.decision is not EngineeringDecision.CANDIDATE_READY or self.reasons:
                raise ValueError("ready closure must be clean candidate-ready")
        elif self.decision is EngineeringDecision.CANDIDATE_READY:
            raise ValueError("blocked closure cannot claim candidate-ready decision")

    def payload(self) -> dict[str, Any]:
        return {
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "transaction_id": self.transaction_id,
            "source_revision": self.source_revision,
            "coding_readiness_receipt_id": self.coding_readiness_receipt_id,
            "coding_readiness_digest": self.coding_readiness_digest,
            "debug_resolution_id": self.debug_resolution_id,
            "debug_resolution_digest": self.debug_resolution_digest,
            "ui_readiness_receipt_id": self.ui_readiness_receipt_id,
            "ui_readiness_digest": self.ui_readiness_digest,
            "attestation_ids": list(self.attestation_ids),
            "ready": self.ready,
            "decision": self.decision.value,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringClosureReceipt":
        row = cls(
            receipt_id=_text(state["receipt_id"], field="closure receipt id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            source_revision=_text(state["source_revision"], field="source revision"),
            coding_readiness_receipt_id=_text(state["coding_readiness_receipt_id"], field="coding readiness id"),
            coding_readiness_digest=_text(state["coding_readiness_digest"], field="coding readiness digest"),
            debug_resolution_id=None if state.get("debug_resolution_id") is None else _text(state["debug_resolution_id"], field="debug resolution id"),
            debug_resolution_digest=None if state.get("debug_resolution_digest") is None else _text(state["debug_resolution_digest"], field="debug resolution digest"),
            ui_readiness_receipt_id=None if state.get("ui_readiness_receipt_id") is None else _text(state["ui_readiness_receipt_id"], field="ui readiness id"),
            ui_readiness_digest=None if state.get("ui_readiness_digest") is None else _text(state["ui_readiness_digest"], field="ui readiness digest"),
            attestation_ids=_refs(tuple(state.get("attestation_ids", ()))),
            ready=bool(state["ready"]),
            decision=EngineeringDecision(str(state["decision"])),
            reasons=_refs(tuple(state.get("reasons", ()))),
            authority=_text(state["authority"], field="closure authority"),
            digest=_text(state["digest"], field="closure digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f"eng-closure-{expected[:20]}":
            raise ValueError("engineering closure receipt digest/id mismatch")
        return row


class SoftwareEngineeringClosureEngine:
    """Cross-surface F closure with deliberately candidate-only authority."""

    def __init__(
        self,
        *,
        evidence: EngineeringEvidenceLedger,
        transactions: PatchTransactionLedger,
    ) -> None:
        self.evidence = evidence
        self.transactions = transactions
        self._receipts: dict[str, EngineeringClosureReceipt] = {}

    def receipts(self) -> tuple[EngineeringClosureReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def get(self, receipt_id: str) -> EngineeringClosureReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering closure receipt: {receipt_id}") from exc

    @staticmethod
    def _value(value: Any) -> str:
        return "" if value is None else str(value)

    def assess(
        self,
        *,
        patch: Any,
        coding_readiness: Any,
        transaction_id: str,
        current_source_revision: str,
        required_attestation_kinds: tuple[EngineeringEvidenceKind, ...],
        attestation_ids: tuple[str, ...],
        require_debug: bool = False,
        debug_resolution: Any | None = None,
        require_ui: bool = False,
        ui_readiness: Any | None = None,
    ) -> EngineeringClosureReceipt:
        patch_ref = _text(getattr(patch, "patch_id"), field="patch id")
        producer_agent_id = _text(getattr(patch, "producer_agent_id"), field="patch producer")
        if not hasattr(patch, "to_state"):
            raise TypeError("engineering closure requires canonical patch state")
        patch_digest = canonical_digest(patch.to_state())
        tx = self.transactions.get(transaction_id)
        source_revision = _text(current_source_revision, field="current source revision")
        identities = _refs(attestation_ids)
        required = tuple(sorted(
            {EngineeringEvidenceKind(kind) for kind in required_attestation_kinds},
            key=lambda value: value.value,
        ))
        reasons: list[str] = []

        if tx.patch_ref != patch_ref or tx.patch_digest != patch_digest:
            reasons.append("patch_transaction_identity_mismatch")
        if tx.phase is not EngineeringPhase.POSTCONDITIONS_VERIFIED:
            reasons.append("transaction_not_postcondition_verified")
        if tx.source_revision != source_revision:
            reasons.append("stale_source_revision")
        if not set(tx.postcondition_attestation_ids).issubset(set(identities)):
            reasons.append("transaction_evidence_scope_mismatch")

        coding_id = self._value(getattr(coding_readiness, "receipt_id", None))
        coding_digest = self._value(getattr(coding_readiness, "digest", None))
        if not coding_id or not coding_digest:
            reasons.append("missing_coding_readiness_identity")
        if self._value(getattr(coding_readiness, "patch_id", None)) != patch_ref:
            reasons.append("coding_readiness_lineage_mismatch")
        if not bool(getattr(coding_readiness, "ready", False)):
            reasons.append("coding_readiness_not_ready")
        verification = getattr(coding_readiness, "verification", None)
        if verification is None:
            reasons.append("missing_coding_verification")
        elif self._value(getattr(verification, "verifier_agent_id", None)) == producer_agent_id:
            reasons.append("self_verification_forbidden")

        valid_rows: list[EngineeringEvidenceAttestation] = []
        invalid = False
        for identity in identities:
            try:
                row = self.evidence.get(identity)
            except KeyError:
                invalid = True
                continue
            if not self.evidence.is_valid(
                identity,
                subject_ref=patch_ref,
                subject_digest=patch_digest,
                source_revision=tx.source_revision,
            ):
                invalid = True
                continue
            valid_rows.append(row)
        if invalid:
            reasons.append("revoked_or_invalid_evidence")
        kinds = {row.kind for row in valid_rows}
        for kind in required:
            if kind not in kinds:
                reasons.append(f"missing_{kind.value}_attestation")

        debug_id: str | None = None
        debug_digest: str | None = None
        if require_debug:
            if debug_resolution is None:
                reasons.append("missing_debug_resolution")
            else:
                debug_id = self._value(getattr(debug_resolution, "resolution_id", None)) or None
                debug_digest = self._value(getattr(debug_resolution, "digest", None)) or None
                if not debug_id or not debug_digest:
                    reasons.append("missing_debug_resolution_identity")
                if (
                    self._value(getattr(debug_resolution, "patch_id", None)) != patch_ref
                    or self._value(getattr(debug_resolution, "coding_readiness_receipt_id", None)) != coding_id
                ):
                    reasons.append("debug_resolution_lineage_mismatch")

        ui_id: str | None = None
        ui_digest: str | None = None
        if require_ui:
            if ui_readiness is None:
                reasons.append("missing_ui_readiness")
            else:
                ui_id = self._value(getattr(ui_readiness, "receipt_id", None)) or None
                ui_digest = self._value(getattr(ui_readiness, "digest", None)) or None
                if not ui_id or not ui_digest:
                    reasons.append("missing_ui_readiness_identity")
                if not bool(getattr(ui_readiness, "ready", False)):
                    reasons.append("ui_readiness_not_ready")
                if (
                    self._value(getattr(ui_readiness, "patch_id", None)) != patch_ref
                    or self._value(getattr(ui_readiness, "coding_readiness_receipt_id", None)) != coding_id
                ):
                    reasons.append("ui_readiness_lineage_mismatch")

        normalized_reasons = tuple(sorted(set(reasons)))
        ready = not normalized_reasons
        decision = EngineeringDecision.CANDIDATE_READY if ready else EngineeringDecision.BLOCKED
        payload = {
            "patch_ref": patch_ref,
            "patch_digest": patch_digest,
            "transaction_id": tx.transaction_id,
            "source_revision": source_revision,
            "coding_readiness_receipt_id": coding_id,
            "coding_readiness_digest": coding_digest,
            "debug_resolution_id": debug_id,
            "debug_resolution_digest": debug_digest,
            "ui_readiness_receipt_id": ui_id,
            "ui_readiness_digest": ui_digest,
            "attestation_ids": list(identities),
            "ready": ready,
            "decision": decision.value,
            "reasons": list(normalized_reasons),
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringClosureReceipt(
            receipt_id=f"eng-closure-{digest[:20]}",
            patch_ref=patch_ref,
            patch_digest=patch_digest,
            transaction_id=tx.transaction_id,
            source_revision=source_revision,
            coding_readiness_receipt_id=coding_id,
            coding_readiness_digest=coding_digest,
            debug_resolution_id=debug_id,
            debug_resolution_digest=debug_digest,
            ui_readiness_receipt_id=ui_id,
            ui_readiness_digest=ui_digest,
            attestation_ids=identities,
            ready=ready,
            decision=decision,
            reasons=normalized_reasons,
            authority="candidate_only",
            digest=digest,
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("engineering closure receipt cannot be rebound")
        self._receipts[row.receipt_id] = row
        if row.ready:
            self.transactions.mark_candidate_ready(
                tx.transaction_id,
                closure_receipt_id=row.receipt_id,
            )
        return existing or row

    def to_state(self) -> dict[str, Any]:
        return {"receipts": [row.to_state() for row in self.receipts()]}

    @classmethod
    def from_state(
        cls,
        *,
        evidence: EngineeringEvidenceLedger,
        transactions: PatchTransactionLedger,
        state: Mapping[str, Any],
    ) -> "SoftwareEngineeringClosureEngine":
        engine = cls(evidence=evidence, transactions=transactions)
        for value in state.get("receipts", ()):
            row = EngineeringClosureReceipt.from_state(value)
            tx = transactions.get(row.transaction_id)
            if (
                row.patch_ref != tx.patch_ref
                or row.patch_digest != tx.patch_digest
                or row.source_revision != tx.source_revision
            ):
                raise ValueError("closure snapshot transaction lineage mismatch")
            if row.ready:
                if (
                    tx.phase is not EngineeringPhase.CANDIDATE_READY
                    or tx.closure_receipt_id != row.receipt_id
                ):
                    raise ValueError("closure snapshot closure lineage mismatch")
                if not set(tx.postcondition_attestation_ids).issubset(set(row.attestation_ids)):
                    raise ValueError("closure snapshot evidence lineage mismatch")
                for identity in row.attestation_ids:
                    if not evidence.is_valid(
                        identity,
                        subject_ref=row.patch_ref,
                        subject_digest=row.patch_digest,
                        source_revision=row.source_revision,
                    ):
                        raise ValueError("closure snapshot contains invalid evidence")
            elif tx.closure_receipt_id == row.receipt_id:
                raise ValueError("blocked closure cannot own transaction closure linkage")
            existing = engine._receipts.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound engineering closure receipt")
            engine._receipts[row.receipt_id] = row
        return engine


__all__ = (
    "EngineeringEvidenceKind",
    "EngineeringPhase",
    "EngineeringDecision",
    "EngineeringEvidenceAttestation",
    "EngineeringEvidenceLedger",
    "EngineeringPatchTransaction",
    "PatchTransactionLedger",
    "EngineeringClosureReceipt",
    "SoftwareEngineeringClosureEngine",
)
