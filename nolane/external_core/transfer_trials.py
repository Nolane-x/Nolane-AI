from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.reasoning_invention import TransferIntent


COMPONENT_ID = "external.transfer_meta"
COMPONENT_VERSION = "0.0.2"
SCHEMA_VERSION = "transfer-trials-v1"


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _ids(values: Iterable[object], name: str, *, minimum: int = 0) -> tuple[str, ...]:
    rows = tuple(_nonempty(value, name) for value in values)
    if len(rows) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} values")
    if len(rows) != len(set(rows)):
        raise ValueError(f"{name} must not contain duplicate values")
    return tuple(sorted(rows))


def _identity(prefix: str, state: Mapping[str, object]) -> str:
    return f"{prefix}:{canonical_digest(dict(state))}"


@dataclass(frozen=True, slots=True)
class TransferTrialEnvelope:
    transfer_intent_id: str
    transfer_id: str
    portable_id: str
    source_domain: str
    target_domain: str
    source_receipt_ids: tuple[str, ...]
    verified_challenge_ids: tuple[str, ...]
    generalized_variables: tuple[str, ...]
    invariants: tuple[str, ...]
    target_assumptions: tuple[str, ...]
    required_trial_ids: tuple[str, ...]
    envelope_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "transfer_intent_id", _nonempty(self.transfer_intent_id, "transfer intent id"))
        object.__setattr__(self, "transfer_id", _nonempty(self.transfer_id, "transfer id"))
        object.__setattr__(self, "portable_id", _nonempty(self.portable_id, "portable id"))
        source = _nonempty(self.source_domain, "source domain")
        target = _nonempty(self.target_domain, "target domain")
        if source == target:
            raise ValueError("transfer source and target domains must differ")
        object.__setattr__(self, "source_domain", source)
        object.__setattr__(self, "target_domain", target)
        object.__setattr__(self, "source_receipt_ids", _ids(self.source_receipt_ids, "source receipt ids"))
        object.__setattr__(self, "verified_challenge_ids", _ids(self.verified_challenge_ids, "verified challenge ids"))
        if not self.source_receipt_ids and not self.verified_challenge_ids:
            raise ValueError("trial envelope requires source receipt or verified challenge")
        object.__setattr__(self, "generalized_variables", _ids(self.generalized_variables, "generalized variables", minimum=1))
        object.__setattr__(self, "invariants", _ids(self.invariants, "invariants", minimum=1))
        object.__setattr__(self, "target_assumptions", _ids(self.target_assumptions, "target assumptions"))
        object.__setattr__(self, "required_trial_ids", _ids(self.required_trial_ids, "required trial ids", minimum=1))
        object.__setattr__(self, "envelope_id", _identity("transfer-trial-envelope", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "transfer_intent_id": self.transfer_intent_id,
            "transfer_id": self.transfer_id,
            "portable_id": self.portable_id,
            "source_domain": self.source_domain,
            "target_domain": self.target_domain,
            "source_receipt_ids": list(self.source_receipt_ids),
            "verified_challenge_ids": list(self.verified_challenge_ids),
            "generalized_variables": list(self.generalized_variables),
            "invariants": list(self.invariants),
            "target_assumptions": list(self.target_assumptions),
            "required_trial_ids": list(self.required_trial_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "envelope_id": self.envelope_id, **self._semantic_state()}

    @classmethod
    def create(cls, intent: TransferIntent, adaptation: object) -> "TransferTrialEnvelope":
        if not isinstance(intent, TransferIntent):
            raise TypeError("intent must be TransferIntent")
        for name in ("transfer_id", "portable_id", "source_domain", "target_domain"):
            if not hasattr(adaptation, name):
                raise TypeError("adaptation must expose canonical transfer adaptation fields")
        if str(getattr(adaptation, "source_domain")) != intent.source_domain:
            raise ValueError("transfer intent source domain does not match adaptation")
        if str(getattr(adaptation, "target_domain")) != intent.target_domain:
            raise ValueError("transfer intent target domain does not match adaptation")
        return cls(
            transfer_intent_id=intent.transfer_intent_id,
            transfer_id=str(getattr(adaptation, "transfer_id")),
            portable_id=str(getattr(adaptation, "portable_id")),
            source_domain=intent.source_domain,
            target_domain=intent.target_domain,
            source_receipt_ids=intent.source_receipt_ids,
            verified_challenge_ids=intent.verified_challenge_ids,
            generalized_variables=intent.generalized_variables,
            invariants=intent.invariants,
            target_assumptions=intent.target_assumptions,
            required_trial_ids=intent.transfer_trial_ids,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "TransferTrialEnvelope":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported transfer trial envelope schema")
        row = cls(
            transfer_intent_id=state["transfer_intent_id"],
            transfer_id=state["transfer_id"],
            portable_id=state["portable_id"],
            source_domain=state["source_domain"],
            target_domain=state["target_domain"],
            source_receipt_ids=tuple(state.get("source_receipt_ids", ())),
            verified_challenge_ids=tuple(state.get("verified_challenge_ids", ())),
            generalized_variables=tuple(state.get("generalized_variables", ())),
            invariants=tuple(state.get("invariants", ())),
            target_assumptions=tuple(state.get("target_assumptions", ())),
            required_trial_ids=tuple(state.get("required_trial_ids", ())),
        )
        if str(state.get("envelope_id")) != row.envelope_id:
            raise ValueError("transfer trial envelope identity mismatch")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical transfer trial envelope state")
        return row


@dataclass(frozen=True, slots=True)
class DestinationTrialResult:
    trial_id: str
    target_regime_id: str
    verifier_id: str
    evidence_id: str
    passed: bool
    violated_invariant_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "trial_id", _nonempty(self.trial_id, "trial id"))
        object.__setattr__(self, "target_regime_id", _nonempty(self.target_regime_id, "target regime id"))
        object.__setattr__(self, "verifier_id", _nonempty(self.verifier_id, "verifier id"))
        object.__setattr__(self, "evidence_id", _nonempty(self.evidence_id, "evidence id"))
        if not isinstance(self.passed, bool):
            raise TypeError("trial passed must be bool")
        violations = _ids(self.violated_invariant_ids, "violated invariant ids")
        if self.passed and violations:
            raise ValueError("passing destination trial cannot violate invariants")
        object.__setattr__(self, "violated_invariant_ids", violations)

    def to_state(self) -> dict[str, object]:
        return {
            "trial_id": self.trial_id,
            "target_regime_id": self.target_regime_id,
            "verifier_id": self.verifier_id,
            "evidence_id": self.evidence_id,
            "passed": self.passed,
            "violated_invariant_ids": list(self.violated_invariant_ids),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "DestinationTrialResult":
        row = cls(
            trial_id=state["trial_id"],
            target_regime_id=state["target_regime_id"],
            verifier_id=state["verifier_id"],
            evidence_id=state["evidence_id"],
            passed=state["passed"],
            violated_invariant_ids=tuple(state.get("violated_invariant_ids", ())),
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical destination trial result state")
        return row


@dataclass(frozen=True, slots=True)
class DestinationTrialMatrix:
    envelope_id: str
    transfer_id: str
    required_trial_ids: tuple[str, ...]
    invariant_ids: tuple[str, ...]
    results: tuple[DestinationTrialResult, ...]
    matrix_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "envelope_id", _nonempty(self.envelope_id, "envelope id"))
        object.__setattr__(self, "transfer_id", _nonempty(self.transfer_id, "transfer id"))
        required = _ids(self.required_trial_ids, "required trial ids", minimum=1)
        invariants = _ids(self.invariant_ids, "invariant ids", minimum=1)
        rows = tuple(self.results)
        if not rows or not all(isinstance(row, DestinationTrialResult) for row in rows):
            raise TypeError("destination trial matrix requires trial results")
        rows = tuple(sorted(rows, key=lambda row: row.trial_id))
        trial_ids = tuple(row.trial_id for row in rows)
        if len(trial_ids) != len(set(trial_ids)):
            raise ValueError("destination trial matrix has duplicate trial ids")
        if set(trial_ids) != set(required):
            raise ValueError("destination trial matrix does not provide exact required trial coverage")
        evidence_ids = tuple(row.evidence_id for row in rows)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("destination trial evidence ids must be unique")
        verifier_ids = {row.verifier_id for row in rows}
        if len(rows) > 1 and len(verifier_ids) < 2:
            raise ValueError("destination trials require independent verifiers")
        allowed = set(invariants)
        violations = {item for row in rows for item in row.violated_invariant_ids}
        unknown = violations - allowed
        if unknown:
            raise ValueError(f"destination trial violates undeclared invariants: {sorted(unknown)}")
        object.__setattr__(self, "required_trial_ids", required)
        object.__setattr__(self, "invariant_ids", invariants)
        object.__setattr__(self, "results", rows)
        object.__setattr__(self, "matrix_id", _identity("destination-trial-matrix", self._semantic_state()))

    @property
    def passed(self) -> bool:
        return all(row.passed for row in self.results) and not self.violated_invariant_ids

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(sorted(row.evidence_id for row in self.results))

    @property
    def target_regime_ids(self) -> tuple[str, ...]:
        return tuple(sorted({row.target_regime_id for row in self.results}))

    @property
    def verifier_ids(self) -> tuple[str, ...]:
        return tuple(sorted({row.verifier_id for row in self.results}))

    @property
    def violated_invariant_ids(self) -> tuple[str, ...]:
        return tuple(sorted({item for row in self.results for item in row.violated_invariant_ids}))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "envelope_id": self.envelope_id,
            "transfer_id": self.transfer_id,
            "required_trial_ids": list(self.required_trial_ids),
            "invariant_ids": list(self.invariant_ids),
            "results": [row.to_state() for row in self.results],
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "matrix_id": self.matrix_id, **self._semantic_state()}

    @classmethod
    def create(
        cls,
        envelope: TransferTrialEnvelope,
        results: Iterable[DestinationTrialResult],
    ) -> "DestinationTrialMatrix":
        if not isinstance(envelope, TransferTrialEnvelope):
            raise TypeError("envelope must be TransferTrialEnvelope")
        return cls(
            envelope_id=envelope.envelope_id,
            transfer_id=envelope.transfer_id,
            required_trial_ids=envelope.required_trial_ids,
            invariant_ids=envelope.invariants,
            results=tuple(results),
        )

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "DestinationTrialMatrix":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported destination trial matrix schema")
        rows = tuple(
            DestinationTrialResult.from_state(row)
            for row in state.get("results", ())
        )
        matrix = cls(
            envelope_id=state["envelope_id"],
            transfer_id=state["transfer_id"],
            required_trial_ids=tuple(state.get("required_trial_ids", ())),
            invariant_ids=tuple(state.get("invariant_ids", ())),
            results=rows,
        )
        if str(state.get("matrix_id")) != matrix.matrix_id:
            raise ValueError("destination trial matrix identity mismatch")
        if matrix.to_state() != dict(state):
            raise ValueError("non-canonical destination trial matrix state")
        return matrix


@dataclass(frozen=True, slots=True)
class NegativeTransferRegimeRecord:
    transfer_id: str
    target_domain: str
    target_regime_id: str
    evidence_ids: tuple[str, ...]
    reason: str
    record_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "transfer_id", _nonempty(self.transfer_id, "transfer id"))
        object.__setattr__(self, "target_domain", _nonempty(self.target_domain, "target domain"))
        object.__setattr__(self, "target_regime_id", _nonempty(self.target_regime_id, "target regime id"))
        object.__setattr__(self, "evidence_ids", _ids(self.evidence_ids, "negative-transfer evidence ids", minimum=1))
        object.__setattr__(self, "reason", _nonempty(self.reason, "negative-transfer reason"))
        object.__setattr__(self, "record_id", _identity("negative-transfer-regime", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "transfer_id": self.transfer_id,
            "target_domain": self.target_domain,
            "target_regime_id": self.target_regime_id,
            "evidence_ids": list(self.evidence_ids),
            "reason": self.reason,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "record_id": self.record_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "NegativeTransferRegimeRecord":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported negative-transfer regime schema")
        row = cls(
            transfer_id=state["transfer_id"],
            target_domain=state["target_domain"],
            target_regime_id=state["target_regime_id"],
            evidence_ids=tuple(state.get("evidence_ids", ())),
            reason=state["reason"],
        )
        if str(state.get("record_id")) != row.record_id:
            raise ValueError("negative-transfer regime record identity mismatch")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical negative-transfer regime state")
        return row


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "TransferTrialEnvelope",
    "DestinationTrialResult",
    "DestinationTrialMatrix",
    "NegativeTransferRegimeRecord",
)
