from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .architecture import InterfaceStability
from .types import canonical_digest


class CompatibilityClass(str, Enum):
    COMPATIBLE = 'compatible'
    BACKWARD_COMPATIBLE_ONLY = 'backward_compatible_only'
    FORWARD_COMPATIBLE_ONLY = 'forward_compatible_only'
    BREAKING = 'breaking'
    UNKNOWN = 'unknown'


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
            'assessment_id': self.assessment_id,
            'compatibility': self.compatibility.value,
            'integration_safe': self.integration_safe,
            'reason': self.reason,
            'evidence_refs': list(self.evidence_refs),
            'digest': self.digest,
        }

    @classmethod
    def from_state(cls, state):
        return cls(
            str(state['assessment_id']), CompatibilityClass(str(state['compatibility'])),
            bool(state['integration_safe']), str(state['reason']),
            tuple(str(x) for x in state.get('evidence_refs', ())), str(state['digest']),
        )


class CompatibilityEngine:
    @staticmethod
    def assess(*, old_signature_digest: str, new_signature_digest: str, old_semantic_version: str, new_semantic_version: str, stability: InterfaceStability, adapter_evidence_refs: tuple[str, ...], migration_evidence_refs: tuple[str, ...]) -> CompatibilityAssessment:
        if not old_signature_digest or not new_signature_digest or not old_semantic_version or not new_semantic_version:
            compatibility = CompatibilityClass.UNKNOWN
            safe = False
            reason = 'missing compatibility input'
        elif old_signature_digest == new_signature_digest:
            compatibility = CompatibilityClass.COMPATIBLE
            safe = True
            reason = 'interface signature unchanged'
        elif stability is InterfaceStability.PUBLIC and not adapter_evidence_refs and not migration_evidence_refs:
            compatibility = CompatibilityClass.BREAKING
            safe = False
            reason = 'public signature changed without adapter or migration evidence'
        elif adapter_evidence_refs or migration_evidence_refs:
            compatibility = CompatibilityClass.BACKWARD_COMPATIBLE_ONLY
            safe = True
            reason = 'changed signature covered by adapter/migration evidence'
        else:
            compatibility = CompatibilityClass.UNKNOWN
            safe = False
            reason = 'changed contract has insufficient compatibility evidence'
        evidence = tuple(dict.fromkeys(tuple(str(x) for x in adapter_evidence_refs) + tuple(str(x) for x in migration_evidence_refs)))
        payload = {
            'old_signature_digest': str(old_signature_digest), 'new_signature_digest': str(new_signature_digest),
            'old_semantic_version': str(old_semantic_version), 'new_semantic_version': str(new_semantic_version),
            'stability': InterfaceStability(stability).value, 'compatibility': compatibility.value,
            'integration_safe': safe, 'reason': reason, 'evidence_refs': list(evidence),
        }
        digest = canonical_digest(payload)
        return CompatibilityAssessment('compat-' + digest[:20], compatibility, safe, reason, evidence, digest)
