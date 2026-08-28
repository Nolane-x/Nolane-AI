from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from nolane.external_core.assurance_profiles import AssuranceDomain, AssuranceProfileRegistry
from nolane.organization.events import EventLedger
from nolane.organization.identity import AgentRegistry
from nolane.core.canonical_digest import canonical_digest


class ChallengeStatus(str, Enum):
    OPEN = 'open'
    FALSIFIED = 'falsified'
    SURVIVED = 'survived'
    INCONCLUSIVE = 'inconclusive'


@dataclass(frozen=True, slots=True)
class AssuranceSubject:
    subject_id: str
    artifact_id: str
    producer_agent_id: str
    subject_version: str
    policy_class: str
    required_domains: tuple[AssuranceDomain, ...]
    evidence_refs: tuple[str, ...]
    registered_epoch: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'subject_id': self.subject_id,
            'artifact_id': self.artifact_id,
            'producer_agent_id': self.producer_agent_id,
            'subject_version': self.subject_version,
            'policy_class': self.policy_class,
            'required_domains': [x.value for x in self.required_domains],
            'evidence_refs': list(self.evidence_refs),
            'registered_epoch': self.registered_epoch,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'AssuranceSubject':
        row = cls(
            subject_id=str(state['subject_id']),
            artifact_id=str(state['artifact_id']),
            producer_agent_id=str(state['producer_agent_id']),
            subject_version=str(state['subject_version']),
            policy_class=str(state['policy_class']),
            required_domains=tuple(AssuranceDomain(str(x)) for x in state.get('required_domains', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            registered_epoch=int(state['registered_epoch']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('assurance subject digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ChallengeCase:
    case_id: str
    subject_id: str
    creator_agent_id: str
    domain: AssuranceDomain
    objective: str
    input_artifact_refs: tuple[str, ...]
    expected_invariant: str
    evidence_refs: tuple[str, ...]
    status: ChallengeStatus
    created_epoch: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'case_id': self.case_id,
            'subject_id': self.subject_id,
            'creator_agent_id': self.creator_agent_id,
            'domain': self.domain.value,
            'objective': self.objective,
            'input_artifact_refs': list(self.input_artifact_refs),
            'expected_invariant': self.expected_invariant,
            'evidence_refs': list(self.evidence_refs),
            'status': self.status.value,
            'created_epoch': self.created_epoch,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ChallengeCase':
        row = cls(
            case_id=str(state['case_id']), subject_id=str(state['subject_id']),
            creator_agent_id=str(state['creator_agent_id']), domain=AssuranceDomain(str(state['domain'])),
            objective=str(state['objective']),
            input_artifact_refs=tuple(str(x) for x in state.get('input_artifact_refs', ())),
            expected_invariant=str(state['expected_invariant']),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            status=ChallengeStatus(str(state.get('status', ChallengeStatus.OPEN.value))),
            created_epoch=int(state['created_epoch']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('challenge case digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class AssuranceEvidence:
    evidence_id: str
    subject_id: str
    subject_version: str
    verifier_agent_id: str
    domain: AssuranceDomain
    passed: bool
    sandbox_digest: str
    observed_epoch: int
    false_accepts: int = 0
    regressions: int = 0
    heldout_digest: str = ''
    cross_version_refs: tuple[str, ...] = ()
    challenge_case_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    digest: str = ''

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (
            self.evidence_id, self.subject_id, self.subject_version,
            self.verifier_agent_id, self.sandbox_digest,
        )):
            raise ValueError('assurance evidence identity/subject/version/verifier/sandbox must be explicit')
        if self.observed_epoch < 0:
            raise ValueError('assurance evidence epoch must be non-negative')
        if self.false_accepts < 0 or self.regressions < 0:
            raise ValueError('assurance evidence counters must be non-negative')
        if not self.evidence_refs:
            raise ValueError('assurance evidence requires evidence refs')
        canonical = canonical_digest(self.payload())
        if self.digest and self.digest != canonical:
            raise ValueError('assurance evidence digest mismatch')
        if not self.digest:
            object.__setattr__(self, 'digest', canonical)

    def payload(self) -> dict[str, Any]:
        return {
            'evidence_id': self.evidence_id,
            'subject_id': self.subject_id,
            'subject_version': self.subject_version,
            'verifier_agent_id': self.verifier_agent_id,
            'domain': AssuranceDomain(self.domain).value,
            'passed': self.passed,
            'sandbox_digest': self.sandbox_digest,
            'observed_epoch': self.observed_epoch,
            'false_accepts': self.false_accepts,
            'regressions': self.regressions,
            'heldout_digest': self.heldout_digest,
            'cross_version_refs': list(self.cross_version_refs),
            'challenge_case_refs': list(self.challenge_case_refs),
            'evidence_refs': list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'AssuranceEvidence':
        return cls(
            evidence_id=str(state['evidence_id']), subject_id=str(state['subject_id']),
            subject_version=str(state['subject_version']), verifier_agent_id=str(state['verifier_agent_id']),
            domain=AssuranceDomain(str(state['domain'])), passed=bool(state['passed']),
            sandbox_digest=str(state['sandbox_digest']), observed_epoch=int(state['observed_epoch']),
            false_accepts=int(state.get('false_accepts', 0)), regressions=int(state.get('regressions', 0)),
            heldout_digest=str(state.get('heldout_digest', '')),
            cross_version_refs=tuple(str(x) for x in state.get('cross_version_refs', ())),
            challenge_case_refs=tuple(str(x) for x in state.get('challenge_case_refs', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            digest=str(state['digest']),
        )


class AssuranceEvidenceLedger:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        ledger: EventLedger,
        profiles: AssuranceProfileRegistry | None = None,
    ) -> None:
        self.registry = registry
        self.ledger = ledger
        self.profiles = profiles or AssuranceProfileRegistry(registry)
        self._subjects: dict[str, AssuranceSubject] = {}
        self._challenges: dict[str, ChallengeCase] = {}
        self._evidence: dict[str, AssuranceEvidence] = {}
        self._challenge_counter = 0
        self.current_epoch = 0

    def subjects(self) -> tuple[AssuranceSubject, ...]:
        return tuple(self._subjects[key] for key in sorted(self._subjects))

    def challenges(self) -> tuple[ChallengeCase, ...]:
        return tuple(self._challenges[key] for key in sorted(self._challenges))

    def evidence_records(self) -> tuple[AssuranceEvidence, ...]:
        return tuple(self._evidence[key] for key in sorted(self._evidence))

    def get_subject(self, subject_id: str) -> AssuranceSubject:
        try:
            return self._subjects[str(subject_id)]
        except KeyError as exc:
            raise KeyError(f'unknown assurance subject: {subject_id}') from exc

    def get_challenge(self, case_id: str) -> ChallengeCase:
        try:
            return self._challenges[str(case_id)]
        except KeyError as exc:
            raise KeyError(f'unknown assurance challenge: {case_id}') from exc

    def get_evidence(self, evidence_id: str) -> AssuranceEvidence:
        try:
            return self._evidence[str(evidence_id)]
        except KeyError as exc:
            raise KeyError(f'unknown assurance evidence: {evidence_id}') from exc

    def register_subject(
        self,
        *,
        subject_id: str,
        artifact_id: str,
        producer_agent_id: str,
        subject_version: str,
        policy_class: str,
        required_domains: tuple[AssuranceDomain, ...],
        evidence_refs: tuple[str, ...],
    ) -> AssuranceSubject:
        if not all(str(x).strip() for x in (
            subject_id, artifact_id, producer_agent_id, subject_version, policy_class,
        )):
            raise ValueError('assurance subject identity/artifact/producer/version/policy must be explicit')
        if not required_domains or not evidence_refs:
            raise ValueError('assurance subject requires domains and evidence refs')
        self.registry.get(producer_agent_id)
        existing = self._subjects.get(str(subject_id))
        if existing is not None:
            if (
                existing.artifact_id == str(artifact_id)
                and existing.producer_agent_id == str(producer_agent_id)
                and existing.subject_version == str(subject_version)
                and existing.policy_class == str(policy_class)
                and existing.required_domains == tuple(AssuranceDomain(x) for x in required_domains)
                and existing.evidence_refs == tuple(str(x) for x in evidence_refs)
            ):
                return existing
            raise ValueError('assurance subject id cannot be rebound')
        self.current_epoch += 1
        payload = {
            'subject_id': str(subject_id), 'artifact_id': str(artifact_id),
            'producer_agent_id': str(producer_agent_id), 'subject_version': str(subject_version),
            'policy_class': str(policy_class),
            'required_domains': [AssuranceDomain(x).value for x in required_domains],
            'evidence_refs': [str(x) for x in evidence_refs],
            'registered_epoch': self.current_epoch,
        }
        row = AssuranceSubject(
            subject_id=payload['subject_id'], artifact_id=payload['artifact_id'],
            producer_agent_id=payload['producer_agent_id'], subject_version=payload['subject_version'],
            policy_class=payload['policy_class'],
            required_domains=tuple(AssuranceDomain(x) for x in required_domains),
            evidence_refs=tuple(payload['evidence_refs']), registered_epoch=self.current_epoch,
            digest=canonical_digest(payload),
        )
        self._subjects[row.subject_id] = row
        return row

    def create_challenge(
        self,
        *,
        subject_id: str,
        creator_agent_id: str,
        domain: AssuranceDomain,
        objective: str,
        input_artifact_refs: tuple[str, ...],
        expected_invariant: str,
        evidence_refs: tuple[str, ...],
    ) -> ChallengeCase:
        subject = self.get_subject(subject_id)
        profile = self.profiles.get(creator_agent_id)
        domain = AssuranceDomain(domain)
        if domain not in profile.domains:
            raise PermissionError('challenge domain is outside creator assurance authority')
        if not str(objective).strip() or not str(expected_invariant).strip():
            raise ValueError('challenge objective and invariant must be explicit')
        if not input_artifact_refs or not evidence_refs:
            raise ValueError('challenge requires input artifacts and evidence refs')
        self.current_epoch += 1
        self._challenge_counter += 1
        case_id = f'assurance-case-{self._challenge_counter:08d}'
        payload = {
            'case_id': case_id, 'subject_id': subject.subject_id,
            'creator_agent_id': str(creator_agent_id), 'domain': domain.value,
            'objective': str(objective), 'input_artifact_refs': [str(x) for x in input_artifact_refs],
            'expected_invariant': str(expected_invariant), 'evidence_refs': [str(x) for x in evidence_refs],
            'status': ChallengeStatus.OPEN.value, 'created_epoch': self.current_epoch,
        }
        row = ChallengeCase(
            case_id=case_id, subject_id=subject.subject_id, creator_agent_id=str(creator_agent_id),
            domain=domain, objective=str(objective),
            input_artifact_refs=tuple(payload['input_artifact_refs']), expected_invariant=str(expected_invariant),
            evidence_refs=tuple(payload['evidence_refs']), status=ChallengeStatus.OPEN,
            created_epoch=self.current_epoch, digest=canonical_digest(payload),
        )
        self._challenges[row.case_id] = row
        return row

    def set_challenge_status(self, case_id: str, status: ChallengeStatus) -> ChallengeCase:
        old = self.get_challenge(case_id)
        status = ChallengeStatus(status)
        payload = {**old.payload(), 'status': status.value}
        row = replace(old, status=status, digest=canonical_digest(payload))
        self._challenges[row.case_id] = row
        self.current_epoch += 1
        return row

    def record_evidence(self, evidence: AssuranceEvidence) -> AssuranceEvidence:
        existing = self._evidence.get(evidence.evidence_id)
        if existing is not None:
            if existing == evidence:
                return existing
            raise ValueError('assurance evidence id cannot be rebound')
        subject = self.get_subject(evidence.subject_id)
        if evidence.subject_version != subject.subject_version:
            raise ValueError('assurance evidence targets stale subject version')
        if evidence.observed_epoch < subject.registered_epoch:
            raise ValueError('assurance evidence predates subject registration')
        if evidence.observed_epoch > self.current_epoch:
            raise ValueError('assurance evidence observation epoch is in the future')
        profile = self.profiles.get(evidence.verifier_agent_id)
        if evidence.verifier_agent_id == subject.producer_agent_id:
            raise PermissionError('producer self-verification is forbidden')
        if AssuranceDomain(evidence.domain) not in profile.domains:
            raise PermissionError('verifier is not authorized for assurance domain')
        for case_id in evidence.challenge_case_refs:
            challenge = self.get_challenge(case_id)
            if challenge.subject_id != subject.subject_id:
                raise ValueError('challenge case belongs to different assurance subject')
        self._evidence[evidence.evidence_id] = evidence
        self.current_epoch += 1
        return evidence

    def to_state(self) -> dict[str, Any]:
        return {
            'profiles': self.profiles.to_state(),
            'subjects': [row.to_state() for row in self.subjects()],
            'challenges': [row.to_state() for row in self.challenges()],
            'evidence': [row.to_state() for row in self.evidence_records()],
            'challenge_counter': self._challenge_counter,
            'current_epoch': self.current_epoch,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        ledger: EventLedger,
        state: Mapping[str, Any],
    ) -> 'AssuranceEvidenceLedger':
        profiles = AssuranceProfileRegistry.from_state(registry, state.get('profiles', {}))
        result = cls(registry=registry, ledger=ledger, profiles=profiles)
        for value in state.get('subjects', ()):
            row = AssuranceSubject.from_state(value)
            if row.subject_id in result._subjects:
                raise ValueError('duplicate assurance subject in snapshot')
            registry.get(row.producer_agent_id)
            result._subjects[row.subject_id] = row
        for value in state.get('challenges', ()):
            row = ChallengeCase.from_state(value)
            if row.case_id in result._challenges:
                raise ValueError('duplicate assurance challenge in snapshot')
            result.get_subject(row.subject_id)
            result.profiles.get(row.creator_agent_id)
            result._challenges[row.case_id] = row
        for value in state.get('evidence', ()):
            row = AssuranceEvidence.from_state(value)
            if row.evidence_id in result._evidence:
                raise ValueError('duplicate assurance evidence in snapshot')
            result.get_subject(row.subject_id)
            result.profiles.get(row.verifier_agent_id)
            result._evidence[row.evidence_id] = row
        result._challenge_counter = int(state.get('challenge_counter', len(result._challenges)))
        result.current_epoch = int(state.get('current_epoch', 0))
        if result.current_epoch < max(
            [0]
            + [row.registered_epoch for row in result._subjects.values()]
            + [row.created_epoch for row in result._challenges.values()]
            + [row.observed_epoch for row in result._evidence.values()]
        ):
            raise ValueError('assurance epoch counter is behind persisted history')
        return result
