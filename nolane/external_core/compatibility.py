from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.architecture import InterfaceStability

SEMANTIC_SURFACE_ID = "external.integration.compatibility"
SEMANTIC_SURFACE_VERSION = "0.0.8"
MIGRATED_FROM = "cogcoder.organization.compatibility"


def _canonical_state_record(
    state: object,
    expected_keys: tuple[str, ...],
    label: str,
) -> Mapping[str, Any]:
    if type(state) is not dict or set(state) != set(expected_keys):
        raise ValueError(f"{label} must use canonical serialized state")
    return state


def _canonical_state_list(value: object, label: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f"{label} must use canonical serialized state")
    return value


def _exact_string(value: object, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{label} must be an exact string")
    return value


def _exact_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must be an exact bool")
    return value


class CompatibilityClass(str, Enum):
    COMPATIBLE = "compatible"
    BACKWARD_COMPATIBLE_ONLY = "backward_compatible_only"
    FORWARD_COMPATIBLE_ONLY = "forward_compatible_only"
    BREAKING = "breaking"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CompatibilityAssessment:
    assessment_id: str
    compatibility: CompatibilityClass
    integration_safe: bool
    reason: str
    evidence_refs: tuple[str, ...]
    digest: str

    def to_state(self) -> dict[str, object]:
        return {
            "assessment_id": self.assessment_id,
            "compatibility": self.compatibility.value,
            "integration_safe": self.integration_safe,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CompatibilityAssessment":
        state = _canonical_state_record(
            state,
            (
                "assessment_id",
                "compatibility",
                "integration_safe",
                "reason",
                "evidence_refs",
                "digest",
            ),
            "compatibility assessment",
        )
        evidence_refs = tuple(
            _exact_string(value, "compatibility evidence reference")
            for value in _canonical_state_list(
                state["evidence_refs"],
                "compatibility evidence references",
            )
        )
        return cls(
            _exact_string(state["assessment_id"], "compatibility assessment identity"),
            CompatibilityClass(
                _exact_string(state["compatibility"], "compatibility classification")
            ),
            _exact_bool(state["integration_safe"], "compatibility integration_safe"),
            _exact_string(state["reason"], "compatibility reason"),
            evidence_refs,
            _exact_string(state["digest"], "compatibility digest"),
        )


class CompatibilityEngine:
    @staticmethod
    def assess(
        *,
        old_signature_digest: str,
        new_signature_digest: str,
        old_semantic_version: str,
        new_semantic_version: str,
        stability: InterfaceStability,
        adapter_evidence_refs: tuple[str, ...],
        migration_evidence_refs: tuple[str, ...],
    ) -> CompatibilityAssessment:
        if not old_signature_digest or not new_signature_digest or not old_semantic_version or not new_semantic_version:
            compatibility = CompatibilityClass.UNKNOWN
            safe = False
            reason = "missing compatibility input"
        elif old_signature_digest == new_signature_digest:
            compatibility = CompatibilityClass.COMPATIBLE
            safe = True
            reason = "interface signature unchanged"
        elif stability is InterfaceStability.PUBLIC and not adapter_evidence_refs and not migration_evidence_refs:
            compatibility = CompatibilityClass.BREAKING
            safe = False
            reason = "public signature changed without adapter or migration evidence"
        elif adapter_evidence_refs or migration_evidence_refs:
            compatibility = CompatibilityClass.BACKWARD_COMPATIBLE_ONLY
            safe = True
            reason = "changed signature covered by adapter/migration evidence"
        else:
            compatibility = CompatibilityClass.UNKNOWN
            safe = False
            reason = "changed contract has insufficient compatibility evidence"

        evidence = tuple(
            dict.fromkeys(
                tuple(str(x) for x in adapter_evidence_refs)
                + tuple(str(x) for x in migration_evidence_refs)
            )
        )
        payload = {
            "old_signature_digest": str(old_signature_digest),
            "new_signature_digest": str(new_signature_digest),
            "old_semantic_version": str(old_semantic_version),
            "new_semantic_version": str(new_semantic_version),
            "stability": InterfaceStability(stability).value,
            "compatibility": compatibility.value,
            "integration_safe": safe,
            "reason": reason,
            "evidence_refs": list(evidence),
        }
        digest = canonical_digest(payload)
        return CompatibilityAssessment(
            "compat-" + digest[:20],
            compatibility,
            safe,
            reason,
            evidence,
            digest,
        )


__all__ = [
    "CompatibilityAssessment",
    "CompatibilityClass",
    "CompatibilityEngine",
]
