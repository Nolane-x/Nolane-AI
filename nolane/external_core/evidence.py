from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.evidence"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.types.EvidenceRecord"
SCOPED_EVIDENCE_PROTOCOL = "scoped-evidence-v2"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    verifier_agent_id: str
    passed: bool
    false_accepts: int = 0
    regressions: int = 0
    notes: str = ""

    def __post_init__(self) -> None:
        if self.false_accepts < 0 or self.regressions < 0:
            raise ValueError("evidence counters must be non-negative")
        if not self.evidence_id or not self.verifier_agent_id:
            raise ValueError("evidence identity must be explicit")

    def to_state(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "verifier_agent_id": self.verifier_agent_id,
            "passed": self.passed,
            "false_accepts": self.false_accepts,
            "regressions": self.regressions,
            "notes": self.notes,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EvidenceRecord":
        return cls(
            str(state["evidence_id"]),
            str(state["verifier_agent_id"]),
            bool(state["passed"]),
            int(state.get("false_accepts", 0)),
            int(state.get("regressions", 0)),
            str(state.get("notes", "")),
        )


@dataclass(frozen=True, slots=True)
class ScopedEvidenceRecord:
    evidence_id: str
    subject_id: str
    subject_version: str
    subject_digest: str
    scope_digest: str
    verifier_agent_id: str
    observed_epoch: int
    passed: bool
    false_accepts: int
    regressions: int
    evidence_refs: tuple[str, ...]
    limitations: tuple[str, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        evidence_id: str,
        subject_id: str,
        subject_version: str,
        subject_digest: str,
        scope_digest: str,
        verifier_agent_id: str,
        observed_epoch: int,
        passed: bool,
        false_accepts: int = 0,
        regressions: int = 0,
        evidence_refs: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> "ScopedEvidenceRecord":
        identity = _explicit(evidence_id, "scoped evidence identity")
        subject = _explicit(subject_id, "scoped evidence subject")
        version = _explicit(subject_version, "scoped evidence subject version")
        subject_state_digest = _explicit(subject_digest, "scoped evidence subject digest")
        scope = _explicit(scope_digest, "scoped evidence scope digest")
        verifier = _explicit(verifier_agent_id, "scoped evidence verifier")
        epoch = _strict_non_negative_int(observed_epoch, "scoped evidence observed epoch")
        if type(passed) is not bool:
            raise ValueError("scoped evidence passed must be an exact boolean")
        false_accept_count = _strict_non_negative_int(false_accepts, "scoped evidence false accepts")
        regression_count = _strict_non_negative_int(regressions, "scoped evidence regressions")
        refs = _canonical_strings(evidence_refs, "scoped evidence refs", require_non_empty=True)
        limits = _canonical_strings(limitations, "scoped evidence limitations", require_non_empty=False)
        payload = {
            "protocol": SCOPED_EVIDENCE_PROTOCOL,
            "evidence_id": identity,
            "subject_id": subject,
            "subject_version": version,
            "subject_digest": subject_state_digest,
            "scope_digest": scope,
            "verifier_agent_id": verifier,
            "observed_epoch": epoch,
            "passed": passed,
            "false_accepts": false_accept_count,
            "regressions": regression_count,
            "evidence_refs": list(refs),
            "limitations": list(limits),
        }
        return cls(
            evidence_id=identity,
            subject_id=subject,
            subject_version=version,
            subject_digest=subject_state_digest,
            scope_digest=scope,
            verifier_agent_id=verifier,
            observed_epoch=epoch,
            passed=passed,
            false_accepts=false_accept_count,
            regressions=regression_count,
            evidence_refs=refs,
            limitations=limits,
            digest="scoped-evidence-v2-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": SCOPED_EVIDENCE_PROTOCOL,
            "evidence_id": self.evidence_id,
            "subject_id": self.subject_id,
            "subject_version": self.subject_version,
            "subject_digest": self.subject_digest,
            "scope_digest": self.scope_digest,
            "verifier_agent_id": self.verifier_agent_id,
            "observed_epoch": self.observed_epoch,
            "passed": self.passed,
            "false_accepts": self.false_accepts,
            "regressions": self.regressions,
            "evidence_refs": list(self.evidence_refs),
            "limitations": list(self.limitations),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ScopedEvidenceRecord":
        if not isinstance(state, Mapping):
            raise ValueError("scoped evidence state must be an object")
        if state.get("protocol") != SCOPED_EVIDENCE_PROTOCOL:
            raise ValueError("scoped evidence protocol mismatch")
        raw_refs = state.get("evidence_refs")
        raw_limitations = state.get("limitations")
        if not isinstance(raw_refs, list) or not isinstance(raw_limitations, list):
            raise ValueError("scoped evidence refs and limitations must be lists")
        expected = cls.create(
            evidence_id=state.get("evidence_id"),
            subject_id=state.get("subject_id"),
            subject_version=state.get("subject_version"),
            subject_digest=state.get("subject_digest"),
            scope_digest=state.get("scope_digest"),
            verifier_agent_id=state.get("verifier_agent_id"),
            observed_epoch=state.get("observed_epoch"),
            passed=state.get("passed"),
            false_accepts=state.get("false_accepts"),
            regressions=state.get("regressions"),
            evidence_refs=tuple(raw_refs),
            limitations=tuple(raw_limitations),
        )
        if state.get("digest") != expected.digest:
            raise ValueError("scoped evidence digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("scoped evidence state is non-canonical")
        return expected

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("scoped evidence integrity validation failed") from exc
        if restored != self:
            raise ValueError("scoped evidence integrity validation failed")


def _explicit(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be an explicit string")
    return value


def _strict_non_negative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _canonical_strings(values: object, label: str, *, require_non_empty: bool) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{label} must be a tuple")
    normalized = tuple(_explicit(value, label) for value in values)
    if require_non_empty and not normalized:
        raise ValueError(f"{label} requires evidence refs/provenance")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(normalized))


__all__ = (
    "EvidenceRecord",
    "ScopedEvidenceRecord",
    "SCOPED_EVIDENCE_PROTOCOL",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
