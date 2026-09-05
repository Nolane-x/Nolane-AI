from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.external_core.artifacts import ArtifactStore
from nolane.external_core.assurance import AssuranceControlPlane, AssuranceDisposition
from nolane.memory.skills import SkillEvolutionEngine, SkillRecord
from nolane.organization.identity import AgentRegistry
from nolane.external_core.research_profiles import ResearchDomain, ResearchProfileRegistry
from nolane.external_core.research_provenance import (
    ClaimDisposition,
    EvidenceMode,
    ResearchProvenanceLedger,
)
from nolane.core.canonical_digest import canonical_digest, canonical_json


class ResearchHandoffDisposition(str, Enum):
    INFORMATIVE = 'informative'
    AUTHORIZED = 'authorized'
    BLOCKED = 'blocked'


class CurrentResearchHandoffDisposition(str, Enum):
    """Current assessment of a historical research handoff.

    This disposition never creates authority. AUTHORIZED means the existing
    handoff still satisfies every current binding that originally made it
    authorizing; UNKNOWN means required current evidence cannot be established.
    """

    INFORMATIVE = 'informative'
    AUTHORIZED = 'authorized'
    BLOCKED = 'blocked'
    UNKNOWN = 'unknown'


@dataclass(frozen=True, slots=True)
class ResearchSynthesis:
    synthesis_id: str
    producer_agent_id: str
    title: str
    finding_ids: tuple[str, ...]
    claim_keys: tuple[str, ...]
    source_ids: tuple[str, ...]
    evidence_modes: tuple[EvidenceMode, ...]
    domains: tuple[ResearchDomain, ...]
    conclusion: str
    limitations: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    reasons: tuple[str, ...]
    shareable: bool
    artifact_id: str
    created_epoch: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'synthesis_id': self.synthesis_id,
            'producer_agent_id': self.producer_agent_id,
            'title': self.title,
            'finding_ids': list(self.finding_ids),
            'claim_keys': list(self.claim_keys),
            'source_ids': list(self.source_ids),
            'evidence_modes': [x.value for x in self.evidence_modes],
            'domains': [x.value for x in self.domains],
            'conclusion': self.conclusion,
            'limitations': list(self.limitations),
            'evidence_refs': list(self.evidence_refs),
            'reasons': list(self.reasons),
            'shareable': self.shareable,
            'artifact_id': self.artifact_id,
            'created_epoch': self.created_epoch,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ResearchSynthesis':
        row = cls(
            synthesis_id=str(state['synthesis_id']),
            producer_agent_id=str(state['producer_agent_id']),
            title=str(state['title']),
            finding_ids=tuple(str(x) for x in state.get('finding_ids', ())),
            claim_keys=tuple(str(x) for x in state.get('claim_keys', ())),
            source_ids=tuple(str(x) for x in state.get('source_ids', ())),
            evidence_modes=tuple(EvidenceMode(str(x)) for x in state.get('evidence_modes', ())),
            domains=tuple(ResearchDomain(str(x)) for x in state.get('domains', ())),
            conclusion=str(state['conclusion']),
            limitations=tuple(str(x) for x in state.get('limitations', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            reasons=tuple(str(x) for x in state.get('reasons', ())),
            shareable=bool(state['shareable']),
            artifact_id=str(state['artifact_id']),
            created_epoch=int(state['created_epoch']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('research synthesis digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ResearchHandoff:
    handoff_id: str
    synthesis_id: str
    synthesis_artifact_id: str
    target_agent_id: str
    target_region: str
    purpose: str
    authorizing: bool
    assurance_subject_id: str | None
    assurance_disposition: AssuranceDisposition | None
    disposition: ResearchHandoffDisposition
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'handoff_id': self.handoff_id,
            'synthesis_id': self.synthesis_id,
            'synthesis_artifact_id': self.synthesis_artifact_id,
            'target_agent_id': self.target_agent_id,
            'target_region': self.target_region,
            'purpose': self.purpose,
            'authorizing': self.authorizing,
            'assurance_subject_id': self.assurance_subject_id,
            'assurance_disposition': None if self.assurance_disposition is None else self.assurance_disposition.value,
            'disposition': self.disposition.value,
            'reasons': list(self.reasons),
            'evidence_refs': list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ResearchHandoff':
        assurance_value = state.get('assurance_disposition')
        row = cls(
            handoff_id=str(state['handoff_id']),
            synthesis_id=str(state['synthesis_id']),
            synthesis_artifact_id=str(state['synthesis_artifact_id']),
            target_agent_id=str(state['target_agent_id']),
            target_region=str(state['target_region']),
            purpose=str(state['purpose']),
            authorizing=bool(state['authorizing']),
            assurance_subject_id=None if state.get('assurance_subject_id') is None else str(state['assurance_subject_id']),
            assurance_disposition=None if assurance_value is None else AssuranceDisposition(str(assurance_value)),
            disposition=ResearchHandoffDisposition(str(state['disposition'])),
            reasons=tuple(str(x) for x in state.get('reasons', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('research handoff digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class CurrentResearchHandoffAssessment:
    handoff_id: str
    historical_handoff_digest: str
    synthesis_id: str
    synthesis_digest: str
    artifact_id: str
    artifact_digest: str | None
    provenance_digest: str
    assurance_disposition: AssuranceDisposition | None
    disposition: CurrentResearchHandoffDisposition
    reasons: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'handoff_id': self.handoff_id,
            'historical_handoff_digest': self.historical_handoff_digest,
            'synthesis_id': self.synthesis_id,
            'synthesis_digest': self.synthesis_digest,
            'artifact_id': self.artifact_id,
            'artifact_digest': self.artifact_digest,
            'provenance_digest': self.provenance_digest,
            'assurance_disposition': None if self.assurance_disposition is None else self.assurance_disposition.value,
            'disposition': self.disposition.value,
            'reasons': list(self.reasons),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}


_ENGINEERING_TARGET_REGIONS = {'planning-program', 'architecture-system', 'core-coding'}


class ResearchControlPlane:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        artifacts: ArtifactStore,
        evolution: SkillEvolutionEngine,
        assurance: AssuranceControlPlane,
        profiles: ResearchProfileRegistry | None = None,
        provenance: ResearchProvenanceLedger | None = None,
        syntheses: tuple[ResearchSynthesis, ...] = (),
        handoffs: tuple[ResearchHandoff, ...] = (),
        handoff_counter: int = 0,
    ) -> None:
        self.registry = registry
        self.artifacts = artifacts
        self.evolution = evolution
        self.assurance = assurance
        self.profiles = profiles or ResearchProfileRegistry(registry)
        self.provenance = provenance or ResearchProvenanceLedger(registry=registry, profiles=self.profiles)
        self._syntheses = {row.synthesis_id: row for row in syntheses}
        self._handoffs = {row.handoff_id: row for row in handoffs}
        self._handoff_counter = int(handoff_counter)

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def synthesis(self, synthesis_id: str) -> ResearchSynthesis:
        try:
            return self._syntheses[str(synthesis_id)]
        except KeyError as exc:
            raise KeyError(f'unknown research synthesis: {synthesis_id}') from exc

    def handoff(self, handoff_id: str) -> ResearchHandoff:
        try:
            return self._handoffs[str(handoff_id)]
        except KeyError as exc:
            raise KeyError(f'unknown research handoff: {handoff_id}') from exc

    def synthesize(
        self,
        *,
        synthesis_id: str,
        producer_agent_id: str,
        title: str,
        finding_ids: tuple[str, ...],
        limitations: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> ResearchSynthesis:
        if not all(str(x).strip() for x in (synthesis_id, producer_agent_id, title)):
            raise ValueError('research synthesis identity, producer and title must be explicit')
        profile = self.profiles.get(producer_agent_id)
        findings = tuple(self.provenance.get_finding(str(x)) for x in finding_ids)
        if not findings or not limitations or not evidence_refs:
            raise ValueError('research synthesis requires findings, limitations and evidence refs')
        if profile.agent_id != 'research.chief' and any(row.domain not in profile.domains for row in findings):
            raise PermissionError('research synthesis producer cannot synthesize outside assigned domains')

        claim_keys = tuple(sorted({row.claim_key for row in findings}))
        source_ids = tuple(sorted({source_id for row in findings for source_id in row.source_ids}))
        modes = tuple(sorted({self.provenance.get_source(x).mode for x in source_ids}, key=lambda x: x.value))
        domains = tuple(sorted({row.domain for row in findings}, key=lambda x: x.value))
        reasons: list[str] = []
        if any(not self.provenance.is_finding_fresh(row.finding_id) for row in findings):
            reasons.append('stale_finding')
        for claim_key in claim_keys:
            assessment = self.provenance.assess_claim(claim_key)
            if assessment.disposition is ClaimDisposition.CONTRADICTED:
                reasons.append('unresolved_contradiction')
            elif assessment.disposition is ClaimDisposition.STALE:
                reasons.append('stale_finding')
        reasons = list(dict.fromkeys(reasons))
        conclusion = '; '.join(row.statement for row in findings)
        core_payload = {
            'synthesis_id': str(synthesis_id),
            'producer_agent_id': profile.agent_id,
            'title': str(title),
            'finding_ids': [row.finding_id for row in findings],
            'claim_keys': list(claim_keys),
            'source_ids': list(source_ids),
            'evidence_modes': [x.value for x in modes],
            'domains': [x.value for x in domains],
            'conclusion': conclusion,
            'limitations': [str(x) for x in limitations],
            'evidence_refs': [str(x) for x in evidence_refs],
            'reasons': reasons,
            'shareable': not reasons,
            'created_epoch': self.provenance.current_epoch,
        }
        artifact = self.artifacts.put(
            kind='research-synthesis',
            producer_agent_id=profile.agent_id,
            content=canonical_json(core_payload),
            evidence_refs=tuple(str(x) for x in evidence_refs),
            metadata={
                'synthesis_id': str(synthesis_id),
                'shareable': not reasons,
                'source_modes': [x.value for x in modes],
            },
        )
        payload = {**core_payload, 'artifact_id': artifact.artifact_id}
        row = ResearchSynthesis(
            synthesis_id=str(synthesis_id), producer_agent_id=profile.agent_id, title=str(title),
            finding_ids=tuple(x.finding_id for x in findings), claim_keys=claim_keys, source_ids=source_ids,
            evidence_modes=modes, domains=domains, conclusion=conclusion,
            limitations=tuple(str(x) for x in limitations), evidence_refs=tuple(str(x) for x in evidence_refs),
            reasons=tuple(reasons), shareable=not reasons, artifact_id=artifact.artifact_id,
            created_epoch=self.provenance.current_epoch, digest=canonical_digest(payload),
        )
        existing = self._syntheses.get(row.synthesis_id)
        if existing is not None:
            if existing != row:
                raise ValueError('research synthesis id cannot be rebound')
            return existing
        self._syntheses[row.synthesis_id] = row
        return row

    def create_handoff(
        self,
        *,
        synthesis_id: str,
        target_agent_id: str,
        purpose: str,
        authorizing: bool,
        assurance_subject_id: str | None,
        evidence_refs: tuple[str, ...],
    ) -> ResearchHandoff:
        synthesis = self.synthesis(synthesis_id)
        target = self.registry.get(target_agent_id)
        if target.region not in _ENGINEERING_TARGET_REGIONS:
            raise PermissionError('research engineering handoff target must be Planning, Architecture or Coding')
        if not str(purpose).strip() or not evidence_refs:
            raise ValueError('research handoff requires purpose and evidence refs')
        reasons: list[str] = []
        assurance_disposition: AssuranceDisposition | None = None
        if not synthesis.shareable:
            reasons.append('synthesis_not_shareable')
        if authorizing:
            if assurance_subject_id is None:
                reasons.append('missing_assurance_subject')
            else:
                subject = self.assurance.evidence.get_subject(assurance_subject_id)
                if subject.artifact_id != synthesis.artifact_id:
                    raise ValueError('research assurance subject does not target synthesis artifact')
                assurance_disposition = self.assurance.effective_disposition(subject.subject_id)
                if assurance_disposition is not AssuranceDisposition.VERIFIED:
                    reasons.append('assurance_not_independently_verified')
        elif assurance_subject_id is not None:
            subject = self.assurance.evidence.get_subject(assurance_subject_id)
            if subject.artifact_id != synthesis.artifact_id:
                raise ValueError('informative research assurance subject targets different artifact')
            assurance_disposition = self.assurance.effective_disposition(subject.subject_id)

        if reasons:
            disposition = ResearchHandoffDisposition.BLOCKED
        elif authorizing:
            disposition = ResearchHandoffDisposition.AUTHORIZED
        else:
            disposition = ResearchHandoffDisposition.INFORMATIVE
        self._handoff_counter += 1
        handoff_id = f'research-handoff-{self._handoff_counter:08d}'
        evidence = tuple(str(x) for x in evidence_refs)
        payload = {
            'handoff_id': handoff_id,
            'synthesis_id': synthesis.synthesis_id,
            'synthesis_artifact_id': synthesis.artifact_id,
            'target_agent_id': target.agent_id,
            'target_region': target.region,
            'purpose': str(purpose),
            'authorizing': bool(authorizing),
            'assurance_subject_id': None if assurance_subject_id is None else str(assurance_subject_id),
            'assurance_disposition': None if assurance_disposition is None else assurance_disposition.value,
            'disposition': disposition.value,
            'reasons': reasons,
            'evidence_refs': list(evidence),
        }
        row = ResearchHandoff(
            handoff_id=handoff_id, synthesis_id=synthesis.synthesis_id,
            synthesis_artifact_id=synthesis.artifact_id, target_agent_id=target.agent_id,
            target_region=target.region, purpose=str(purpose), authorizing=bool(authorizing),
            assurance_subject_id=None if assurance_subject_id is None else str(assurance_subject_id),
            assurance_disposition=assurance_disposition, disposition=disposition,
            reasons=tuple(reasons), evidence_refs=evidence, digest=canonical_digest(payload),
        )
        self._handoffs[row.handoff_id] = row
        return row

    def assess_current_handoff(self, handoff_id: str) -> CurrentResearchHandoffAssessment:
        """Revalidate a historical handoff against current evidence and authority.

        Historical AUTHORIZED is not durable authority. Current authorization is
        preserved only when the synthesis artifact still has exact integrity,
        the underlying research findings/claims are current, and the Assurance
        subject remains independently VERIFIED for the exact synthesis artifact.
        """

        handoff = self.handoff(handoff_id)
        synthesis = self.synthesis(handoff.synthesis_id)
        blocking: list[str] = []
        unknown: list[str] = []
        current_assurance: AssuranceDisposition | None = None
        artifact_digest: str | None = None

        if handoff.synthesis_artifact_id != synthesis.artifact_id:
            blocking.append('handoff_synthesis_artifact_mismatch')
        if handoff.disposition is ResearchHandoffDisposition.BLOCKED:
            blocking.append('historical_handoff_blocked')
        if not synthesis.shareable:
            blocking.append('synthesis_not_shareable')

        try:
            artifact = self.artifacts.get(synthesis.artifact_id)
        except KeyError:
            unknown.append('synthesis_artifact_unavailable')
        else:
            artifact_digest = artifact.digest
            if not _legacy_artifact_integrity_is_current(artifact):
                blocking.append('artifact_integrity_mismatch')
            if artifact.kind != 'research-synthesis' or artifact.producer_agent_id != synthesis.producer_agent_id:
                blocking.append('artifact_provenance_mismatch')
            expected_content = canonical_json(_synthesis_core_payload(synthesis))
            if artifact.content != expected_content:
                blocking.append('artifact_integrity_mismatch')
            try:
                metadata = artifact.metadata
            except (TypeError, ValueError):
                blocking.append('artifact_integrity_mismatch')
            else:
                if metadata.get('synthesis_id') != synthesis.synthesis_id:
                    blocking.append('artifact_synthesis_binding_mismatch')
                if metadata.get('shareable') is not synthesis.shareable:
                    blocking.append('artifact_synthesis_binding_mismatch')
            if tuple(sorted(artifact.evidence_refs)) != tuple(sorted(set(synthesis.evidence_refs))):
                blocking.append('artifact_evidence_binding_mismatch')

        try:
            for finding_id in synthesis.finding_ids:
                if not self.provenance.is_finding_fresh(finding_id):
                    blocking.append('stale_finding')
            for claim_key in synthesis.claim_keys:
                assessment = self.provenance.assess_claim(claim_key)
                if assessment.disposition is ClaimDisposition.CONTRADICTED:
                    blocking.append('unresolved_contradiction')
                elif assessment.disposition is ClaimDisposition.STALE:
                    blocking.append('stale_finding')
                elif assessment.disposition is ClaimDisposition.UNKNOWN:
                    unknown.append('claim_currentness_unknown')
        except KeyError:
            unknown.append('research_basis_unavailable')

        if handoff.authorizing:
            if handoff.assurance_subject_id is None:
                blocking.append('missing_assurance_subject')
            else:
                try:
                    subject = self.assurance.evidence.get_subject(handoff.assurance_subject_id)
                except KeyError:
                    unknown.append('assurance_subject_unavailable')
                else:
                    if subject.artifact_id != synthesis.artifact_id:
                        blocking.append('assurance_subject_artifact_mismatch')
                    try:
                        current_assurance = self.assurance.effective_disposition(subject.subject_id)
                    except KeyError:
                        unknown.append('assurance_currentness_unavailable')
                    else:
                        if current_assurance is AssuranceDisposition.PENDING:
                            unknown.append('assurance_currentness_unresolved')
                        elif current_assurance is not AssuranceDisposition.VERIFIED:
                            blocking.append('assurance_not_currently_verified')
        elif handoff.assurance_subject_id is not None:
            try:
                subject = self.assurance.evidence.get_subject(handoff.assurance_subject_id)
                if subject.artifact_id != synthesis.artifact_id:
                    blocking.append('assurance_subject_artifact_mismatch')
                else:
                    current_assurance = self.assurance.effective_disposition(subject.subject_id)
            except KeyError:
                unknown.append('assurance_subject_unavailable')

        if blocking:
            disposition = CurrentResearchHandoffDisposition.BLOCKED
            reasons = tuple(dict.fromkeys(blocking + unknown))
        elif unknown:
            disposition = CurrentResearchHandoffDisposition.UNKNOWN
            reasons = tuple(dict.fromkeys(unknown))
        elif handoff.authorizing:
            disposition = CurrentResearchHandoffDisposition.AUTHORIZED
            reasons = ()
        else:
            disposition = CurrentResearchHandoffDisposition.INFORMATIVE
            reasons = ()

        provenance_digest = str(getattr(self.provenance, 'digest', ''))
        payload = {
            'handoff_id': handoff.handoff_id,
            'historical_handoff_digest': handoff.digest,
            'synthesis_id': synthesis.synthesis_id,
            'synthesis_digest': synthesis.digest,
            'artifact_id': synthesis.artifact_id,
            'artifact_digest': artifact_digest,
            'provenance_digest': provenance_digest,
            'assurance_disposition': None if current_assurance is None else current_assurance.value,
            'disposition': disposition.value,
            'reasons': list(reasons),
        }
        return CurrentResearchHandoffAssessment(
            handoff_id=handoff.handoff_id,
            historical_handoff_digest=handoff.digest,
            synthesis_id=synthesis.synthesis_id,
            synthesis_digest=synthesis.digest,
            artifact_id=synthesis.artifact_id,
            artifact_digest=artifact_digest,
            provenance_digest=provenance_digest,
            assurance_disposition=current_assurance,
            disposition=disposition,
            reasons=reasons,
            digest=canonical_digest(payload),
        )

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
            raise ValueError('research skill candidate requires object and evidence refs')
        return self.evolution.propose(
            owner_agent_id=profile.agent_id,
            region=profile.region,
            name=name,
            body=body,
        )

    def to_state(self) -> dict[str, Any]:
        return {
            'provenance': self.provenance.to_state(),
            'syntheses': [self._syntheses[key].to_state() for key in sorted(self._syntheses)],
            'handoffs': [self._handoffs[key].to_state() for key in sorted(self._handoffs)],
            'handoff_counter': self._handoff_counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        artifacts: ArtifactStore,
        evolution: SkillEvolutionEngine,
        assurance: AssuranceControlPlane,
        state: Mapping[str, Any],
    ) -> 'ResearchControlPlane':
        provenance = ResearchProvenanceLedger.from_state(
            registry=registry,
            state=state.get('provenance', {}),
        )
        profiles = provenance.profiles
        syntheses = tuple(ResearchSynthesis.from_state(x) for x in state.get('syntheses', ()))
        handoffs = tuple(ResearchHandoff.from_state(x) for x in state.get('handoffs', ()))
        result = cls(
            registry=registry, artifacts=artifacts, evolution=evolution, assurance=assurance,
            profiles=profiles, provenance=provenance, syntheses=syntheses, handoffs=handoffs,
            handoff_counter=int(state.get('handoff_counter', len(handoffs))),
        )
        if len(result._syntheses) != len(syntheses) or len(result._handoffs) != len(handoffs):
            raise ValueError('duplicate research synthesis/handoff id in serialized state')
        for synthesis in syntheses:
            profile = profiles.get(synthesis.producer_agent_id)
            if profile.agent_id != synthesis.producer_agent_id:
                raise PermissionError('serialized research synthesis has invalid producer')
            artifact = artifacts.get(synthesis.artifact_id)
            if artifact.producer_agent_id != synthesis.producer_agent_id or artifact.kind != 'research-synthesis':
                raise ValueError('serialized research synthesis artifact provenance mismatch')
            for finding_id in synthesis.finding_ids:
                provenance.get_finding(finding_id)
            for source_id in synthesis.source_ids:
                provenance.get_source(source_id)
        for handoff in handoffs:
            synthesis = result.synthesis(handoff.synthesis_id)
            if synthesis.artifact_id != handoff.synthesis_artifact_id:
                raise ValueError('serialized research handoff targets wrong synthesis artifact')
            target = registry.get(handoff.target_agent_id)
            if target.region != handoff.target_region or target.region not in _ENGINEERING_TARGET_REGIONS:
                raise ValueError('serialized research handoff target mismatch')
            if handoff.assurance_subject_id is not None:
                subject = assurance.evidence.get_subject(handoff.assurance_subject_id)
                if subject.artifact_id != synthesis.artifact_id:
                    raise ValueError('serialized research handoff assurance subject mismatch')
        return result


def _synthesis_core_payload(synthesis: ResearchSynthesis) -> dict[str, Any]:
    return {
        'synthesis_id': synthesis.synthesis_id,
        'producer_agent_id': synthesis.producer_agent_id,
        'title': synthesis.title,
        'finding_ids': list(synthesis.finding_ids),
        'claim_keys': list(synthesis.claim_keys),
        'source_ids': list(synthesis.source_ids),
        'evidence_modes': [x.value for x in synthesis.evidence_modes],
        'domains': [x.value for x in synthesis.domains],
        'conclusion': synthesis.conclusion,
        'limitations': list(synthesis.limitations),
        'evidence_refs': list(synthesis.evidence_refs),
        'reasons': list(synthesis.reasons),
        'shareable': synthesis.shareable,
        'created_epoch': synthesis.created_epoch,
    }


def _legacy_artifact_integrity_is_current(artifact: Any) -> bool:
    try:
        metadata = artifact.metadata
    except (TypeError, ValueError):
        return False
    payload = {
        'kind': artifact.kind,
        'producer_agent_id': artifact.producer_agent_id,
        'content': artifact.content,
        'evidence_refs': sorted({str(x) for x in artifact.evidence_refs}),
        'metadata': metadata,
    }
    digest = canonical_digest(payload)
    return artifact.digest == digest and artifact.artifact_id == 'artifact-' + digest[:24]


COMPONENT_ID = "external.research"
COMPONENT_VERSION = "0.0.1"
RESEARCH_PROTOCOL_VERSION = "2"
MIGRATED_FROM = "cogcoder.organization.research"


__all__ = (
    'COMPONENT_ID',
    'COMPONENT_VERSION',
    'CurrentResearchHandoffAssessment',
    'CurrentResearchHandoffDisposition',
    'MIGRATED_FROM',
    'RESEARCH_PROTOCOL_VERSION',
    'ResearchControlPlane',
    'ResearchHandoff',
    'ResearchHandoffDisposition',
    'ResearchSynthesis',
)
