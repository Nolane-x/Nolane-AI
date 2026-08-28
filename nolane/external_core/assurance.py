from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.external_core.artifacts import ArtifactStore
from nolane.external_core.assurance_evidence import AssuranceEvidence, AssuranceEvidenceLedger, AssuranceSubject, ChallengeCase
from nolane.external_core.assurance_profiles import AssuranceDomain, AssuranceProfileRegistry
from nolane.organization.authority import AuthorityGraph
from nolane.organization.events import EventLedger
from nolane.memory.skills import SkillEvolutionEngine, SkillRecord
from nolane.organization.identity import AgentRegistry
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.verification import PromotionReceipt, VerificationAuthority

COMPONENT_ID = "external.assurance"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.assurance"


class AssuranceDisposition(str, Enum):
    PENDING = 'pending'
    VERIFIED = 'verified'
    REJECTED = 'rejected'
    OVERRIDDEN = 'overridden'


@dataclass(frozen=True, slots=True)
class AssurancePolicy:
    policy_class: str
    required_domains: tuple[AssuranceDomain, ...]
    blocking: bool


_POLICIES: dict[str, AssurancePolicy] = {
    'code-change': AssurancePolicy(
        'code-change',
        (AssuranceDomain.UNIT_PROPERTY, AssuranceDomain.INTEGRATION_E2E, AssuranceDomain.FUZZ_REGRESSION),
        False,
    ),
    'acceptance-critical': AssurancePolicy(
        'acceptance-critical',
        (
            AssuranceDomain.UNIT_PROPERTY, AssuranceDomain.INTEGRATION_E2E,
            AssuranceDomain.SPEC_ACCEPTANCE, AssuranceDomain.FUZZ_REGRESSION,
        ),
        True,
    ),
    'security-sensitive': AssurancePolicy(
        'security-sensitive',
        (
            AssuranceDomain.UNIT_PROPERTY, AssuranceDomain.INTEGRATION_E2E,
            AssuranceDomain.SPEC_ACCEPTANCE, AssuranceDomain.FUZZ_REGRESSION,
            AssuranceDomain.THREAT_MODEL, AssuranceDomain.ADVERSARIAL,
        ),
        True,
    ),
    'dependency-change': AssurancePolicy(
        'dependency-change',
        (
            AssuranceDomain.UNIT_PROPERTY, AssuranceDomain.INTEGRATION_E2E,
            AssuranceDomain.SUPPLY_CHAIN, AssuranceDomain.ADVERSARIAL,
        ),
        True,
    ),
    'promotion': AssurancePolicy(
        'promotion',
        (AssuranceDomain.UNIT_PROPERTY, AssuranceDomain.FUZZ_REGRESSION),
        False,
    ),
}

_SECURITY_DOMAINS = {
    AssuranceDomain.THREAT_MODEL,
    AssuranceDomain.SUPPLY_CHAIN,
    AssuranceDomain.ADVERSARIAL,
    AssuranceDomain.CROSS_SECURITY,
}


@dataclass(frozen=True, slots=True)
class BlockingReceipt:
    receipt_id: str
    subject_id: str
    decision_id: str
    authority_block_id: str
    blocker_agent_id: str
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id,
            'subject_id': self.subject_id,
            'decision_id': self.decision_id,
            'authority_block_id': self.authority_block_id,
            'blocker_agent_id': self.blocker_agent_id,
            'reasons': list(self.reasons),
            'evidence_refs': list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'BlockingReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']), subject_id=str(state['subject_id']),
            decision_id=str(state['decision_id']), authority_block_id=str(state['authority_block_id']),
            blocker_agent_id=str(state['blocker_agent_id']),
            reasons=tuple(str(x) for x in state.get('reasons', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('blocking receipt digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class AssuranceDecision:
    decision_id: str
    subject_id: str
    evidence_ids: tuple[str, ...]
    disposition: AssuranceDisposition
    reasons: tuple[str, ...]
    blocking_receipt_id: str | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'decision_id': self.decision_id,
            'subject_id': self.subject_id,
            'evidence_ids': list(self.evidence_ids),
            'disposition': self.disposition.value,
            'reasons': list(self.reasons),
            'blocking_receipt_id': self.blocking_receipt_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'AssuranceDecision':
        row = cls(
            decision_id=str(state['decision_id']), subject_id=str(state['subject_id']),
            evidence_ids=tuple(str(x) for x in state.get('evidence_ids', ())),
            disposition=AssuranceDisposition(str(state['disposition'])),
            reasons=tuple(str(x) for x in state.get('reasons', ())),
            blocking_receipt_id=None if state.get('blocking_receipt_id') is None else str(state['blocking_receipt_id']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('assurance decision digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class AssuranceOverrideReceipt:
    override_id: str
    subject_id: str
    original_decision_id: str
    blocking_receipt_id: str
    authority_override_id: str
    reason: str
    evidence_ids: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'override_id': self.override_id,
            'subject_id': self.subject_id,
            'original_decision_id': self.original_decision_id,
            'blocking_receipt_id': self.blocking_receipt_id,
            'authority_override_id': self.authority_override_id,
            'reason': self.reason,
            'evidence_ids': list(self.evidence_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'AssuranceOverrideReceipt':
        row = cls(
            override_id=str(state['override_id']), subject_id=str(state['subject_id']),
            original_decision_id=str(state['original_decision_id']),
            blocking_receipt_id=str(state['blocking_receipt_id']),
            authority_override_id=str(state['authority_override_id']), reason=str(state['reason']),
            evidence_ids=tuple(str(x) for x in state.get('evidence_ids', ())), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('assurance override receipt digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class PromotionAssuranceReceipt:
    receipt_id: str
    subject_id: str
    evidence_ids: tuple[str, ...]
    predecessor_version: str
    verifier_ids: tuple[str, ...]
    authorized: bool
    reasons: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id,
            'subject_id': self.subject_id,
            'evidence_ids': list(self.evidence_ids),
            'predecessor_version': self.predecessor_version,
            'verifier_ids': list(self.verifier_ids),
            'authorized': self.authorized,
            'reasons': list(self.reasons),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'PromotionAssuranceReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']), subject_id=str(state['subject_id']),
            evidence_ids=tuple(str(x) for x in state.get('evidence_ids', ())),
            predecessor_version=str(state['predecessor_version']),
            verifier_ids=tuple(str(x) for x in state.get('verifier_ids', ())),
            authorized=bool(state['authorized']), reasons=tuple(str(x) for x in state.get('reasons', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('promotion assurance receipt digest mismatch')
        return row


class AssuranceControlPlane:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        ledger: EventLedger,
        authority: AuthorityGraph,
        artifacts: ArtifactStore,
        evolution: SkillEvolutionEngine,
        verification: VerificationAuthority,
        profiles: AssuranceProfileRegistry | None = None,
        evidence: AssuranceEvidenceLedger | None = None,
        decisions: tuple[AssuranceDecision, ...] = (),
        blocks: tuple[BlockingReceipt, ...] = (),
        overrides: tuple[AssuranceOverrideReceipt, ...] = (),
        promotion_receipts: tuple[PromotionAssuranceReceipt, ...] = (),
        decision_counter: int = 0,
        block_counter: int = 0,
        override_counter: int = 0,
        promotion_counter: int = 0,
    ) -> None:
        self.registry = registry
        self.ledger = ledger
        self.authority = authority
        self.artifacts = artifacts
        self.evolution = evolution
        self.verification = verification
        self.profiles = profiles or AssuranceProfileRegistry(registry)
        self.evidence = evidence or AssuranceEvidenceLedger(
            registry=registry, ledger=ledger, profiles=self.profiles,
        )
        self._decisions = list(decisions)
        self._blocks = {row.receipt_id: row for row in blocks}
        self._overrides = list(overrides)
        self._promotion_receipts = {row.receipt_id: row for row in promotion_receipts}
        self._decision_counter = int(decision_counter)
        self._block_counter = int(block_counter)
        self._override_counter = int(override_counter)
        self._promotion_counter = int(promotion_counter)

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    @staticmethod
    def policy(policy_class: str) -> AssurancePolicy:
        try:
            return _POLICIES[str(policy_class)]
        except KeyError as exc:
            raise ValueError(f'unknown assurance policy: {policy_class}') from exc

    def register_subject(
        self,
        *,
        subject_id: str,
        artifact_id: str,
        producer_agent_id: str,
        subject_version: str,
        policy_class: str,
        evidence_refs: tuple[str, ...],
        required_domains: tuple[AssuranceDomain, ...] | None = None,
    ) -> AssuranceSubject:
        artifact = self.artifacts.get(artifact_id)
        if artifact.producer_agent_id != str(producer_agent_id):
            raise ValueError('assurance subject producer does not match artifact producer')
        policy = self.policy(policy_class)
        domains = policy.required_domains if required_domains is None else tuple(AssuranceDomain(x) for x in required_domains)
        return self.evidence.register_subject(
            subject_id=subject_id, artifact_id=artifact_id, producer_agent_id=producer_agent_id,
            subject_version=subject_version, policy_class=policy.policy_class,
            required_domains=domains, evidence_refs=evidence_refs,
        )

    def create_challenge(self, **kwargs) -> ChallengeCase:
        return self.evidence.create_challenge(**kwargs)

    def record_evidence(self, evidence: AssuranceEvidence) -> AssuranceEvidence:
        return self.evidence.record_evidence(evidence)

    def decisions(self) -> tuple[AssuranceDecision, ...]:
        return tuple(self._decisions)

    def get_decision(self, decision_id: str) -> AssuranceDecision:
        for row in self._decisions:
            if row.decision_id == str(decision_id):
                return row
        raise KeyError(f'unknown assurance decision: {decision_id}')

    def blocking_receipt(self, receipt_id: str | None) -> BlockingReceipt:
        if receipt_id is None:
            raise KeyError('blocking receipt id is required')
        try:
            return self._blocks[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f'unknown assurance blocking receipt: {receipt_id}') from exc

    def _selected_evidence(self, subject: AssuranceSubject, evidence_ids: tuple[str, ...]) -> tuple[AssuranceEvidence, ...]:
        rows: list[AssuranceEvidence] = []
        seen: set[str] = set()
        for evidence_id in evidence_ids:
            row = self.evidence.get_evidence(evidence_id)
            if row.subject_id != subject.subject_id or row.subject_version != subject.subject_version:
                raise ValueError('assurance decision evidence targets a different subject revision')
            if row.evidence_id not in seen:
                rows.append(row)
                seen.add(row.evidence_id)
        return tuple(rows)

    @staticmethod
    def _reasons(subject: AssuranceSubject, rows: tuple[AssuranceEvidence, ...]) -> tuple[str, ...]:
        reasons: list[str] = []
        passing_domains = {
            row.domain for row in rows
            if row.passed and row.false_accepts == 0 and row.regressions == 0
        }
        for domain in subject.required_domains:
            if domain not in passing_domains:
                reasons.append(f'missing_{domain.value}')
        if any(not row.passed for row in rows):
            reasons.append('evidence_failed')
        if any(row.false_accepts for row in rows):
            reasons.append('evidence_false_accepts')
        if any(row.regressions for row in rows):
            reasons.append('evidence_regressions')
        return tuple(dict.fromkeys(reasons))

    @staticmethod
    def _blocker(subject: AssuranceSubject, rows: tuple[AssuranceEvidence, ...]) -> str:
        for row in rows:
            if (not row.passed) or row.false_accepts or row.regressions:
                return row.verifier_agent_id
        if any(domain in _SECURITY_DOMAINS for domain in subject.required_domains):
            return 'security.chief'
        return 'verification.chief'

    def assess(self, subject_id: str, *, evidence_ids: tuple[str, ...]) -> AssuranceDecision:
        subject = self.evidence.get_subject(subject_id)
        policy = self.policy(subject.policy_class)
        rows = self._selected_evidence(subject, tuple(str(x) for x in evidence_ids))
        reasons = self._reasons(subject, rows)
        disposition = AssuranceDisposition.REJECTED if reasons else AssuranceDisposition.VERIFIED
        self._decision_counter += 1
        decision_id = f'assurance-decision-{self._decision_counter:08d}'
        blocking_receipt_id: str | None = None
        if disposition is AssuranceDisposition.REJECTED and policy.blocking:
            blocker = self._blocker(subject, rows)
            block = self.authority.record_block(
                subject.artifact_id, blocker,
                reason=';'.join(reasons) if reasons else 'assurance policy rejected subject',
            )
            self._block_counter += 1
            blocking_receipt_id = f'assurance-block-{self._block_counter:08d}'
            block_payload = {
                'receipt_id': blocking_receipt_id,
                'subject_id': subject.subject_id,
                'decision_id': decision_id,
                'authority_block_id': block.block_id,
                'blocker_agent_id': blocker,
                'reasons': list(reasons),
                'evidence_refs': [row.evidence_id for row in rows],
            }
            blocking = BlockingReceipt(
                receipt_id=blocking_receipt_id, subject_id=subject.subject_id,
                decision_id=decision_id, authority_block_id=block.block_id,
                blocker_agent_id=blocker, reasons=reasons,
                evidence_refs=tuple(row.evidence_id for row in rows),
                digest=canonical_digest(block_payload),
            )
            self._blocks[blocking.receipt_id] = blocking
        payload = {
            'decision_id': decision_id,
            'subject_id': subject.subject_id,
            'evidence_ids': [row.evidence_id for row in rows],
            'disposition': disposition.value,
            'reasons': list(reasons),
            'blocking_receipt_id': blocking_receipt_id,
        }
        decision = AssuranceDecision(
            decision_id=decision_id, subject_id=subject.subject_id,
            evidence_ids=tuple(row.evidence_id for row in rows), disposition=disposition,
            reasons=reasons, blocking_receipt_id=blocking_receipt_id,
            digest=canonical_digest(payload),
        )
        self._decisions.append(decision)
        return decision

    def central_override(
        self,
        *,
        subject_id: str,
        decision_id: str,
        reason: str,
        evidence_ids: tuple[str, ...],
    ) -> AssuranceOverrideReceipt:
        if not str(reason).strip() or not evidence_ids:
            raise ValueError('Central assurance override requires explicit reason and evidence')
        subject = self.evidence.get_subject(subject_id)
        decision = self.get_decision(decision_id)
        if decision.subject_id != subject.subject_id:
            raise ValueError('override decision targets a different subject')
        if decision.disposition is not AssuranceDisposition.REJECTED or decision.blocking_receipt_id is None:
            raise PermissionError('only a blocked rejected assurance decision can be overridden')
        blocking = self.blocking_receipt(decision.blocking_receipt_id)
        authority_override = self.authority.central_override(
            artifact_id=subject.artifact_id, reason=str(reason),
            evidence_ids=tuple(str(x) for x in evidence_ids),
        )
        self._override_counter += 1
        override_id = f'assurance-override-{self._override_counter:08d}'
        payload = {
            'override_id': override_id,
            'subject_id': subject.subject_id,
            'original_decision_id': decision.decision_id,
            'blocking_receipt_id': blocking.receipt_id,
            'authority_override_id': authority_override.override_id,
            'reason': str(reason),
            'evidence_ids': [str(x) for x in evidence_ids],
        }
        row = AssuranceOverrideReceipt(
            override_id=override_id, subject_id=subject.subject_id,
            original_decision_id=decision.decision_id, blocking_receipt_id=blocking.receipt_id,
            authority_override_id=authority_override.override_id, reason=str(reason),
            evidence_ids=tuple(str(x) for x in evidence_ids), digest=canonical_digest(payload),
        )
        self._overrides.append(row)
        return row

    def effective_disposition(self, subject_id: str) -> AssuranceDisposition:
        subject = self.evidence.get_subject(subject_id)
        if any(row.subject_id == subject.subject_id for row in self._overrides):
            return AssuranceDisposition.OVERRIDDEN
        for row in reversed(self._decisions):
            if row.subject_id == subject.subject_id:
                return row.disposition
        return AssuranceDisposition.PENDING

    def authorize_promotion(
        self,
        *,
        subject_id: str,
        evidence_ids: tuple[str, ...],
        predecessor_version: str,
    ) -> PromotionAssuranceReceipt:
        subject = self.evidence.get_subject(subject_id)
        if not str(predecessor_version).strip():
            raise ValueError('promotion predecessor version must be explicit')
        rows = self._selected_evidence(subject, tuple(str(x) for x in evidence_ids))
        reasons: list[str] = []
        if subject.policy_class != 'promotion':
            reasons.append('wrong_promotion_policy')
        reasons.extend(self._reasons(subject, rows))
        if not rows or any(not row.heldout_digest.strip() for row in rows):
            reasons.append('missing_heldout_evidence')
        if not any(str(predecessor_version) in row.cross_version_refs for row in rows):
            reasons.append('missing_cross_version_evidence')
        verifier_ids = tuple(sorted({row.verifier_agent_id for row in rows}))
        if len(verifier_ids) < 2:
            reasons.append('insufficient_independent_verifiers')
        reasons = list(dict.fromkeys(reasons))
        self._promotion_counter += 1
        receipt_id = f'assurance-promotion-{self._promotion_counter:08d}'
        payload = {
            'receipt_id': receipt_id, 'subject_id': subject.subject_id,
            'evidence_ids': [row.evidence_id for row in rows],
            'predecessor_version': str(predecessor_version),
            'verifier_ids': list(verifier_ids), 'authorized': not reasons,
            'reasons': reasons,
        }
        row = PromotionAssuranceReceipt(
            receipt_id=receipt_id, subject_id=subject.subject_id,
            evidence_ids=tuple(x.evidence_id for x in rows), predecessor_version=str(predecessor_version),
            verifier_ids=verifier_ids, authorized=not reasons, reasons=tuple(reasons),
            digest=canonical_digest(payload),
        )
        self._promotion_receipts[row.receipt_id] = row
        return row

    def promotion_receipt(self, receipt_id: str) -> PromotionAssuranceReceipt:
        try:
            return self._promotion_receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f'unknown promotion assurance receipt: {receipt_id}') from exc

    def promote_neural_candidate(self, assurance_receipt_id: str, low_level_receipt_id: str) -> PromotionReceipt:
        authorization = self.promotion_receipt(assurance_receipt_id)
        if not authorization.authorized:
            raise PermissionError('production promotion is not assurance-authorized')
        subject = self.evidence.get_subject(authorization.subject_id)
        low_level = self.verification.get_receipt(low_level_receipt_id)
        if low_level.agent_id != subject.producer_agent_id:
            raise ValueError('low-level promotion agent does not match assurance subject producer')
        if low_level.candidate_version != subject.subject_version:
            raise ValueError('low-level promotion version does not match assurance subject version')
        if self.registry.get(low_level.agent_id).neural_version != authorization.predecessor_version:
            raise ValueError('accepted predecessor version changed after assurance authorization')
        return self.verification.promote_candidate(low_level.receipt_id)

    def propose_personal_skill(
        self,
        *,
        agent_id: str,
        name: str,
        body: str,
        object_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> SkillRecord:
        profile = self.profiles.get(agent_id)
        if not object_refs or not evidence_refs:
            raise ValueError('assurance skill candidate requires object and evidence refs')
        return self.evolution.propose(
            owner_agent_id=profile.agent_id, region=profile.region, name=name, body=body,
        )

    def to_state(self) -> dict[str, Any]:
        return {
            'evidence': self.evidence.to_state(),
            'decisions': [row.to_state() for row in self._decisions],
            'blocks': [self._blocks[key].to_state() for key in sorted(self._blocks)],
            'overrides': [row.to_state() for row in self._overrides],
            'promotion_receipts': [self._promotion_receipts[key].to_state() for key in sorted(self._promotion_receipts)],
            'decision_counter': self._decision_counter,
            'block_counter': self._block_counter,
            'override_counter': self._override_counter,
            'promotion_counter': self._promotion_counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        ledger: EventLedger,
        authority: AuthorityGraph,
        artifacts: ArtifactStore,
        evolution: SkillEvolutionEngine,
        verification: VerificationAuthority,
        state: Mapping[str, Any],
    ) -> 'AssuranceControlPlane':
        profiles = AssuranceProfileRegistry.from_state(
            registry, state.get('evidence', {}).get('profiles', {}),
        )
        evidence = AssuranceEvidenceLedger.from_state(
            registry=registry, ledger=ledger, state=state.get('evidence', {}),
        )
        decisions = tuple(AssuranceDecision.from_state(x) for x in state.get('decisions', ()))
        blocks = tuple(BlockingReceipt.from_state(x) for x in state.get('blocks', ()))
        overrides = tuple(AssuranceOverrideReceipt.from_state(x) for x in state.get('overrides', ()))
        promotion_receipts = tuple(PromotionAssuranceReceipt.from_state(x) for x in state.get('promotion_receipts', ()))
        result = cls(
            registry=registry, ledger=ledger, authority=authority, artifacts=artifacts,
            evolution=evolution, verification=verification, profiles=profiles, evidence=evidence,
            decisions=decisions, blocks=blocks, overrides=overrides,
            promotion_receipts=promotion_receipts,
            decision_counter=int(state.get('decision_counter', len(decisions))),
            block_counter=int(state.get('block_counter', len(blocks))),
            override_counter=int(state.get('override_counter', len(overrides))),
            promotion_counter=int(state.get('promotion_counter', len(promotion_receipts))),
        )
        for row in decisions:
            evidence.get_subject(row.subject_id)
            if row.blocking_receipt_id is not None:
                result.blocking_receipt(row.blocking_receipt_id)
        for row in blocks:
            registry.get(row.blocker_agent_id)
            evidence.get_subject(row.subject_id)
        for row in overrides:
            result.get_decision(row.original_decision_id)
            result.blocking_receipt(row.blocking_receipt_id)
        for row in promotion_receipts:
            evidence.get_subject(row.subject_id)
        return result
