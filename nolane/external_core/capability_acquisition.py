from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane, PromotionAssuranceReceipt
from nolane.external_core.cognitive_catalog import OperatorFamilyDescriptor
from nolane.external_core.cognitive_library import (
    COMPONENT_ID as COGNITIVE_LIBRARY_COMPONENT_ID,
    COMPONENT_VERSION as COGNITIVE_LIBRARY_COMPONENT_VERSION,
    CognitiveLibrary,
)
from nolane.external_core.cognitive_vocabulary import LearnedAbstraction


COMPONENT_ID = "external.capability_acquisition"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder R2.55 hardened capability-acquisition lineage"
_SCHEMA_VERSION = "capability-acquisition-v1"
_DEFAULT_MIN_RELIABILITY = 0.75


class CapabilityKind(str, Enum):
    OPERATOR_FAMILY = "operator_family"
    LEARNED_ABSTRACTION = "learned_abstraction"


class CapabilityState(str, Enum):
    CANDIDATE = "candidate"
    PROBATION = "probation"
    PROMOTED = "promoted"
    QUARANTINED = "quarantined"


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _payload_from_json(payload_json: str) -> dict[str, Any]:
    try:
        value = json.loads(payload_json)
    except (TypeError, ValueError) as exc:
        raise ValueError("capability payload must be canonical JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("capability payload must be a JSON object")
    if _canonical_json(value) != payload_json:
        raise ValueError("capability payload JSON is not canonical")
    return value


def _library_fragment(kind: CapabilityKind, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "cognitive-library-v1",
        "component_id": COGNITIVE_LIBRARY_COMPONENT_ID,
        "component_version": COGNITIVE_LIBRARY_COMPONENT_VERSION,
        "families": [dict(payload)] if kind is CapabilityKind.OPERATOR_FAMILY else [],
        "abstractions": [dict(payload)] if kind is CapabilityKind.LEARNED_ABSTRACTION else [],
    }


def _payload_state(value: OperatorFamilyDescriptor | LearnedAbstraction) -> tuple[CapabilityKind, dict[str, Any]]:
    if isinstance(value, OperatorFamilyDescriptor):
        state = CognitiveLibrary(families=(value,)).to_state()
        return CapabilityKind.OPERATOR_FAMILY, dict(state["families"][0])
    if isinstance(value, LearnedAbstraction):
        state = CognitiveLibrary(abstractions=(value,)).to_state()
        return CapabilityKind.LEARNED_ABSTRACTION, dict(state["abstractions"][0])
    raise TypeError("capability payload must be OperatorFamilyDescriptor or LearnedAbstraction")


def _decode_payload(kind: CapabilityKind, payload: Mapping[str, Any]) -> OperatorFamilyDescriptor | LearnedAbstraction:
    fragment = CognitiveLibrary.from_state(_library_fragment(kind, payload))
    if kind is CapabilityKind.OPERATOR_FAMILY:
        families = fragment.families()
        if len(families) != 1:
            raise ValueError("operator-family capability payload must decode to one family")
        return families[0]
    abstractions = fragment.vocabulary.abstractions()
    if len(abstractions) != 1:
        raise ValueError("learned-abstraction capability payload must decode to one abstraction")
    return abstractions[0]


@dataclass(frozen=True, slots=True)
class CapabilityCandidate:
    kind: CapabilityKind
    payload_json: str
    display_name: str
    candidate_id: str

    def __post_init__(self) -> None:
        kind = CapabilityKind(self.kind)
        payload_json = str(self.payload_json)
        payload = _payload_from_json(payload_json)
        # Decode through the canonical Cognitive Library parser so malformed or
        # non-canonical payloads never acquire a stable capability identity.
        _decode_payload(kind, payload)
        display_name = str(self.display_name).strip()
        semantic = {"kind": kind.value, "payload": payload}
        expected_id = f"capability:{canonical_digest(semantic)}"
        if str(self.candidate_id) != expected_id:
            raise ValueError("capability candidate identity mismatch")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "payload_json", payload_json)
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "candidate_id", expected_id)

    @classmethod
    def _from_payload(
        cls,
        value: OperatorFamilyDescriptor | LearnedAbstraction,
        *,
        display_name: str = "",
    ) -> "CapabilityCandidate":
        kind, payload = _payload_state(value)
        payload_json = _canonical_json(payload)
        semantic = {"kind": kind.value, "payload": payload}
        return cls(
            kind=kind,
            payload_json=payload_json,
            display_name=display_name,
            candidate_id=f"capability:{canonical_digest(semantic)}",
        )

    @classmethod
    def for_operator_family(
        cls,
        family: OperatorFamilyDescriptor,
        *,
        display_name: str = "",
    ) -> "CapabilityCandidate":
        if not isinstance(family, OperatorFamilyDescriptor):
            raise TypeError("family must be OperatorFamilyDescriptor")
        return cls._from_payload(family, display_name=display_name)

    @classmethod
    def for_learned_abstraction(
        cls,
        abstraction: LearnedAbstraction,
        *,
        display_name: str = "",
    ) -> "CapabilityCandidate":
        if not isinstance(abstraction, LearnedAbstraction):
            raise TypeError("abstraction must be LearnedAbstraction")
        return cls._from_payload(abstraction, display_name=display_name)

    def semantic_state(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "payload": _payload_from_json(self.payload_json)}

    def payload(self) -> OperatorFamilyDescriptor | LearnedAbstraction:
        return _decode_payload(self.kind, _payload_from_json(self.payload_json))

    def to_state(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "kind": self.kind.value,
            "payload": _payload_from_json(self.payload_json),
            "display_name": self.display_name,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CapabilityCandidate":
        payload = state.get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("capability candidate payload state is required")
        row = cls(
            kind=CapabilityKind(str(state["kind"])),
            payload_json=_canonical_json(payload),
            display_name=str(state.get("display_name", "")),
            candidate_id=str(state["candidate_id"]),
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical capability candidate state")
        return row


@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    candidate: CapabilityCandidate
    state: CapabilityState
    baseline_digest: str | None = None
    evidence_ids: tuple[str, ...] = ()
    independent_passed: bool | None = None
    challenge_passed: bool | None = None
    reliability: float | None = None
    assurance_receipt_id: str | None = None
    quarantine_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, CapabilityCandidate):
            raise TypeError("candidate must be CapabilityCandidate")
        state = CapabilityState(self.state)
        baseline = None if self.baseline_digest is None else str(self.baseline_digest).strip()
        evidence = tuple(str(value).strip() for value in self.evidence_ids)
        if any(not value for value in evidence) or len(set(evidence)) != len(evidence):
            raise ValueError("probation evidence ids must be non-empty and unique")
        reliability = self.reliability
        if reliability is not None:
            reliability = float(reliability)
            if not math.isfinite(reliability) or not 0.0 <= reliability <= 1.0:
                raise ValueError("probation reliability must be finite and within [0, 1]")
        receipt_id = None if self.assurance_receipt_id is None else str(self.assurance_receipt_id).strip()
        reason = None if self.quarantine_reason is None else str(self.quarantine_reason).strip()

        if state is CapabilityState.CANDIDATE:
            if any(
                value is not None
                for value in (
                    baseline,
                    self.independent_passed,
                    self.challenge_passed,
                    reliability,
                    receipt_id,
                    reason,
                )
            ) or evidence:
                raise ValueError("candidate state cannot carry probation or promotion authority")
        else:
            if not baseline:
                raise ValueError("non-candidate capability record requires probation baseline")
        if state is CapabilityState.PROMOTED:
            if not evidence or self.independent_passed is not True or self.challenge_passed is not True:
                raise ValueError("promoted capability requires passing probation evidence")
            if reliability is None or not receipt_id:
                raise ValueError("promoted capability requires reliability and assurance receipt")
            if reason:
                raise ValueError("promoted capability cannot carry quarantine reason")
        if state is CapabilityState.QUARANTINED and not reason:
            raise ValueError("quarantined capability requires reason")

        object.__setattr__(self, "state", state)
        object.__setattr__(self, "baseline_digest", baseline)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "reliability", reliability)
        object.__setattr__(self, "assurance_receipt_id", receipt_id)
        object.__setattr__(self, "quarantine_reason", reason)

    def to_state(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_state(),
            "state": self.state.value,
            "baseline_digest": self.baseline_digest,
            "evidence_ids": list(self.evidence_ids),
            "independent_passed": self.independent_passed,
            "challenge_passed": self.challenge_passed,
            "reliability": self.reliability,
            "assurance_receipt_id": self.assurance_receipt_id,
            "quarantine_reason": self.quarantine_reason,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CapabilityRecord":
        candidate_state = state.get("candidate")
        if not isinstance(candidate_state, Mapping):
            raise ValueError("capability record candidate state is required")
        row = cls(
            candidate=CapabilityCandidate.from_state(candidate_state),
            state=CapabilityState(str(state["state"])),
            baseline_digest=None if state.get("baseline_digest") is None else str(state["baseline_digest"]),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            independent_passed=None if state.get("independent_passed") is None else bool(state["independent_passed"]),
            challenge_passed=None if state.get("challenge_passed") is None else bool(state["challenge_passed"]),
            reliability=None if state.get("reliability") is None else float(state["reliability"]),
            assurance_receipt_id=None if state.get("assurance_receipt_id") is None else str(state["assurance_receipt_id"]),
            quarantine_reason=None if state.get("quarantine_reason") is None else str(state["quarantine_reason"]),
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical capability record state")
        return row


class CapabilityAcquisitionGovernor:
    """Fail-closed probation/promotion authority for Cognitive Library growth.

    Candidate generation is deliberately outside this component. This governor
    owns only admission, probation, Assurance-bound promotion, quarantine and
    the promoted-only retrieval firewall inherited from the R2.55 lifecycle.
    """

    def __init__(
        self,
        library: CognitiveLibrary,
        *,
        min_reliability: float = _DEFAULT_MIN_RELIABILITY,
        records: tuple[CapabilityRecord, ...] = (),
    ) -> None:
        if not isinstance(library, CognitiveLibrary):
            raise TypeError("library must be CognitiveLibrary")
        threshold = float(min_reliability)
        if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
            raise ValueError("minimum reliability must be finite and within [0, 1]")
        self.library = library
        self.min_reliability = threshold
        self._records: dict[str, CapabilityRecord] = {}
        for record in records:
            if not isinstance(record, CapabilityRecord):
                raise TypeError("records must contain CapabilityRecord values")
            candidate_id = record.candidate.candidate_id
            if candidate_id in self._records:
                raise ValueError("duplicate capability record identity")
            self._records[candidate_id] = record
        self._validate_library_bindings()

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def records(self) -> tuple[CapabilityRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def record(self, candidate_id: str) -> CapabilityRecord:
        try:
            return self._records[str(candidate_id)]
        except KeyError:
            raise KeyError(str(candidate_id)) from None

    @staticmethod
    def _candidate_in_library(library: CognitiveLibrary, candidate: CapabilityCandidate) -> bool:
        payload = candidate.payload()
        try:
            if candidate.kind is CapabilityKind.OPERATOR_FAMILY:
                assert isinstance(payload, OperatorFamilyDescriptor)
                return library.family(payload.family_id) == payload
            assert isinstance(payload, LearnedAbstraction)
            return library.vocabulary.get(payload.abstraction_id) == payload
        except KeyError:
            return False

    def _validate_library_bindings(self) -> None:
        for record in self._records.values():
            installed = self._candidate_in_library(self.library, record.candidate)
            authority_requires_install = (
                record.state is CapabilityState.PROMOTED
                or (
                    record.state is CapabilityState.QUARANTINED
                    and record.assurance_receipt_id is not None
                )
            )
            if authority_requires_install and not installed:
                if record.state is CapabilityState.PROMOTED:
                    raise ValueError("promoted capability is missing from cognitive library")
                raise ValueError("revoked promoted capability is missing from cognitive library")
            if not authority_requires_install and installed:
                raise ValueError("non-promoted capability is unexpectedly present in cognitive library")

    def admit(self, candidate: CapabilityCandidate) -> CapabilityRecord:
        if not isinstance(candidate, CapabilityCandidate):
            raise TypeError("candidate must be CapabilityCandidate")
        if candidate.candidate_id in self._records:
            raise ValueError("duplicate capability candidate identity")
        if self._candidate_in_library(self.library, candidate):
            raise ValueError("capability is already present in cognitive library")
        record = CapabilityRecord(candidate=candidate, state=CapabilityState.CANDIDATE)
        self._records[candidate.candidate_id] = record
        return record

    def begin_probation(self, candidate_id: str) -> CapabilityRecord:
        record = self.record(candidate_id)
        if record.state is CapabilityState.QUARANTINED:
            raise ValueError("quarantined capability cannot re-enter probation")
        if record.state is not CapabilityState.CANDIDATE:
            raise ValueError("only a candidate capability can enter probation")
        updated = replace(
            record,
            state=CapabilityState.PROBATION,
            baseline_digest=self.library.digest,
        )
        self._records[record.candidate.candidate_id] = updated
        return updated

    def record_probation(
        self,
        candidate_id: str,
        *,
        evidence_ids: tuple[str, ...],
        independent_passed: bool,
        challenge_passed: bool,
        reliability: float,
    ) -> CapabilityRecord:
        record = self.record(candidate_id)
        if record.state is not CapabilityState.PROBATION:
            raise ValueError("probation evidence requires a capability in probation")
        evidence = tuple(str(value).strip() for value in evidence_ids)
        if not evidence or any(not value for value in evidence) or len(set(evidence)) != len(evidence):
            raise ValueError("probation requires unique non-empty evidence ids")
        score = float(reliability)
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError("probation reliability must be finite and within [0, 1]")
        passed = bool(independent_passed) and bool(challenge_passed) and score >= self.min_reliability
        updated = replace(
            record,
            state=CapabilityState.PROBATION if passed else CapabilityState.QUARANTINED,
            evidence_ids=evidence,
            independent_passed=bool(independent_passed),
            challenge_passed=bool(challenge_passed),
            reliability=score,
            quarantine_reason=None if passed else "probation_gate_failed",
        )
        self._records[record.candidate.candidate_id] = updated
        return updated

    @staticmethod
    def _validated_persisted_receipt(
        assurance: AssuranceControlPlane,
        receipt: PromotionAssuranceReceipt,
    ) -> PromotionAssuranceReceipt:
        if not isinstance(assurance, AssuranceControlPlane):
            raise TypeError("assurance must be native AssuranceControlPlane")
        if not isinstance(receipt, PromotionAssuranceReceipt):
            raise TypeError("receipt must be PromotionAssuranceReceipt")
        # Recompute the native receipt digest instead of trusting a detached
        # dataclass instance supplied by the caller.
        PromotionAssuranceReceipt.from_state(receipt.to_state())
        try:
            persisted = AssuranceControlPlane.promotion_receipt(assurance, receipt.receipt_id)
        except (KeyError, LookupError) as exc:
            raise ValueError("persisted assurance receipt is required") from exc
        if not isinstance(persisted, PromotionAssuranceReceipt):
            raise ValueError("persisted assurance receipt has invalid type")
        PromotionAssuranceReceipt.from_state(persisted.to_state())
        if persisted != receipt:
            raise ValueError("persisted assurance receipt does not match supplied receipt")
        return persisted

    @classmethod
    def _validate_restored_assurance(
        cls,
        assurance: AssuranceControlPlane | None,
        record: CapabilityRecord,
    ) -> None:
        if record.assurance_receipt_id is None:
            return
        if not isinstance(assurance, AssuranceControlPlane):
            raise ValueError("persisted assurance authority is required to restore capability")
        try:
            receipt = AssuranceControlPlane.promotion_receipt(
                assurance, record.assurance_receipt_id
            )
        except (KeyError, LookupError) as exc:
            raise ValueError(
                "persisted assurance receipt is required to restore capability authority"
            ) from exc
        persisted = cls._validated_persisted_receipt(assurance, receipt)
        if not persisted.authorized:
            raise ValueError("restored promotion assurance receipt is not authorized")
        if persisted.subject_id != record.candidate.candidate_id:
            raise ValueError("restored promotion assurance receipt subject mismatch")
        if tuple(persisted.evidence_ids) != record.evidence_ids:
            raise ValueError("restored promotion assurance receipt evidence mismatch")
        if persisted.predecessor_version != record.baseline_digest:
            raise ValueError("restored promotion assurance receipt baseline mismatch")

    def promote(
        self,
        candidate_id: str,
        *,
        assurance: AssuranceControlPlane,
        receipt: PromotionAssuranceReceipt,
    ) -> CapabilityRecord:
        record = self.record(candidate_id)
        if record.state is CapabilityState.QUARANTINED:
            raise ValueError("quarantined capability cannot be promoted")
        if record.state is not CapabilityState.PROBATION:
            raise ValueError("only a capability in probation can be promoted")
        if (
            not record.evidence_ids
            or record.independent_passed is not True
            or record.challenge_passed is not True
            or record.reliability is None
            or record.reliability < self.min_reliability
        ):
            raise ValueError("capability has not passed probation gates")
        if self.library.digest != record.baseline_digest:
            raise ValueError("cognitive library baseline changed during probation")

        persisted = self._validated_persisted_receipt(assurance, receipt)
        if not persisted.authorized:
            raise ValueError("promotion assurance receipt is not authorized")
        if persisted.subject_id != record.candidate.candidate_id:
            raise ValueError("promotion assurance receipt subject mismatch")
        if tuple(persisted.evidence_ids) != record.evidence_ids:
            raise ValueError("promotion assurance receipt evidence mismatch")
        if persisted.predecessor_version != record.baseline_digest:
            raise ValueError("promotion assurance receipt baseline mismatch")

        payload = record.candidate.payload()
        if record.candidate.kind is CapabilityKind.OPERATOR_FAMILY:
            assert isinstance(payload, OperatorFamilyDescriptor)
            self.library.register_family(payload)
        else:
            assert isinstance(payload, LearnedAbstraction)
            self.library.register_abstraction(payload)

        updated = replace(
            record,
            state=CapabilityState.PROMOTED,
            assurance_receipt_id=persisted.receipt_id,
        )
        self._records[record.candidate.candidate_id] = updated
        return updated

    def retrievable_ids(self) -> tuple[str, ...]:
        return tuple(
            key
            for key in sorted(self._records)
            if self._records[key].state is CapabilityState.PROMOTED
        )

    def retrieve(self, candidate_id: str) -> OperatorFamilyDescriptor | LearnedAbstraction:
        record = self.record(candidate_id)
        if record.state is not CapabilityState.PROMOTED:
            raise PermissionError("capability is not promoted through the acquisition firewall")
        if not self._candidate_in_library(self.library, record.candidate):
            raise RuntimeError("promoted capability/library binding is broken")
        return record.candidate.payload()

    def quarantine(self, candidate_id: str, *, reason: str) -> CapabilityRecord:
        record = self.record(candidate_id)
        clean_reason = str(reason).strip()
        if not clean_reason:
            raise ValueError("quarantine reason must be non-empty")
        if record.state is CapabilityState.QUARANTINED:
            return record
        updated = replace(
            record,
            state=CapabilityState.QUARANTINED,
            baseline_digest=record.baseline_digest or self.library.digest,
            quarantine_reason=clean_reason,
        )
        self._records[record.candidate.candidate_id] = updated
        return updated

    def report_live_failure(self, candidate_id: str, *, reason: str) -> CapabilityRecord:
        record = self.record(candidate_id)
        if record.state is not CapabilityState.PROMOTED:
            raise ValueError("live failure can only revoke a promoted capability")
        clean_reason = str(reason).strip()
        if not clean_reason:
            raise ValueError("live failure reason must be non-empty")
        updated = replace(
            record,
            state=CapabilityState.QUARANTINED,
            quarantine_reason=f"live_failure:{clean_reason}",
        )
        self._records[record.candidate.candidate_id] = updated
        return updated

    def to_state(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "component_id": COMPONENT_ID,
            "component_version": COMPONENT_VERSION,
            "min_reliability": self.min_reliability,
            "records": [record.to_state() for record in self.records()],
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        library: CognitiveLibrary,
        assurance: AssuranceControlPlane | None = None,
    ) -> "CapabilityAcquisitionGovernor":
        if str(state.get("schema_version")) != _SCHEMA_VERSION:
            raise ValueError("unsupported capability acquisition schema")
        if str(state.get("component_id")) != COMPONENT_ID:
            raise ValueError("capability acquisition component mismatch")
        if str(state.get("component_version")) != COMPONENT_VERSION:
            raise ValueError("capability acquisition component version mismatch")
        records_state = state.get("records", ())
        if not isinstance(records_state, (list, tuple)):
            raise ValueError("capability acquisition records must be a sequence")
        records = tuple(CapabilityRecord.from_state(row) for row in records_state)
        result = cls(
            library,
            min_reliability=float(state.get("min_reliability", _DEFAULT_MIN_RELIABILITY)),
            records=records,
        )
        for record in result.records():
            cls._validate_restored_assurance(assurance, record)
        if result.to_state() != dict(state):
            raise ValueError("non-canonical capability acquisition state")
        return result


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
    "CapabilityKind",
    "CapabilityState",
    "CapabilityCandidate",
    "CapabilityRecord",
    "CapabilityAcquisitionGovernor",
)
