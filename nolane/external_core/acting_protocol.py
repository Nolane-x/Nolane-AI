from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum, IntEnum
from typing import Any, Iterable, Mapping

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.acting.protocol"
COMPONENT_VERSION = "0.1.3"
PROTOCOL_SCHEMA_VERSION = 1


class ProtocolViolation(RuntimeError):
    """Raised when an execution transition would violate the acting contract."""


class LeaseExpired(ProtocolViolation):
    """Raised when forward execution is attempted without a live execution lease."""


class IdempotencyConflict(ProtocolViolation):
    """Raised when an idempotency key is reused for a semantically different action."""


class ExecutionRisk(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class EffectClass(str, Enum):
    READ = "read"
    LOCAL_MUTATION = "local_mutation"
    EXTERNAL_MUTATION = "external_mutation"
    IRREVERSIBLE = "irreversible"


class ActionPhase(str, Enum):
    PROPOSED = "proposed"
    LEASED = "leased"
    PRECONDITION_VERIFIED = "precondition_verified"
    EXECUTING = "executing"
    OUTCOME_OBSERVED = "outcome_observed"
    POSTCONDITION_VERIFIED = "postcondition_verified"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    DEGRADED = "degraded"
    CANCELLED = "cancelled"


class VerifierLevel(IntEnum):
    V0 = 0
    V1 = 1
    V2 = 2
    V3 = 3
    V4 = 4

    @classmethod
    def coerce(cls, value: "VerifierLevel | int | str") -> "VerifierLevel":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            token = value.strip().upper()
            if token.startswith("V"):
                return cls(int(token[1:]))
        return cls(int(value))


@dataclass(frozen=True, slots=True)
class ActionBudget:
    """Per-action side-effect budget. Zero is meaningful for effect counters."""

    max_attempts: int = 1
    max_local_mutations: int = 0
    max_external_effects: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or int(self.max_attempts) <= 0:
            raise ValueError("max_attempts must be a positive integer")
        for name, value in (
            ("max_local_mutations", self.max_local_mutations),
            ("max_external_effects", self.max_external_effects),
        ):
            if isinstance(value, bool) or int(value) < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    def to_state(self) -> dict[str, int]:
        return {
            "max_attempts": int(self.max_attempts),
            "max_local_mutations": int(self.max_local_mutations),
            "max_external_effects": int(self.max_external_effects),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ActionBudget":
        return cls(
            max_attempts=int(state.get("max_attempts", 1)),
            max_local_mutations=int(state.get("max_local_mutations", 0)),
            max_external_effects=int(state.get("max_external_effects", 0)),
        )


@dataclass(frozen=True, slots=True)
class ExecutionContract:
    """Authorized intent consumed by E. Acting; it does not select the action itself."""

    action_id: str
    core_id: str
    operation: str
    input_digest: str
    risk_class: ExecutionRisk
    effect_class: EffectClass
    required_capabilities: tuple[str, ...]
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]
    idempotency_key: str
    recovery_plan: str = ""
    budget: ActionBudget = field(default_factory=ActionBudget)

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_class", ExecutionRisk(self.risk_class))
        object.__setattr__(self, "effect_class", EffectClass(self.effect_class))
        if isinstance(self.budget, Mapping):
            object.__setattr__(self, "budget", ActionBudget.from_state(self.budget))
        object.__setattr__(self, "required_capabilities", tuple(str(x) for x in self.required_capabilities))
        object.__setattr__(self, "preconditions", tuple(str(x) for x in self.preconditions))
        object.__setattr__(self, "postconditions", tuple(str(x) for x in self.postconditions))

        required = (
            (self.action_id, "action id"),
            (self.core_id, "core id"),
            (self.operation, "operation"),
            (self.input_digest, "input digest"),
            (self.idempotency_key, "idempotency key"),
        )
        for value, label in required:
            if not str(value).strip():
                raise ValueError(f"{label} must be explicit")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("required capabilities must be unique")
        if any(not x.strip() for x in self.required_capabilities + self.preconditions + self.postconditions):
            raise ValueError("capabilities and conditions cannot contain empty values")
        if self.risk_class is ExecutionRisk.R4 and not self.recovery_plan.strip():
            raise ValueError("R4 action requires an explicit recovery plan")
        if self.effect_class is EffectClass.IRREVERSIBLE and not self.recovery_plan.strip():
            raise ValueError("irreversible action requires an explicit recovery plan")

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "core_id": self.core_id,
            "operation": self.operation,
            "input_digest": self.input_digest,
            "risk_class": self.risk_class.value,
            "effect_class": self.effect_class.value,
            "required_capabilities": list(self.required_capabilities),
            "preconditions": list(self.preconditions),
            "postconditions": list(self.postconditions),
            "recovery_plan": self.recovery_plan,
            "budget": self.budget.to_state(),
        }

    @property
    def semantic_digest(self) -> str:
        return canonical_digest(self.semantic_payload())

    def to_state(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            **self.semantic_payload(),
            "idempotency_key": self.idempotency_key,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExecutionContract":
        return cls(
            action_id=str(state["action_id"]),
            core_id=str(state["core_id"]),
            operation=str(state["operation"]),
            input_digest=str(state["input_digest"]),
            risk_class=ExecutionRisk(str(state["risk_class"])),
            effect_class=EffectClass(str(state["effect_class"])),
            required_capabilities=tuple(str(x) for x in state.get("required_capabilities", ())),
            preconditions=tuple(str(x) for x in state.get("preconditions", ())),
            postconditions=tuple(str(x) for x in state.get("postconditions", ())),
            idempotency_key=str(state["idempotency_key"]),
            recovery_plan=str(state.get("recovery_plan", "")),
            budget=ActionBudget.from_state(state.get("budget", {})),
        )


@dataclass(frozen=True, slots=True)
class ExecutionLease:
    lease_id: str
    action_id: str
    owner_id: str
    generation: int
    issued_at_ms: int
    expires_at_ms: int
    revoked: bool = False

    def __post_init__(self) -> None:
        if not self.lease_id.strip() or not self.action_id.strip() or not self.owner_id.strip():
            raise ValueError("execution lease identity must be explicit")
        if self.generation <= 0:
            raise ValueError("lease generation must be positive")
        if self.expires_at_ms <= self.issued_at_ms:
            raise ValueError("execution lease expiry must be after issuance")

    def valid_at(self, now_ms: int) -> bool:
        return not self.revoked and int(self.issued_at_ms) <= int(now_ms) < int(self.expires_at_ms)

    def to_state(self) -> dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "action_id": self.action_id,
            "owner_id": self.owner_id,
            "generation": self.generation,
            "issued_at_ms": self.issued_at_ms,
            "expires_at_ms": self.expires_at_ms,
            "revoked": self.revoked,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExecutionLease":
        return cls(
            lease_id=str(state["lease_id"]),
            action_id=str(state["action_id"]),
            owner_id=str(state["owner_id"]),
            generation=int(state["generation"]),
            issued_at_ms=int(state["issued_at_ms"]),
            expires_at_ms=int(state["expires_at_ms"]),
            revoked=bool(state.get("revoked", False)),
        )


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    receipt_id: str
    action_id: str
    sequence: int
    phase: ActionPhase
    event_type: str
    evidence_refs: tuple[str, ...]
    previous_digest: str
    payload_digest: str
    digest: str

    @classmethod
    def create(
        cls,
        *,
        action_id: str,
        sequence: int,
        phase: ActionPhase,
        event_type: str,
        evidence_refs: Iterable[str] = (),
        previous_digest: str = "",
        payload: Mapping[str, Any] | None = None,
    ) -> "ExecutionEvent":
        refs = tuple(dict.fromkeys(str(x).strip() for x in evidence_refs if str(x).strip()))
        payload_digest = canonical_digest(dict(payload or {}))
        body = {
            "action_id": str(action_id),
            "sequence": int(sequence),
            "phase": ActionPhase(phase).value,
            "event_type": str(event_type),
            "evidence_refs": list(refs),
            "previous_digest": str(previous_digest),
            "payload_digest": payload_digest,
        }
        digest = canonical_digest(body)
        return cls(
            receipt_id="acting-event-" + digest[:24],
            action_id=str(action_id),
            sequence=int(sequence),
            phase=ActionPhase(phase),
            event_type=str(event_type),
            evidence_refs=refs,
            previous_digest=str(previous_digest),
            payload_digest=payload_digest,
            digest=digest,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "sequence": self.sequence,
            "phase": self.phase.value,
            "event_type": self.event_type,
            "evidence_refs": list(self.evidence_refs),
            "previous_digest": self.previous_digest,
            "payload_digest": self.payload_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExecutionEvent":
        row = cls(
            receipt_id=str(state["receipt_id"]),
            action_id=str(state["action_id"]),
            sequence=int(state["sequence"]),
            phase=ActionPhase(str(state["phase"])),
            event_type=str(state["event_type"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            previous_digest=str(state.get("previous_digest", "")),
            payload_digest=str(state["payload_digest"]),
            digest=str(state["digest"]),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != "acting-event-" + expected[:24]:
            raise ValueError("execution event digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class ActionRecord:
    contract: ExecutionContract
    phase: ActionPhase = ActionPhase.PROPOSED
    lease: ExecutionLease | None = None
    authorization_ref: str = ""
    precondition_evidence_refs: tuple[str, ...] = ()
    outcome_ref: str = ""
    outcome_success: bool | None = None
    postcondition_evidence_refs: tuple[str, ...] = ()
    verifier_level: VerifierLevel = VerifierLevel.V0
    attempts: int = 0
    local_mutations: int = 0
    external_effects: int = 0
    commit_ref: str = ""
    rollback_ref: str = ""
    failure_reason: str = ""
    event_receipt_ids: tuple[str, ...] = ()

    @property
    def action_id(self) -> str:
        return self.contract.action_id

    def _state_payload(self) -> dict[str, Any]:
        return {
            "contract": self.contract.to_state(),
            "phase": self.phase.value,
            "lease": None if self.lease is None else self.lease.to_state(),
            "authorization_ref": self.authorization_ref,
            "precondition_evidence_refs": list(self.precondition_evidence_refs),
            "outcome_ref": self.outcome_ref,
            "outcome_success": self.outcome_success,
            "postcondition_evidence_refs": list(self.postcondition_evidence_refs),
            "verifier_level": int(self.verifier_level),
            "attempts": self.attempts,
            "local_mutations": self.local_mutations,
            "external_effects": self.external_effects,
            "commit_ref": self.commit_ref,
            "rollback_ref": self.rollback_ref,
            "failure_reason": self.failure_reason,
            "event_receipt_ids": list(self.event_receipt_ids),
        }

    @property
    def digest(self) -> str:
        return canonical_digest(self._state_payload())

    def to_state(self) -> dict[str, Any]:
        return {**self._state_payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ActionRecord":
        lease = state.get("lease")
        row = cls(
            contract=ExecutionContract.from_state(state["contract"]),
            phase=ActionPhase(str(state.get("phase", ActionPhase.PROPOSED.value))),
            lease=None if lease is None else ExecutionLease.from_state(lease),
            authorization_ref=str(state.get("authorization_ref", "")),
            precondition_evidence_refs=tuple(str(x) for x in state.get("precondition_evidence_refs", ())),
            outcome_ref=str(state.get("outcome_ref", "")),
            outcome_success=state.get("outcome_success"),
            postcondition_evidence_refs=tuple(str(x) for x in state.get("postcondition_evidence_refs", ())),
            verifier_level=VerifierLevel(int(state.get("verifier_level", 0))),
            attempts=int(state.get("attempts", 0)),
            local_mutations=int(state.get("local_mutations", 0)),
            external_effects=int(state.get("external_effects", 0)),
            commit_ref=str(state.get("commit_ref", "")),
            rollback_ref=str(state.get("rollback_ref", "")),
            failure_reason=str(state.get("failure_reason", "")),
            event_receipt_ids=tuple(str(x) for x in state.get("event_receipt_ids", ())),
        )
        supplied_digest = state.get("digest")
        if supplied_digest is not None and str(supplied_digest) != row.digest:
            raise ValueError("action record digest mismatch")
        return row


_TERMINAL_PHASES = {
    ActionPhase.COMMITTED,
    ActionPhase.ROLLED_BACK,
    ActionPhase.DEGRADED,
    ActionPhase.CANCELLED,
}


class ActingProtocolLedger:
    """Append-only, lease-aware action lifecycle for the E. Acting boundary.

    The ledger consumes an externally authorized ExecutionContract. It deliberately
    does not perform candidate selection, planning, or policy optimization.
    """

    def __init__(
        self,
        *,
        records: Iterable[ActionRecord] = (),
        events: Iterable[ExecutionEvent] = (),
    ) -> None:
        self._records: dict[str, ActionRecord] = {}
        self._events: dict[str, ExecutionEvent] = {}
        self._idempotency: dict[str, str] = {}
        for event in events:
            if event.receipt_id in self._events and self._events[event.receipt_id] != event:
                raise ValueError("duplicate execution event receipt")
            self._events[event.receipt_id] = event
        for row in records:
            if row.action_id in self._records and self._records[row.action_id] != row:
                raise ValueError("duplicate action record")
            key = row.contract.idempotency_key
            existing = self._idempotency.get(key)
            if existing is not None and existing != row.action_id:
                raise ValueError("duplicate idempotency key in protocol state")
            self._records[row.action_id] = row
            self._idempotency[key] = row.action_id
        self._validate_state()

    def records(self) -> tuple[ActionRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def get(self, action_id: str) -> ActionRecord:
        try:
            return self._records[str(action_id)]
        except KeyError as exc:
            raise KeyError(f"unknown acting action: {action_id}") from exc

    def events(self, action_id: str) -> tuple[ExecutionEvent, ...]:
        row = self.get(action_id)
        return tuple(self._events[receipt_id] for receipt_id in row.event_receipt_ids)

    def _append_event(
        self,
        row: ActionRecord,
        *,
        phase: ActionPhase,
        event_type: str,
        evidence_refs: Iterable[str] = (),
        payload: Mapping[str, Any] | None = None,
        **updates: Any,
    ) -> ActionRecord:
        history = self.events(row.action_id) if row.event_receipt_ids else ()
        previous = history[-1].digest if history else ""
        event = ExecutionEvent.create(
            action_id=row.action_id,
            sequence=len(history),
            phase=phase,
            event_type=event_type,
            evidence_refs=evidence_refs,
            previous_digest=previous,
            payload=payload,
        )
        self._events[event.receipt_id] = event
        updated = replace(
            row,
            phase=phase,
            event_receipt_ids=row.event_receipt_ids + (event.receipt_id,),
            **updates,
        )
        self._records[row.action_id] = updated
        return updated

    @staticmethod
    def _expect(row: ActionRecord, *phases: ActionPhase) -> None:
        if row.phase not in phases:
            expected = ", ".join(x.value for x in phases)
            raise ProtocolViolation(f"action must be in [{expected}] before transition; current={row.phase.value}")

    @staticmethod
    def _require_lease(row: ActionRecord, now_ms: int) -> ExecutionLease:
        if row.lease is None:
            raise LeaseExpired("forward execution requires an execution lease")
        if not row.lease.valid_at(now_ms):
            raise LeaseExpired("execution lease is expired or revoked")
        return row.lease

    def propose(self, contract: ExecutionContract) -> ActionRecord:
        existing_action_id = self._idempotency.get(contract.idempotency_key)
        if existing_action_id is not None:
            existing = self.get(existing_action_id)
            if existing.contract.semantic_digest != contract.semantic_digest:
                raise IdempotencyConflict("idempotency key reused for semantically different action")
            return existing
        if contract.action_id in self._records:
            existing = self._records[contract.action_id]
            if existing.contract != contract:
                raise ProtocolViolation("action id already exists with a different contract")
            return existing
        row = ActionRecord(contract=contract)
        self._records[row.action_id] = row
        self._idempotency[contract.idempotency_key] = row.action_id
        return self._append_event(
            row,
            phase=ActionPhase.PROPOSED,
            event_type="proposed",
            payload={"contract_digest": canonical_digest(contract.to_state()), "semantic_digest": contract.semantic_digest},
        )

    def acquire_lease(
        self,
        action_id: str,
        *,
        owner_id: str,
        authorization_ref: str,
        capability_grants: Iterable[str],
        now_ms: int,
        ttl_ms: int,
    ) -> ActionRecord:
        row = self.get(action_id)
        self._expect(row, ActionPhase.PROPOSED)
        owner = str(owner_id).strip()
        auth = str(authorization_ref).strip()
        if not owner or not auth:
            raise ValueError("lease owner and upstream authorization reference are required")
        if isinstance(ttl_ms, bool) or int(ttl_ms) <= 0:
            raise ValueError("lease ttl must be positive")
        grants = frozenset(str(x).strip() for x in capability_grants if str(x).strip())
        missing = sorted(set(row.contract.required_capabilities) - grants)
        if missing:
            raise PermissionError("required capabilities not granted: " + ", ".join(missing))
        issued = int(now_ms)
        expires = issued + int(ttl_ms)
        generation = 1 if row.lease is None else row.lease.generation + 1
        lease_digest = canonical_digest(
            {
                "action_id": row.action_id,
                "owner_id": owner,
                "generation": generation,
                "issued_at_ms": issued,
                "expires_at_ms": expires,
                "authorization_ref": auth,
            }
        )
        lease = ExecutionLease(
            lease_id="execution-lease-" + lease_digest[:24],
            action_id=row.action_id,
            owner_id=owner,
            generation=generation,
            issued_at_ms=issued,
            expires_at_ms=expires,
        )
        return self._append_event(
            row,
            phase=ActionPhase.LEASED,
            event_type="lease_acquired",
            evidence_refs=(auth, "lease:" + lease.lease_id),
            payload={"lease": lease.to_state(), "capability_grants": sorted(grants)},
            lease=lease,
            authorization_ref=auth,
        )

    def renew_lease(
        self,
        action_id: str,
        *,
        owner_id: str,
        capability_grants: Iterable[str],
        now_ms: int,
        ttl_ms: int,
        evidence_ref: str,
    ) -> ActionRecord:
        row = self.get(action_id)
        if row.phase in _TERMINAL_PHASES:
            raise ProtocolViolation("terminal action lease cannot be renewed")
        current = self._require_lease(row, now_ms)
        if current.owner_id != str(owner_id):
            raise PermissionError("lease renewal owner mismatch")
        grants = frozenset(str(x).strip() for x in capability_grants if str(x).strip())
        missing = sorted(set(row.contract.required_capabilities) - grants)
        if missing:
            raise PermissionError("required capabilities not granted: " + ", ".join(missing))
        if int(ttl_ms) <= 0:
            raise ValueError("lease ttl must be positive")
        ref = str(evidence_ref).strip()
        if not ref:
            raise ValueError("lease renewal evidence is required")
        issued = int(now_ms)
        expires = issued + int(ttl_ms)
        generation = current.generation + 1
        digest = canonical_digest(
            {
                "action_id": row.action_id,
                "owner_id": current.owner_id,
                "generation": generation,
                "issued_at_ms": issued,
                "expires_at_ms": expires,
                "previous_lease_id": current.lease_id,
            }
        )
        lease = ExecutionLease(
            lease_id="execution-lease-" + digest[:24],
            action_id=row.action_id,
            owner_id=current.owner_id,
            generation=generation,
            issued_at_ms=issued,
            expires_at_ms=expires,
        )
        return self._append_event(
            row,
            phase=row.phase,
            event_type="lease_renewed",
            evidence_refs=(ref, "lease:" + lease.lease_id, "previous-lease:" + current.lease_id),
            payload={"lease": lease.to_state(), "previous_lease_id": current.lease_id},
            lease=lease,
        )

    def revoke_lease(self, action_id: str, *, reason: str, evidence_ref: str) -> ActionRecord:
        row = self.get(action_id)
        if row.lease is None:
            raise ProtocolViolation("cannot revoke a missing lease")
        if row.phase in _TERMINAL_PHASES:
            return row
        reason_text = str(reason).strip()
        ref = str(evidence_ref).strip()
        if not reason_text or not ref:
            raise ValueError("lease revocation reason and evidence are required")
        lease = replace(row.lease, revoked=True)
        return self._append_event(
            row,
            phase=row.phase,
            event_type="lease_revoked",
            evidence_refs=(ref, "lease:" + lease.lease_id),
            payload={"reason": reason_text, "lease_id": lease.lease_id},
            lease=lease,
        )

    def verify_preconditions(self, action_id: str, *, evidence_refs: Iterable[str], now_ms: int) -> ActionRecord:
        row = self.get(action_id)
        self._expect(row, ActionPhase.LEASED)
        self._require_lease(row, now_ms)
        refs = tuple(dict.fromkeys(str(x).strip() for x in evidence_refs if str(x).strip()))
        if row.contract.preconditions and not refs:
            raise ProtocolViolation("precondition evidence is required")
        return self._append_event(
            row,
            phase=ActionPhase.PRECONDITION_VERIFIED,
            event_type="preconditions_verified",
            evidence_refs=refs,
            payload={"declared_preconditions": list(row.contract.preconditions)},
            precondition_evidence_refs=refs,
        )

    def begin_execution(self, action_id: str, *, now_ms: int) -> ActionRecord:
        row = self.get(action_id)
        self._expect(row, ActionPhase.PRECONDITION_VERIFIED)
        self._require_lease(row, now_ms)
        attempts = row.attempts + 1
        local_mutations = row.local_mutations + (1 if row.contract.effect_class is EffectClass.LOCAL_MUTATION else 0)
        external_effects = row.external_effects + (
            1 if row.contract.effect_class in {EffectClass.EXTERNAL_MUTATION, EffectClass.IRREVERSIBLE} else 0
        )
        if attempts > row.contract.budget.max_attempts:
            raise ProtocolViolation("action attempt budget exhausted")
        if local_mutations > row.contract.budget.max_local_mutations:
            raise ProtocolViolation("local mutation budget exhausted")
        if external_effects > row.contract.budget.max_external_effects:
            raise ProtocolViolation("external effect budget exhausted")
        return self._append_event(
            row,
            phase=ActionPhase.EXECUTING,
            event_type="execution_started",
            payload={
                "attempt": attempts,
                "local_mutations": local_mutations,
                "external_effects": external_effects,
                "effect_class": row.contract.effect_class.value,
            },
            attempts=attempts,
            local_mutations=local_mutations,
            external_effects=external_effects,
        )

    def observe_outcome(
        self,
        action_id: str,
        *,
        outcome_ref: str,
        success: bool,
        now_ms: int,
    ) -> ActionRecord:
        del now_ms  # observation/recovery must remain possible after lease expiry
        row = self.get(action_id)
        self._expect(row, ActionPhase.EXECUTING)
        ref = str(outcome_ref).strip()
        if not ref:
            raise ValueError("outcome reference is required")
        return self._append_event(
            row,
            phase=ActionPhase.OUTCOME_OBSERVED,
            event_type="outcome_observed",
            evidence_refs=(ref,),
            payload={"success": bool(success)},
            outcome_ref=ref,
            outcome_success=bool(success),
        )

    @staticmethod
    def minimum_verifier_level(risk: ExecutionRisk) -> VerifierLevel:
        return {
            ExecutionRisk.R0: VerifierLevel.V1,
            ExecutionRisk.R1: VerifierLevel.V1,
            ExecutionRisk.R2: VerifierLevel.V2,
            ExecutionRisk.R3: VerifierLevel.V3,
            ExecutionRisk.R4: VerifierLevel.V4,
        }[ExecutionRisk(risk)]

    def verify_postconditions(
        self,
        action_id: str,
        *,
        evidence_refs: Iterable[str],
        verifier_level: VerifierLevel | int | str,
        now_ms: int,
    ) -> ActionRecord:
        row = self.get(action_id)
        self._expect(row, ActionPhase.OUTCOME_OBSERVED)
        self._require_lease(row, now_ms)
        if row.outcome_success is not True:
            raise ProtocolViolation("failed execution cannot pass postcondition verification")
        refs = tuple(dict.fromkeys(str(x).strip() for x in evidence_refs if str(x).strip()))
        if row.contract.postconditions and not refs:
            raise ProtocolViolation("postcondition evidence is required")
        level = VerifierLevel.coerce(verifier_level)
        minimum = self.minimum_verifier_level(row.contract.risk_class)
        if level < minimum:
            raise PermissionError(
                f"{row.contract.risk_class.value} postcondition verification requires {minimum.name}"
            )
        return self._append_event(
            row,
            phase=ActionPhase.POSTCONDITION_VERIFIED,
            event_type="postconditions_verified",
            evidence_refs=refs,
            payload={"verifier_level": int(level), "declared_postconditions": list(row.contract.postconditions)},
            postcondition_evidence_refs=refs,
            verifier_level=level,
        )

    def commit(self, action_id: str, *, commit_ref: str, now_ms: int) -> ActionRecord:
        row = self.get(action_id)
        if row.phase is not ActionPhase.POSTCONDITION_VERIFIED:
            raise ProtocolViolation("postcondition verification is required before commit")
        self._require_lease(row, now_ms)
        ref = str(commit_ref).strip()
        if not ref:
            raise ValueError("commit reference is required")
        return self._append_event(
            row,
            phase=ActionPhase.COMMITTED,
            event_type="committed",
            evidence_refs=(ref,),
            payload={"outcome_ref": row.outcome_ref},
            commit_ref=ref,
        )

    def rollback(
        self,
        action_id: str,
        *,
        rollback_ref: str,
        failure_reason: str,
    ) -> ActionRecord:
        row = self.get(action_id)
        self._expect(row, ActionPhase.EXECUTING, ActionPhase.OUTCOME_OBSERVED, ActionPhase.POSTCONDITION_VERIFIED)
        ref = str(rollback_ref).strip()
        reason = str(failure_reason).strip()
        if not ref or not reason:
            raise ValueError("rollback reference and failure reason are required")
        return self._append_event(
            row,
            phase=ActionPhase.ROLLED_BACK,
            event_type="rolled_back",
            evidence_refs=(ref,),
            payload={"failure_reason": reason},
            rollback_ref=ref,
            failure_reason=reason,
        )

    def degrade(
        self,
        action_id: str,
        *,
        recovery_ref: str,
        failure_reason: str,
    ) -> ActionRecord:
        row = self.get(action_id)
        self._expect(
            row,
            ActionPhase.LEASED,
            ActionPhase.PRECONDITION_VERIFIED,
            ActionPhase.EXECUTING,
            ActionPhase.OUTCOME_OBSERVED,
            ActionPhase.POSTCONDITION_VERIFIED,
        )
        ref = str(recovery_ref).strip()
        reason = str(failure_reason).strip()
        if not ref or not reason:
            raise ValueError("degraded recovery requires evidence and a failure reason")
        return self._append_event(
            row,
            phase=ActionPhase.DEGRADED,
            event_type="degraded",
            evidence_refs=(ref,),
            payload={"failure_reason": reason, "recovery_plan": row.contract.recovery_plan},
            rollback_ref=ref,
            failure_reason=reason,
        )

    def cancel(self, action_id: str, *, reason: str, evidence_ref: str) -> ActionRecord:
        row = self.get(action_id)
        self._expect(row, ActionPhase.PROPOSED, ActionPhase.LEASED, ActionPhase.PRECONDITION_VERIFIED)
        reason_text = str(reason).strip()
        ref = str(evidence_ref).strip()
        if not reason_text or not ref:
            raise ValueError("cancellation reason and evidence are required")
        return self._append_event(
            row,
            phase=ActionPhase.CANCELLED,
            event_type="cancelled",
            evidence_refs=(ref,),
            payload={"reason": reason_text},
            failure_reason=reason_text,
        )

    def reconcile_interrupted(
        self,
        action_id: str,
        *,
        evidence_ref: str,
        reason: str,
    ) -> ActionRecord:
        """Resolve a persisted non-terminal action after runtime interruption.

        Reconciliation is intentionally fail-closed. Before execution dispatch the
        action is cancelled. Once dispatch may have happened, reads can be discarded
        as no-side-effect work while every mutating effect is degraded because a
        process restart cannot prove whether the side effect completed or whether an
        ephemeral local checkpoint is still available. No lease is required because
        this is recovery, not forward execution.
        """

        row = self.get(action_id)
        if row.phase in _TERMINAL_PHASES:
            return row
        ref = str(evidence_ref).strip()
        why = str(reason).strip()
        if not ref or not why:
            raise ValueError("interrupted reconciliation requires evidence and a reason")
        if row.phase in {
            ActionPhase.PROPOSED,
            ActionPhase.LEASED,
            ActionPhase.PRECONDITION_VERIFIED,
        }:
            return self.cancel(action_id, reason=why, evidence_ref=ref)
        if row.contract.effect_class is EffectClass.READ:
            return self.rollback(
                action_id,
                rollback_ref="no-side-effect:" + ref,
                failure_reason=why,
            )
        return self.degrade(
            action_id,
            recovery_ref=ref,
            failure_reason=why,
        )

    def validate_chain(self, action_id: str) -> bool:
        row = self.get(action_id)
        previous = ""
        for expected_sequence, receipt_id in enumerate(row.event_receipt_ids):
            try:
                event = self._events[receipt_id]
            except KeyError as exc:
                raise ValueError("action references missing execution event") from exc
            if event.action_id != row.action_id:
                raise ValueError("execution event belongs to a different action")
            if event.sequence != expected_sequence:
                raise ValueError("execution event sequence is non-canonical")
            if event.previous_digest != previous:
                raise ValueError("execution event chain is broken")
            expected_digest = canonical_digest(event.payload())
            if event.digest != expected_digest or event.receipt_id != "acting-event-" + expected_digest[:24]:
                raise ValueError("execution event digest/id mismatch")
            previous = event.digest
        if not row.event_receipt_ids:
            raise ValueError("action has no lifecycle events")
        if self._events[row.event_receipt_ids[-1]].phase is not row.phase:
            raise ValueError("action phase disagrees with event chain head")
        return True

    @staticmethod
    def _single_event(history: tuple[ExecutionEvent, ...], event_type: str) -> ExecutionEvent | None:
        matches = tuple(event for event in history if event.event_type == event_type)
        if len(matches) > 1:
            raise ValueError(f"action lifecycle contains duplicate {event_type} events")
        return matches[0] if matches else None

    def _validate_record_projection(self, row: ActionRecord) -> None:
        history = self.events(row.action_id)
        if not history or history[0].event_type != "proposed" or history[0].phase is not ActionPhase.PROPOSED:
            raise ValueError("action record has no canonical proposed event")

        proposed_payload_digest = canonical_digest(
            {
                "contract_digest": canonical_digest(row.contract.to_state()),
                "semantic_digest": row.contract.semantic_digest,
            }
        )
        if history[0].payload_digest != proposed_payload_digest:
            raise ValueError("action record contract disagrees with proposed event")

        lease_acquired = self._single_event(history, "lease_acquired")
        renewal_events = tuple(event for event in history if event.event_type == "lease_renewed")
        revocation_events = tuple(event for event in history if event.event_type == "lease_revoked")
        if lease_acquired is None:
            if row.authorization_ref or row.lease is not None:
                raise ValueError("action record lease/authorization disagrees with lifecycle events")
        else:
            if row.lease is None:
                raise ValueError("action record lease missing despite lease event")
            acquired_refs = lease_acquired.evidence_refs
            if not acquired_refs or acquired_refs[0] != row.authorization_ref:
                raise ValueError("action record authorization disagrees with lease event")
            if len(acquired_refs) not in {1, 2}:
                raise ValueError("action record lease acquisition evidence is non-canonical")

            lifecycle_lease_id: str | None = None
            if len(acquired_refs) == 2:
                if not acquired_refs[1].startswith("lease:"):
                    raise ValueError("action record lease acquisition evidence is non-canonical")
                lifecycle_lease_id = acquired_refs[1][len("lease:"):]

            if row.lease.generation != 1 + len(renewal_events):
                raise ValueError("action record lease generation disagrees with lifecycle events")

            last_modern_previous_id: str | None = None
            for renewal in renewal_events:
                refs = renewal.evidence_refs
                if len(refs) == 1:  # schema-1 legacy renewal evidence
                    lifecycle_lease_id = None
                    last_modern_previous_id = None
                    continue
                if (
                    len(refs) != 3
                    or not refs[1].startswith("lease:")
                    or not refs[2].startswith("previous-lease:")
                ):
                    raise ValueError("action record lease renewal evidence is non-canonical")
                renewed_id = refs[1][len("lease:"):]
                previous_id = refs[2][len("previous-lease:"):]
                if lifecycle_lease_id is not None and previous_id != lifecycle_lease_id:
                    raise ValueError("action record lease renewal chain disagrees with lifecycle events")
                lifecycle_lease_id = renewed_id
                last_modern_previous_id = previous_id

            for revocation in revocation_events:
                refs = revocation.evidence_refs
                if len(refs) == 1:  # schema-1 legacy revocation evidence
                    lifecycle_lease_id = None
                    continue
                if len(refs) != 2 or not refs[1].startswith("lease:"):
                    raise ValueError("action record lease revocation evidence is non-canonical")
                revoked_id = refs[1][len("lease:"):]
                if lifecycle_lease_id is not None and revoked_id != lifecycle_lease_id:
                    raise ValueError("action record lease revocation disagrees with lifecycle events")
                lifecycle_lease_id = revoked_id

            if lifecycle_lease_id is not None and lifecycle_lease_id != row.lease.lease_id:
                raise ValueError("action record lease disagrees with lifecycle event evidence")
            if revocation_events and not row.lease.revoked:
                raise ValueError("action record lease revocation state disagrees with lifecycle events")
            if not revocation_events and row.lease.revoked:
                raise ValueError("action record lease is revoked without lifecycle evidence")

            if row.lease.generation == 1:
                expected_lease_digest = canonical_digest(
                    {
                        "action_id": row.action_id,
                        "owner_id": row.lease.owner_id,
                        "generation": row.lease.generation,
                        "issued_at_ms": row.lease.issued_at_ms,
                        "expires_at_ms": row.lease.expires_at_ms,
                        "authorization_ref": row.authorization_ref,
                    }
                )
                if row.lease.lease_id != "execution-lease-" + expected_lease_digest[:24]:
                    raise ValueError("action record lease digest is invalid")
            elif last_modern_previous_id is not None:
                expected_lease_digest = canonical_digest(
                    {
                        "action_id": row.action_id,
                        "owner_id": row.lease.owner_id,
                        "generation": row.lease.generation,
                        "issued_at_ms": row.lease.issued_at_ms,
                        "expires_at_ms": row.lease.expires_at_ms,
                        "previous_lease_id": last_modern_previous_id,
                    }
                )
                if row.lease.lease_id != "execution-lease-" + expected_lease_digest[:24]:
                    raise ValueError("action record renewed lease digest is invalid")

        preconditions = self._single_event(history, "preconditions_verified")
        expected_precondition_refs = () if preconditions is None else preconditions.evidence_refs
        if row.precondition_evidence_refs != expected_precondition_refs:
            raise ValueError("action record precondition evidence disagrees with lifecycle event")
        if preconditions is not None:
            expected_payload = canonical_digest(
                {"declared_preconditions": list(row.contract.preconditions)}
            )
            if preconditions.payload_digest != expected_payload:
                raise ValueError("action record preconditions disagree with lifecycle event")

        execution = self._single_event(history, "execution_started")
        if execution is None:
            if row.attempts or row.local_mutations or row.external_effects:
                raise ValueError("action record execution counters disagree with lifecycle events")
        else:
            expected_payload = canonical_digest(
                {
                    "attempt": row.attempts,
                    "local_mutations": row.local_mutations,
                    "external_effects": row.external_effects,
                    "effect_class": row.contract.effect_class.value,
                }
            )
            if execution.payload_digest != expected_payload:
                raise ValueError("action record execution counters disagree with lifecycle event")

        outcome = self._single_event(history, "outcome_observed")
        if outcome is None:
            if row.outcome_ref or row.outcome_success is not None:
                raise ValueError("action record outcome disagrees with lifecycle events")
        else:
            if row.outcome_success is None or outcome.evidence_refs != (row.outcome_ref,):
                raise ValueError("action record outcome disagrees with lifecycle event")
            expected_payload = canonical_digest({"success": bool(row.outcome_success)})
            if outcome.payload_digest != expected_payload:
                raise ValueError("action record outcome result disagrees with lifecycle event")

        postconditions = self._single_event(history, "postconditions_verified")
        if postconditions is None:
            if row.postcondition_evidence_refs or row.verifier_level is not VerifierLevel.V0:
                raise ValueError("action record postcondition state disagrees with lifecycle events")
        else:
            if postconditions.evidence_refs != row.postcondition_evidence_refs:
                raise ValueError("action record postcondition evidence disagrees with lifecycle event")
            expected_payload = canonical_digest(
                {
                    "verifier_level": int(row.verifier_level),
                    "declared_postconditions": list(row.contract.postconditions),
                }
            )
            if postconditions.payload_digest != expected_payload:
                raise ValueError("action record verifier state disagrees with lifecycle event")

        committed = self._single_event(history, "committed")
        if committed is None:
            if row.commit_ref:
                raise ValueError("action record commit disagrees with lifecycle events")
        else:
            if committed.evidence_refs != (row.commit_ref,):
                raise ValueError("action record commit reference disagrees with lifecycle event")
            if committed.payload_digest != canonical_digest({"outcome_ref": row.outcome_ref}):
                raise ValueError("action record commit outcome disagrees with lifecycle event")

        rolled_back = self._single_event(history, "rolled_back")
        degraded = self._single_event(history, "degraded")
        cancelled = self._single_event(history, "cancelled")
        terminal_events = tuple(x for x in (committed, rolled_back, degraded, cancelled) if x is not None)
        if len(terminal_events) > 1:
            raise ValueError("action record contains multiple terminal lifecycle events")
        if rolled_back is not None:
            if rolled_back.evidence_refs != (row.rollback_ref,):
                raise ValueError("action record rollback reference disagrees with lifecycle event")
            if rolled_back.payload_digest != canonical_digest({"failure_reason": row.failure_reason}):
                raise ValueError("action record rollback reason disagrees with lifecycle event")
        elif degraded is not None:
            if degraded.evidence_refs != (row.rollback_ref,):
                raise ValueError("action record recovery reference disagrees with lifecycle event")
            expected_payload = canonical_digest(
                {"failure_reason": row.failure_reason, "recovery_plan": row.contract.recovery_plan}
            )
            if degraded.payload_digest != expected_payload:
                raise ValueError("action record degraded recovery disagrees with lifecycle event")
        elif cancelled is not None:
            if cancelled.payload_digest != canonical_digest({"reason": row.failure_reason}):
                raise ValueError("action record cancellation reason disagrees with lifecycle event")
        elif row.rollback_ref or row.failure_reason:
            raise ValueError("action record terminal failure state has no lifecycle event")

    def _validate_state(self) -> None:
        referenced: set[str] = set()
        for row in self.records():
            if row.lease is not None and row.lease.action_id != row.action_id:
                raise ValueError("action contains lease for a different action")
            self.validate_chain(row.action_id)
            self._validate_record_projection(row)
            referenced.update(row.event_receipt_ids)
        if referenced != set(self._events):
            raise ValueError("protocol state contains orphan execution events")

    def to_state(self) -> dict[str, Any]:
        events = sorted(self._events.values(), key=lambda x: (x.action_id, x.sequence, x.receipt_id))
        return {
            "schema_version": PROTOCOL_SCHEMA_VERSION,
            "records": [row.to_state() for row in self.records()],
            "events": [row.to_state() for row in events],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ActingProtocolLedger":
        if int(state.get("schema_version", PROTOCOL_SCHEMA_VERSION)) != PROTOCOL_SCHEMA_VERSION:
            raise ValueError("unsupported acting protocol schema version")
        events = tuple(ExecutionEvent.from_state(row) for row in state.get("events", ()))
        records = tuple(ActionRecord.from_state(row) for row in state.get("records", ()))
        return cls(records=records, events=events)


__all__ = (
    "ActionBudget",
    "ActionPhase",
    "ActionRecord",
    "ActingProtocolLedger",
    "EffectClass",
    "ExecutionContract",
    "ExecutionEvent",
    "ExecutionLease",
    "ExecutionRisk",
    "IdempotencyConflict",
    "LeaseExpired",
    "ProtocolViolation",
    "VerifierLevel",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
)
