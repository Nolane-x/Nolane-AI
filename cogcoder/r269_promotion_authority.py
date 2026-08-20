from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from .r269_scoped_promotion import (
    ChampionChallengerEvidence,
    PromotionCandidate,
    PromotionDecision,
    PromotionRegistryEvent,
    ScopedPromotionController,
    ScopedPromotionRegistry,
)

_HEX64 = re.compile(r'^[0-9a-f]{64}$')


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f'{name} must be non-empty')
    return text


def _hex64(value: object, name: str) -> str:
    text = _nonempty(value, name).lower()
    if _HEX64.fullmatch(text) is None:
        raise ValueError(f'{name} must be a 64-hex digest')
    return text


def _sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _attestation_payload(
    *,
    evidence_digest: str,
    candidate_artifact_digest: str,
    structural_class_digest: str,
    freeze_receipt_digest: str,
    authority_root_digest: str,
    verifier_issuer: str,
    hosted_run_identity: str,
    source_tree_digest: str,
) -> dict[str, object]:
    return {
        'schema_version': 1,
        'evidence_digest': evidence_digest,
        'candidate_artifact_digest': candidate_artifact_digest,
        'structural_class_digest': structural_class_digest,
        'freeze_receipt_digest': freeze_receipt_digest,
        'authority_root_digest': authority_root_digest,
        'verifier_issuer': verifier_issuer,
        'hosted_run_identity': hosted_run_identity,
        'source_tree_digest': source_tree_digest,
    }


@dataclass(frozen=True, slots=True)
class HostedVerifierAttestation:
    evidence_digest: str
    candidate_artifact_digest: str
    structural_class_digest: str
    freeze_receipt_digest: str
    authority_root_digest: str
    verifier_issuer: str
    hosted_run_identity: str
    source_tree_digest: str
    attestation_digest: str

    def __post_init__(self) -> None:
        evidence = _nonempty(self.evidence_digest, 'evidence_digest')
        artifact = _nonempty(self.candidate_artifact_digest, 'candidate_artifact_digest')
        scope = _hex64(self.structural_class_digest, 'structural_class_digest')
        freeze = _nonempty(self.freeze_receipt_digest, 'freeze_receipt_digest')
        root = _hex64(self.authority_root_digest, 'authority_root_digest')
        issuer = _nonempty(self.verifier_issuer, 'verifier_issuer')
        run = _nonempty(self.hosted_run_identity, 'hosted_run_identity')
        tree = _hex64(self.source_tree_digest, 'source_tree_digest')
        payload = _attestation_payload(
            evidence_digest=evidence,
            candidate_artifact_digest=artifact,
            structural_class_digest=scope,
            freeze_receipt_digest=freeze,
            authority_root_digest=root,
            verifier_issuer=issuer,
            hosted_run_identity=run,
            source_tree_digest=tree,
        )
        expected = 'r269.hosted-promotion-attestation.' + _sha(payload)
        if self.attestation_digest != expected:
            raise ValueError('attestation_digest must bind exact hosted verifier receipt content')
        object.__setattr__(self, 'evidence_digest', evidence)
        object.__setattr__(self, 'candidate_artifact_digest', artifact)
        object.__setattr__(self, 'structural_class_digest', scope)
        object.__setattr__(self, 'freeze_receipt_digest', freeze)
        object.__setattr__(self, 'authority_root_digest', root)
        object.__setattr__(self, 'verifier_issuer', issuer)
        object.__setattr__(self, 'hosted_run_identity', run)
        object.__setattr__(self, 'source_tree_digest', tree)

    @classmethod
    def create(
        cls,
        *,
        evidence: ChampionChallengerEvidence,
        candidate: PromotionCandidate,
        authority_root_digest: str,
        verifier_issuer: str,
        hosted_run_identity: str,
        source_tree_digest: str,
    ) -> 'HostedVerifierAttestation':
        if not isinstance(evidence, ChampionChallengerEvidence):
            raise TypeError('evidence must be ChampionChallengerEvidence')
        if not isinstance(candidate, PromotionCandidate):
            raise TypeError('candidate must be PromotionCandidate')
        root = _hex64(authority_root_digest, 'authority_root_digest')
        issuer = _nonempty(verifier_issuer, 'verifier_issuer')
        run = _nonempty(hosted_run_identity, 'hosted_run_identity')
        tree = _hex64(source_tree_digest, 'source_tree_digest')
        payload = _attestation_payload(
            evidence_digest=evidence.evidence_digest,
            candidate_artifact_digest=candidate.artifact_digest,
            structural_class_digest=candidate.structural_class_digest,
            freeze_receipt_digest=candidate.freeze_receipt_digest,
            authority_root_digest=root,
            verifier_issuer=issuer,
            hosted_run_identity=run,
            source_tree_digest=tree,
        )
        return cls(
            evidence_digest=evidence.evidence_digest,
            candidate_artifact_digest=candidate.artifact_digest,
            structural_class_digest=candidate.structural_class_digest,
            freeze_receipt_digest=candidate.freeze_receipt_digest,
            authority_root_digest=root,
            verifier_issuer=issuer,
            hosted_run_identity=run,
            source_tree_digest=tree,
            attestation_digest='r269.hosted-promotion-attestation.' + _sha(payload),
        )


def _envelope_payload(
    *, decision_digest: str, attestation_digest: str, authority_root_digest: str
) -> dict[str, object]:
    return {
        'schema_version': 1,
        'decision_digest': decision_digest,
        'attestation_digest': attestation_digest,
        'authority_root_digest': authority_root_digest,
    }


@dataclass(frozen=True, slots=True)
class AuthorityBoundPromotion:
    decision: PromotionDecision
    attestation: HostedVerifierAttestation
    authority_root_digest: str
    envelope_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.decision, PromotionDecision):
            raise TypeError('decision must be PromotionDecision')
        if not isinstance(self.attestation, HostedVerifierAttestation):
            raise TypeError('attestation must be HostedVerifierAttestation')
        root = _hex64(self.authority_root_digest, 'authority_root_digest')
        if self.attestation.authority_root_digest != root:
            raise ValueError('attestation authority root does not match promotion envelope')
        if self.decision.evidence_digest != self.attestation.evidence_digest:
            raise ValueError('decision evidence is not bound to hosted attestation')
        if self.decision.candidate_artifact_digest != self.attestation.candidate_artifact_digest:
            raise ValueError('decision artifact is not bound to hosted attestation')
        if self.decision.structural_class_digest != self.attestation.structural_class_digest:
            raise ValueError('decision scope is not bound to hosted attestation')
        if self.decision.freeze_receipt_digest != self.attestation.freeze_receipt_digest:
            raise ValueError('decision freeze receipt is not bound to hosted attestation')
        payload = _envelope_payload(
            decision_digest=self.decision.decision_digest,
            attestation_digest=self.attestation.attestation_digest,
            authority_root_digest=root,
        )
        expected = 'r269.authority-bound-promotion.' + _sha(payload)
        if self.envelope_digest != expected:
            raise ValueError('envelope_digest must bind decision and hosted attestation')
        object.__setattr__(self, 'authority_root_digest', root)


class PromotionEvidenceAuthority:
    def __init__(self, authority_root_digest: str, verifier_issuer: str) -> None:
        self.authority_root_digest = _hex64(authority_root_digest, 'authority_root_digest')
        self.verifier_issuer = _nonempty(verifier_issuer, 'verifier_issuer')

    def adjudicate(
        self,
        candidate: PromotionCandidate,
        evidence: ChampionChallengerEvidence,
        attestation: HostedVerifierAttestation,
    ) -> AuthorityBoundPromotion:
        if not isinstance(candidate, PromotionCandidate):
            raise TypeError('candidate must be PromotionCandidate')
        if not isinstance(evidence, ChampionChallengerEvidence):
            raise TypeError('evidence must be ChampionChallengerEvidence')
        if not isinstance(attestation, HostedVerifierAttestation):
            raise TypeError('attestation must be HostedVerifierAttestation')
        if attestation.authority_root_digest != self.authority_root_digest:
            raise ValueError('hosted attestation authority root is not trusted')
        if attestation.verifier_issuer != self.verifier_issuer:
            raise ValueError('hosted attestation verifier issuer is not trusted')
        if evidence.verifier_issuer != self.verifier_issuer:
            raise ValueError('evidence verifier issuer does not match hosted authority')
        if attestation.evidence_digest != evidence.evidence_digest:
            raise ValueError('hosted attestation evidence digest mismatch')
        if attestation.candidate_artifact_digest != candidate.artifact_digest:
            raise ValueError('hosted attestation candidate artifact mismatch')
        if attestation.structural_class_digest != candidate.structural_class_digest:
            raise ValueError('hosted attestation structural scope mismatch')
        if attestation.freeze_receipt_digest != candidate.freeze_receipt_digest:
            raise ValueError('hosted attestation freeze receipt mismatch')

        decision = ScopedPromotionController().adjudicate(candidate, evidence)
        payload = _envelope_payload(
            decision_digest=decision.decision_digest,
            attestation_digest=attestation.attestation_digest,
            authority_root_digest=self.authority_root_digest,
        )
        return AuthorityBoundPromotion(
            decision=decision,
            attestation=attestation,
            authority_root_digest=self.authority_root_digest,
            envelope_digest='r269.authority-bound-promotion.' + _sha(payload),
        )


class AuthorityBoundPromotionRegistry(ScopedPromotionRegistry):
    def __init__(self, authority_root_digest: str) -> None:
        super().__init__()
        self.authority_root_digest = _hex64(authority_root_digest, 'authority_root_digest')
        self._authority_bound: dict[str, AuthorityBoundPromotion] = {}

    def activate(self, decision: PromotionDecision) -> PromotionRegistryEvent:
        raise TypeError('release registry requires activate_verified with AuthorityBoundPromotion')

    def activate_verified(self, envelope: AuthorityBoundPromotion) -> PromotionRegistryEvent:
        if not isinstance(envelope, AuthorityBoundPromotion):
            raise TypeError('envelope must be AuthorityBoundPromotion')
        if envelope.authority_root_digest != self.authority_root_digest:
            raise ValueError('promotion envelope authority root is not trusted by registry')
        decision = envelope.decision
        if not decision.promoted:
            raise ValueError('release registry activation requires an accepted promotion')
        existing = self._authority_bound.get(decision.structural_class_digest)
        if existing is not None and existing.envelope_digest != envelope.envelope_digest:
            raise ValueError('structural scope already has a different authority-bound promotion')
        event = super().activate(decision)
        self._authority_bound[decision.structural_class_digest] = envelope
        return event

    def is_authorized(
        self,
        structural_class_digest: str,
        *,
        decision_digest: str,
        artifact_digest: str,
    ) -> bool:
        envelope = self._authority_bound.get(str(structural_class_digest).strip().lower())
        if envelope is None:
            return False
        active = super().active_for(structural_class_digest)
        return bool(
            active is not None
            and active.decision_digest == decision_digest
            and active.candidate_artifact_digest == artifact_digest
            and envelope.decision.decision_digest == decision_digest
            and envelope.decision.candidate_artifact_digest == artifact_digest
            and envelope.authority_root_digest == self.authority_root_digest
        )

    def rollback(
        self,
        structural_class_digest: str,
        *,
        rollback_identity: str,
        expected_decision_digest: str,
    ) -> PromotionRegistryEvent:
        event = super().rollback(
            structural_class_digest,
            rollback_identity=rollback_identity,
            expected_decision_digest=expected_decision_digest,
        )
        self._authority_bound.pop(str(structural_class_digest).strip().lower(), None)
        return event

    def audit(self) -> bool:
        if not super().audit():
            return False
        for scope, envelope in self._authority_bound.items():
            active = super().active_for(scope)
            if active is None:
                return False
            if not self.is_authorized(
                scope,
                decision_digest=active.decision_digest,
                artifact_digest=active.candidate_artifact_digest,
            ):
                return False
            if envelope.attestation.authority_root_digest != self.authority_root_digest:
                return False
        return True


__all__ = [
    'HostedVerifierAttestation',
    'AuthorityBoundPromotion',
    'PromotionEvidenceAuthority',
    'AuthorityBoundPromotionRegistry',
]
