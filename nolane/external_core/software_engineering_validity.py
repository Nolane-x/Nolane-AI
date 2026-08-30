from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import (
    ClaimMode,
    ClaimStatus,
    CodeClaim,
    CodeClaimLedger,
)
from nolane.external_core.software_engineering import (
    EngineeringEvidenceLedger,
    EngineeringPhase,
    PatchTransactionLedger,
    SoftwareEngineeringClosureEngine,
)


COMPONENT_ID = "external.software_engineering.validity"
COMPONENT_VERSION = "0.2.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _refs(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


def _path_under(path: str, prefix: str) -> bool:
    normalized_path = str(path).replace("\\", "/").strip()
    normalized_prefix = str(prefix).replace("\\", "/").strip().rstrip("/")
    return normalized_path == normalized_prefix or normalized_path.startswith(normalized_prefix + "/")


def _scopes_cover_patch(scopes: Sequence[Any], patch: Any) -> bool:
    required_attrs = ("producer_agent_id", "task_id", "touched_files", "touched_symbols")
    if not scopes or not all(hasattr(patch, name) for name in required_attrs):
        return False
    producer = str(patch.producer_agent_id)
    task_id = str(patch.task_id)
    for scope in scopes:
        if (
            scope.status is not ClaimStatus.ACTIVE
            or scope.mode is not ClaimMode.EXCLUSIVE_WRITE
            or scope.agent_id != producer
            or scope.task_id != task_id
        ):
            return False
    for raw_path in tuple(patch.touched_files):
        path = str(raw_path).replace("\\", "/").strip()
        if not any(
            path in scope.file_paths
            or any(_path_under(path, prefix) for prefix in scope.directory_prefixes)
            for scope in scopes
        ):
            return False
    for raw_symbol in tuple(patch.touched_symbols):
        symbol = str(raw_symbol).strip()
        if not any(symbol in scope.symbol_ids for scope in scopes):
            return False
    return True


class EngineeringValidityDecision(str, Enum):
    CURRENT_VALID = "current_valid"
    STALE = "stale"
    BLOCKED = "blocked"


class EngineeringMutationAuthorityDecision(str, Enum):
    AUTHORIZED = "authorized"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class EngineeringBoundClaimSnapshot:
    claim_id: str
    agent_id: str
    task_id: str
    file_paths: tuple[str, ...]
    symbol_ids: tuple[str, ...]
    directory_prefixes: tuple[str, ...]
    mode: ClaimMode
    status: ClaimStatus
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "file_paths": list(self.file_paths),
            "symbol_ids": list(self.symbol_ids),
            "directory_prefixes": list(self.directory_prefixes),
            "mode": self.mode.value,
            "status": self.status.value,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_claim(cls, claim: CodeClaim) -> "EngineeringBoundClaimSnapshot":
        payload = claim.to_state()
        digest = canonical_digest(payload)
        return cls(
            claim_id=claim.claim_id,
            agent_id=claim.agent_id,
            task_id=claim.task_id,
            file_paths=tuple(claim.file_paths),
            symbol_ids=tuple(claim.symbol_ids),
            directory_prefixes=tuple(claim.directory_prefixes),
            mode=claim.mode,
            status=claim.status,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringBoundClaimSnapshot":
        row = cls(
            claim_id=_text(state["claim_id"], field="claim id"),
            agent_id=_text(state["agent_id"], field="claim agent"),
            task_id=_text(state["task_id"], field="claim task"),
            file_paths=_refs(tuple(state.get("file_paths", ()))),
            symbol_ids=_refs(tuple(state.get("symbol_ids", ()))),
            directory_prefixes=tuple(value.rstrip("/") for value in _refs(tuple(state.get("directory_prefixes", ())))),
            mode=ClaimMode(str(state["mode"])),
            status=ClaimStatus(str(state["status"])),
            digest=_text(state["digest"], field="claim snapshot digest"),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("engineering bound claim snapshot digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringClaimBinding:
    binding_id: str
    transaction_id: str
    claim_snapshots: tuple[EngineeringBoundClaimSnapshot, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        _text(self.binding_id, field="claim binding id")
        _text(self.transaction_id, field="transaction id")
        if not self.claim_snapshots:
            raise ValueError("engineering claim binding requires at least one claim")
        claim_ids = [row.claim_id for row in self.claim_snapshots]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("engineering claim binding contains duplicate claim ids")
        if self.authority != "mutation_scope_only":
            raise ValueError("claim binding cannot grant broader authority")

    @property
    def claim_state_digests(self) -> tuple[tuple[str, str], ...]:
        return tuple((row.claim_id, row.digest) for row in self.claim_snapshots)

    def payload(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "claims": [row.to_state() for row in self.claim_snapshots],
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"binding_id": self.binding_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringClaimBinding":
        snapshots = tuple(sorted(
            (EngineeringBoundClaimSnapshot.from_state(value) for value in state.get("claims", ())),
            key=lambda row: row.claim_id,
        ))
        row = cls(
            binding_id=_text(state["binding_id"], field="claim binding id"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            claim_snapshots=snapshots,
            authority=_text(state["authority"], field="claim binding authority"),
            digest=_text(state["digest"], field="claim binding digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.binding_id != f"eng-claim-binding-{expected[:20]}":
            raise ValueError("engineering claim binding digest/id mismatch")
        return row


class EngineeringClaimBindingLedger:
    """Historical authorization proof plus current mutation-scope inspection."""

    def __init__(
        self,
        *,
        transactions: PatchTransactionLedger,
        claims: CodeClaimLedger,
    ) -> None:
        self.transactions = transactions
        self.claims = claims
        self._bindings: dict[str, EngineeringClaimBinding] = {}
        self._by_transaction: dict[str, str] = {}

    def bindings(self) -> tuple[EngineeringClaimBinding, ...]:
        return tuple(self._bindings[key] for key in sorted(self._bindings))

    def get(self, binding_id: str) -> EngineeringClaimBinding:
        try:
            return self._bindings[str(binding_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering claim binding: {binding_id}") from exc

    def for_transaction(self, transaction_id: str) -> EngineeringClaimBinding | None:
        binding_id = self._by_transaction.get(str(transaction_id))
        return None if binding_id is None else self._bindings[binding_id]

    def bind(self, transaction_id: str) -> EngineeringClaimBinding:
        tx = self.transactions.get(transaction_id)
        if tx.phase not in {EngineeringPhase.CLAIMS_BOUND, EngineeringPhase.PRECONDITIONS_VERIFIED}:
            raise ValueError("engineering claims must be snapshotted before patch application")
        if not tx.claim_refs:
            raise ValueError("engineering transaction has no mutation claims")

        snapshots: list[EngineeringBoundClaimSnapshot] = []
        for claim_id in sorted(tx.claim_refs):
            claim = self.claims.get(claim_id)
            if claim.status is not ClaimStatus.ACTIVE:
                raise PermissionError(f"mutation claim is not active: {claim_id}")
            if claim.mode is not ClaimMode.EXCLUSIVE_WRITE:
                raise PermissionError(f"mutation claim must be exclusive write: {claim_id}")
            snapshots.append(EngineeringBoundClaimSnapshot.from_claim(claim))

        payload = {
            "transaction_id": tx.transaction_id,
            "claims": [row.to_state() for row in snapshots],
            "authority": "mutation_scope_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringClaimBinding(
            binding_id=f"eng-claim-binding-{digest[:20]}",
            transaction_id=tx.transaction_id,
            claim_snapshots=tuple(snapshots),
            authority="mutation_scope_only",
            digest=digest,
        )
        previous_binding_id = self._by_transaction.get(tx.transaction_id)
        if previous_binding_id is not None and previous_binding_id != row.binding_id:
            raise ValueError("engineering transaction claim binding cannot be rebound")
        existing = self._bindings.get(row.binding_id)
        if existing is not None and existing != row:
            raise ValueError("engineering claim binding id cannot be rebound")
        self._bindings[row.binding_id] = row
        self._by_transaction[tx.transaction_id] = row.binding_id
        return existing or row

    def current_reasons(self, binding_id: str) -> tuple[str, ...]:
        row = self.get(binding_id)
        reasons: list[str] = []
        tx = self.transactions.get(row.transaction_id)
        bound_claim_ids = tuple(snapshot.claim_id for snapshot in row.claim_snapshots)
        if tuple(sorted(tx.claim_refs)) != bound_claim_ids:
            reasons.append("claim_binding_scope_changed")

        for snapshot in row.claim_snapshots:
            try:
                claim = self.claims.get(snapshot.claim_id)
            except KeyError:
                reasons.append(f"claim_missing:{snapshot.claim_id}")
                continue
            if canonical_digest(claim.to_state()) != snapshot.digest:
                reasons.append(f"claim_state_changed:{snapshot.claim_id}")
            if claim.status is not ClaimStatus.ACTIVE:
                reasons.append(f"claim_not_active:{snapshot.claim_id}")
            if claim.mode is not ClaimMode.EXCLUSIVE_WRITE:
                reasons.append(f"claim_not_exclusive:{snapshot.claim_id}")
        return tuple(sorted(set(reasons)))

    def covers_patch(self, binding_id: str, patch: Any) -> bool:
        binding = self.get(binding_id)
        current_claims: list[CodeClaim] = []
        for snapshot in binding.claim_snapshots:
            try:
                current_claims.append(self.claims.get(snapshot.claim_id))
            except KeyError:
                return False
        return _scopes_cover_patch(current_claims, patch)

    def historically_covers_patch(self, binding_id: str, patch: Any) -> bool:
        return _scopes_cover_patch(self.get(binding_id).claim_snapshots, patch)

    def to_state(self) -> dict[str, Any]:
        return {"bindings": [row.to_state() for row in self.bindings()]}

    @classmethod
    def from_state(
        cls,
        *,
        transactions: PatchTransactionLedger,
        claims: CodeClaimLedger,
        state: Mapping[str, Any],
    ) -> "EngineeringClaimBindingLedger":
        ledger = cls(transactions=transactions, claims=claims)
        for value in state.get("bindings", ()):
            row = EngineeringClaimBinding.from_state(value)
            tx = transactions.get(row.transaction_id)
            bound_claim_ids = tuple(snapshot.claim_id for snapshot in row.claim_snapshots)
            if tuple(sorted(tx.claim_refs)) != bound_claim_ids:
                raise ValueError("claim binding snapshot transaction scope mismatch")
            existing = ledger._bindings.get(row.binding_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound engineering claim binding")
            prior = ledger._by_transaction.get(row.transaction_id)
            if prior is not None and prior != row.binding_id:
                raise ValueError("transaction has multiple historical claim bindings")
            ledger._bindings[row.binding_id] = row
            ledger._by_transaction[row.transaction_id] = row.binding_id
        return ledger


@dataclass(frozen=True, slots=True)
class EngineeringMutationAuthorityReceipt:
    receipt_id: str
    transaction_id: str
    patch_ref: str
    patch_digest: str
    claim_binding_id: str | None
    claim_binding_digest: str | None
    authorized: bool
    decision: EngineeringMutationAuthorityDecision
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        if self.authority != "mutation_scope_only":
            raise ValueError("mutation authority receipt cannot grant broader authority")
        if bool(self.claim_binding_id) != bool(self.claim_binding_digest):
            raise ValueError("mutation authority claim identity must be complete")
        if self.authorized:
            if self.decision is not EngineeringMutationAuthorityDecision.AUTHORIZED or self.reasons:
                raise ValueError("authorized mutation receipt must have no blocking reasons")
        elif self.decision is EngineeringMutationAuthorityDecision.AUTHORIZED:
            raise ValueError("blocked mutation receipt cannot claim authorization")

    def payload(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "claim_binding_id": self.claim_binding_id,
            "claim_binding_digest": self.claim_binding_digest,
            "authorized": self.authorized,
            "decision": self.decision.value,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringMutationAuthorityReceipt":
        row = cls(
            receipt_id=_text(state["receipt_id"], field="mutation authority receipt id"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            claim_binding_id=_optional_text(state.get("claim_binding_id")),
            claim_binding_digest=_optional_text(state.get("claim_binding_digest")),
            authorized=bool(state["authorized"]),
            decision=EngineeringMutationAuthorityDecision(str(state["decision"])),
            reasons=_refs(tuple(state.get("reasons", ()))),
            authority=_text(state["authority"], field="mutation authority"),
            digest=_text(state["digest"], field="mutation authority digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f"eng-mutation-authority-{expected[:20]}":
            raise ValueError("engineering mutation authority digest/id mismatch")
        return row


class EngineeringMutationAuthorityEngine:
    """Evaluates *current* right to apply one already-preconditioned transaction."""

    def __init__(
        self,
        *,
        transactions: PatchTransactionLedger,
        claim_bindings: EngineeringClaimBindingLedger,
    ) -> None:
        self.transactions = transactions
        self.claim_bindings = claim_bindings
        self._receipts: dict[str, EngineeringMutationAuthorityReceipt] = {}

    def receipts(self) -> tuple[EngineeringMutationAuthorityReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def get(self, receipt_id: str) -> EngineeringMutationAuthorityReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering mutation authority receipt: {receipt_id}") from exc

    def assess(self, transaction_id: str, *, patch: Any) -> EngineeringMutationAuthorityReceipt:
        tx = self.transactions.get(transaction_id)
        reasons: list[str] = []
        if tx.phase is not EngineeringPhase.PRECONDITIONS_VERIFIED:
            reasons.append("transaction_not_precondition_verified")
        if not hasattr(patch, "to_state"):
            patch_ref = str(getattr(patch, "patch_id", ""))
            patch_digest = "unavailable"
            reasons.append("missing_canonical_patch_state")
        else:
            patch_ref = str(getattr(patch, "patch_id", ""))
            patch_digest = canonical_digest(patch.to_state())
            if patch_ref != tx.patch_ref or patch_digest != tx.patch_digest:
                reasons.append("transaction_patch_lineage_mismatch")

        binding = self.claim_bindings.for_transaction(tx.transaction_id)
        binding_id: str | None = None
        binding_digest: str | None = None
        if binding is None:
            reasons.append("missing_claim_state_binding")
        else:
            binding_id = binding.binding_id
            binding_digest = binding.digest
            reasons.extend(self.claim_bindings.current_reasons(binding.binding_id))
            if not self.claim_bindings.covers_patch(binding.binding_id, patch):
                reasons.append("bound_claim_scope_does_not_cover_patch")

        normalized_reasons = tuple(sorted(set(reasons)))
        authorized = not normalized_reasons
        decision = (
            EngineeringMutationAuthorityDecision.AUTHORIZED
            if authorized
            else EngineeringMutationAuthorityDecision.BLOCKED
        )
        payload = {
            "transaction_id": tx.transaction_id,
            "patch_ref": tx.patch_ref,
            "patch_digest": tx.patch_digest,
            "claim_binding_id": binding_id,
            "claim_binding_digest": binding_digest,
            "authorized": authorized,
            "decision": decision.value,
            "reasons": list(normalized_reasons),
            "authority": "mutation_scope_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringMutationAuthorityReceipt(
            receipt_id=f"eng-mutation-authority-{digest[:20]}",
            transaction_id=tx.transaction_id,
            patch_ref=tx.patch_ref,
            patch_digest=tx.patch_digest,
            claim_binding_id=binding_id,
            claim_binding_digest=binding_digest,
            authorized=authorized,
            decision=decision,
            reasons=normalized_reasons,
            authority="mutation_scope_only",
            digest=digest,
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("engineering mutation authority receipt cannot be rebound")
        self._receipts[row.receipt_id] = row
        return existing or row

    def to_state(self) -> dict[str, Any]:
        return {"receipts": [row.to_state() for row in self.receipts()]}

    @classmethod
    def from_state(
        cls,
        *,
        transactions: PatchTransactionLedger,
        claim_bindings: EngineeringClaimBindingLedger,
        state: Mapping[str, Any],
    ) -> "EngineeringMutationAuthorityEngine":
        engine = cls(transactions=transactions, claim_bindings=claim_bindings)
        for value in state.get("receipts", ()):
            row = EngineeringMutationAuthorityReceipt.from_state(value)
            tx = transactions.get(row.transaction_id)
            if row.patch_ref != tx.patch_ref or row.patch_digest != tx.patch_digest:
                raise ValueError("mutation authority snapshot transaction lineage mismatch")
            if row.claim_binding_id is not None:
                binding = claim_bindings.get(row.claim_binding_id)
                if binding.digest != row.claim_binding_digest or binding.transaction_id != row.transaction_id:
                    raise ValueError("mutation authority snapshot claim lineage mismatch")
            existing = engine._receipts.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound mutation authority receipt")
            engine._receipts[row.receipt_id] = row
        return engine


@dataclass(frozen=True, slots=True)
class EngineeringCurrentValidityReceipt:
    receipt_id: str
    closure_receipt_id: str
    closure_digest: str
    transaction_id: str
    patch_ref: str
    patch_digest: str
    current_source_revision: str
    claim_binding_id: str | None
    current: bool
    decision: EngineeringValidityDecision
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.receipt_id, "validity receipt id"),
            (self.closure_receipt_id, "closure receipt id"),
            (self.closure_digest, "closure digest"),
            (self.transaction_id, "transaction id"),
            (self.patch_ref, "patch ref"),
            (self.patch_digest, "patch digest"),
            (self.current_source_revision, "current source revision"),
            (self.digest, "validity digest"),
        ):
            _text(value, field=field)
        if self.authority != "candidate_only":
            raise ValueError("current validity cannot hold promotion authority")
        if self.current:
            if self.decision is not EngineeringValidityDecision.CURRENT_VALID or self.reasons:
                raise ValueError("current-valid receipt must have no invalidation reasons")
        elif self.decision is EngineeringValidityDecision.CURRENT_VALID:
            raise ValueError("non-current receipt cannot claim current-valid")

    def payload(self) -> dict[str, Any]:
        return {
            "closure_receipt_id": self.closure_receipt_id,
            "closure_digest": self.closure_digest,
            "transaction_id": self.transaction_id,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "current_source_revision": self.current_source_revision,
            "claim_binding_id": self.claim_binding_id,
            "current": self.current,
            "decision": self.decision.value,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringCurrentValidityReceipt":
        row = cls(
            receipt_id=_text(state["receipt_id"], field="validity receipt id"),
            closure_receipt_id=_text(state["closure_receipt_id"], field="closure receipt id"),
            closure_digest=_text(state["closure_digest"], field="closure digest"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            current_source_revision=_text(state["current_source_revision"], field="current source revision"),
            claim_binding_id=_optional_text(state.get("claim_binding_id")),
            current=bool(state["current"]),
            decision=EngineeringValidityDecision(str(state["decision"])),
            reasons=_refs(tuple(state.get("reasons", ()))),
            authority=_text(state["authority"], field="validity authority"),
            digest=_text(state["digest"], field="validity digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f"eng-validity-{expected[:20]}":
            raise ValueError("engineering current validity digest/id mismatch")
        return row


class EngineeringValidityEngine:
    """Revalidates candidate truth without conflating it with a transient lease."""

    def __init__(
        self,
        *,
        evidence: EngineeringEvidenceLedger,
        transactions: PatchTransactionLedger,
        closure: SoftwareEngineeringClosureEngine,
        claims: CodeClaimLedger,
        claim_bindings: EngineeringClaimBindingLedger,
    ) -> None:
        self.evidence = evidence
        self.transactions = transactions
        self.closure = closure
        self.claims = claims
        self.claim_bindings = claim_bindings
        self._receipts: dict[str, EngineeringCurrentValidityReceipt] = {}

    def receipts(self) -> tuple[EngineeringCurrentValidityReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def get(self, receipt_id: str) -> EngineeringCurrentValidityReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering current validity receipt: {receipt_id}") from exc

    def revalidate(
        self,
        closure_receipt_id: str,
        *,
        patch: Any,
        current_source_revision: str,
    ) -> EngineeringCurrentValidityReceipt:
        historical = self.closure.get(closure_receipt_id)
        tx = self.transactions.get(historical.transaction_id)
        source_revision = _text(current_source_revision, field="current source revision")
        reasons: list[str] = []

        if not historical.ready:
            reasons.append("historical_closure_not_ready")
        if (
            tx.patch_ref != historical.patch_ref
            or tx.patch_digest != historical.patch_digest
            or tx.source_revision != historical.source_revision
        ):
            reasons.append("transaction_lineage_changed")
        if historical.ready and (
            tx.phase is not EngineeringPhase.CANDIDATE_READY
            or tx.closure_receipt_id != historical.receipt_id
        ):
            reasons.append("candidate_transaction_state_changed")
        if source_revision != historical.source_revision or source_revision != tx.source_revision:
            reasons.append("stale_source_revision")

        if not hasattr(patch, "to_state"):
            reasons.append("missing_current_patch_state")
        else:
            current_patch_digest = canonical_digest(patch.to_state())
            current_patch_ref = str(getattr(patch, "patch_id", ""))
            if current_patch_ref != historical.patch_ref:
                reasons.append("patch_identity_changed")
            elif current_patch_digest != historical.patch_digest:
                reasons.append("patch_state_changed")

        if any(
            not self.evidence.is_valid(
                attestation_id,
                subject_ref=historical.patch_ref,
                subject_digest=historical.patch_digest,
                source_revision=historical.source_revision,
            )
            for attestation_id in historical.attestation_ids
        ):
            reasons.append("revoked_or_invalid_evidence")

        binding = self.claim_bindings.for_transaction(tx.transaction_id)
        binding_id: str | None = None
        if binding is None:
            reasons.append("missing_claim_state_binding")
        else:
            binding_id = binding.binding_id
            if not self.claim_bindings.historically_covers_patch(binding.binding_id, patch):
                reasons.append("historical_claim_binding_does_not_cover_patch")

        normalized_reasons = tuple(sorted(set(reasons)))
        current = historical.ready and not normalized_reasons
        if current:
            decision = EngineeringValidityDecision.CURRENT_VALID
        elif historical.ready:
            decision = EngineeringValidityDecision.STALE
        else:
            decision = EngineeringValidityDecision.BLOCKED

        payload = {
            "closure_receipt_id": historical.receipt_id,
            "closure_digest": historical.digest,
            "transaction_id": historical.transaction_id,
            "patch_ref": historical.patch_ref,
            "patch_digest": historical.patch_digest,
            "current_source_revision": source_revision,
            "claim_binding_id": binding_id,
            "current": current,
            "decision": decision.value,
            "reasons": list(normalized_reasons),
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringCurrentValidityReceipt(
            receipt_id=f"eng-validity-{digest[:20]}",
            closure_receipt_id=historical.receipt_id,
            closure_digest=historical.digest,
            transaction_id=historical.transaction_id,
            patch_ref=historical.patch_ref,
            patch_digest=historical.patch_digest,
            current_source_revision=source_revision,
            claim_binding_id=binding_id,
            current=current,
            decision=decision,
            reasons=normalized_reasons,
            authority="candidate_only",
            digest=digest,
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("engineering validity receipt cannot be rebound")
        self._receipts[row.receipt_id] = row
        return existing or row

    def is_current(
        self,
        closure_receipt_id: str,
        *,
        patch: Any,
        current_source_revision: str,
    ) -> bool:
        return self.revalidate(
            closure_receipt_id,
            patch=patch,
            current_source_revision=current_source_revision,
        ).current

    def to_state(self) -> dict[str, Any]:
        return {"receipts": [row.to_state() for row in self.receipts()]}

    @classmethod
    def from_state(
        cls,
        *,
        evidence: EngineeringEvidenceLedger,
        transactions: PatchTransactionLedger,
        closure: SoftwareEngineeringClosureEngine,
        claims: CodeClaimLedger,
        claim_bindings: EngineeringClaimBindingLedger,
        state: Mapping[str, Any],
    ) -> "EngineeringValidityEngine":
        engine = cls(
            evidence=evidence,
            transactions=transactions,
            closure=closure,
            claims=claims,
            claim_bindings=claim_bindings,
        )
        for value in state.get("receipts", ()):
            row = EngineeringCurrentValidityReceipt.from_state(value)
            historical = closure.get(row.closure_receipt_id)
            if (
                row.closure_digest != historical.digest
                or row.transaction_id != historical.transaction_id
                or row.patch_ref != historical.patch_ref
                or row.patch_digest != historical.patch_digest
            ):
                raise ValueError("engineering validity snapshot closure lineage mismatch")
            if row.claim_binding_id is not None:
                binding = claim_bindings.get(row.claim_binding_id)
                if binding.transaction_id != row.transaction_id:
                    raise ValueError("engineering validity snapshot claim lineage mismatch")
            existing = engine._receipts.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound engineering validity receipt")
            engine._receipts[row.receipt_id] = row
        return engine


__all__ = (
    "EngineeringValidityDecision",
    "EngineeringMutationAuthorityDecision",
    "EngineeringBoundClaimSnapshot",
    "EngineeringClaimBinding",
    "EngineeringClaimBindingLedger",
    "EngineeringMutationAuthorityReceipt",
    "EngineeringMutationAuthorityEngine",
    "EngineeringCurrentValidityReceipt",
    "EngineeringValidityEngine",
)
