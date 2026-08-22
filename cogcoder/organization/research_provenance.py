from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Mapping

from .registry import AgentRegistry
from .research_profiles import ResearchDomain, ResearchProfileRegistry
from .types import canonical_digest


class EvidenceMode(str, Enum):
    CURRENT_EXTERNAL = 'current_external'
    INTERNAL_OFFLINE = 'internal_offline'


class SourceKind(str, Enum):
    REPOSITORY_HISTORY = 'repository_history'
    OFFICIAL_DOCUMENTATION = 'official_documentation'
    OFFICIAL_API = 'official_api'
    PAPER = 'paper'
    PRIOR_ART = 'prior_art'
    PACKAGE_REGISTRY = 'package_registry'
    RELEASE_NOTE = 'release_note'
    ADVISORY = 'advisory'
    INTERNAL_OFFLINE = 'internal_offline'


class SourceQuality(IntEnum):
    SECONDARY = 1
    PRIMARY = 2
    AUTHORITATIVE = 3


class ClaimDisposition(str, Enum):
    SUPPORTED = 'supported'
    CONTRADICTED = 'contradicted'
    STALE = 'stale'
    UNKNOWN = 'unknown'


@dataclass(frozen=True, slots=True)
class ResearchSource:
    source_id: str
    kind: SourceKind
    locator: str
    title: str
    retrieved_at: str
    source_version: str
    retrieved_epoch: int
    max_age_epochs: int
    mode: EvidenceMode
    quality: SourceQuality
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'source_id': self.source_id,
            'kind': self.kind.value,
            'locator': self.locator,
            'title': self.title,
            'retrieved_at': self.retrieved_at,
            'source_version': self.source_version,
            'retrieved_epoch': self.retrieved_epoch,
            'max_age_epochs': self.max_age_epochs,
            'mode': self.mode.value,
            'quality': int(self.quality),
            'evidence_refs': list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ResearchSource':
        row = cls(
            source_id=str(state['source_id']),
            kind=SourceKind(str(state['kind'])),
            locator=str(state['locator']),
            title=str(state['title']),
            retrieved_at=str(state['retrieved_at']),
            source_version=str(state['source_version']),
            retrieved_epoch=int(state['retrieved_epoch']),
            max_age_epochs=int(state['max_age_epochs']),
            mode=EvidenceMode(str(state['mode'])),
            quality=SourceQuality(int(state['quality'])),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('research source digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ResearchFinding:
    finding_id: str
    producer_agent_id: str
    domain: ResearchDomain
    claim_key: str
    normalized_value: str
    statement: str
    source_ids: tuple[str, ...]
    history_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    created_epoch: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'finding_id': self.finding_id,
            'producer_agent_id': self.producer_agent_id,
            'domain': self.domain.value,
            'claim_key': self.claim_key,
            'normalized_value': self.normalized_value,
            'statement': self.statement,
            'source_ids': list(self.source_ids),
            'history_refs': list(self.history_refs),
            'evidence_refs': list(self.evidence_refs),
            'created_epoch': self.created_epoch,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ResearchFinding':
        row = cls(
            finding_id=str(state['finding_id']),
            producer_agent_id=str(state['producer_agent_id']),
            domain=ResearchDomain(str(state['domain'])),
            claim_key=str(state['claim_key']),
            normalized_value=str(state['normalized_value']),
            statement=str(state['statement']),
            source_ids=tuple(str(x) for x in state.get('source_ids', ())),
            history_refs=tuple(str(x) for x in state.get('history_refs', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            created_epoch=int(state['created_epoch']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('research finding digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ContradictionResolution:
    resolution_id: str
    claim_key: str
    resolver_agent_id: str
    selected_finding_id: str
    competing_finding_ids: tuple[str, ...]
    reason: str
    evidence_refs: tuple[str, ...]
    created_epoch: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'resolution_id': self.resolution_id,
            'claim_key': self.claim_key,
            'resolver_agent_id': self.resolver_agent_id,
            'selected_finding_id': self.selected_finding_id,
            'competing_finding_ids': list(self.competing_finding_ids),
            'reason': self.reason,
            'evidence_refs': list(self.evidence_refs),
            'created_epoch': self.created_epoch,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ContradictionResolution':
        row = cls(
            resolution_id=str(state['resolution_id']),
            claim_key=str(state['claim_key']),
            resolver_agent_id=str(state['resolver_agent_id']),
            selected_finding_id=str(state['selected_finding_id']),
            competing_finding_ids=tuple(str(x) for x in state.get('competing_finding_ids', ())),
            reason=str(state['reason']),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            created_epoch=int(state['created_epoch']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('research contradiction resolution digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ClaimAssessment:
    claim_key: str
    disposition: ClaimDisposition
    finding_ids: tuple[str, ...]
    normalized_values: tuple[str, ...]
    selected_finding_id: str | None = None
    resolution_id: str | None = None


_DOCS_KINDS = {
    SourceKind.OFFICIAL_DOCUMENTATION,
    SourceKind.OFFICIAL_API,
    SourceKind.PACKAGE_REGISTRY,
    SourceKind.RELEASE_NOTE,
    SourceKind.ADVISORY,
}
_PRIOR_ART_KINDS = {SourceKind.PAPER, SourceKind.PRIOR_ART}


class ResearchProvenanceLedger:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        profiles: ResearchProfileRegistry | None = None,
        sources: tuple[ResearchSource, ...] = (),
        findings: tuple[ResearchFinding, ...] = (),
        resolutions: tuple[ContradictionResolution, ...] = (),
        current_epoch: int = 1,
        resolution_counter: int = 0,
    ) -> None:
        self.registry = registry
        self.profiles = profiles or ResearchProfileRegistry(registry)
        self._sources = {row.source_id: row for row in sources}
        self._findings = {row.finding_id: row for row in findings}
        self._resolutions = list(resolutions)
        self._current_epoch = int(current_epoch)
        self._resolution_counter = int(resolution_counter)
        if self._current_epoch < 0:
            raise ValueError('research logical epoch must be non-negative')

    @property
    def current_epoch(self) -> int:
        return self._current_epoch

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def advance_epoch(self, amount: int = 1) -> int:
        amount = int(amount)
        if amount < 0:
            raise ValueError('research epoch advance must be non-negative')
        self._current_epoch += amount
        return self._current_epoch

    def register_source(
        self,
        *,
        source_id: str,
        kind: SourceKind,
        locator: str,
        title: str,
        retrieved_at: str,
        source_version: str,
        retrieved_epoch: int,
        max_age_epochs: int,
        mode: EvidenceMode,
        quality: SourceQuality,
        evidence_refs: tuple[str, ...],
    ) -> ResearchSource:
        if not all(str(x).strip() for x in (source_id, locator, title, retrieved_at, source_version)):
            raise ValueError('research source identity, locator, title, retrieval text and version must be explicit')
        if int(retrieved_epoch) < 0 or int(retrieved_epoch) > self.current_epoch:
            raise ValueError('research source retrieval epoch must be a non-future logical epoch')
        if int(max_age_epochs) < 0:
            raise ValueError('research source max age must be non-negative')
        evidence = tuple(str(x) for x in evidence_refs)
        if not evidence:
            raise ValueError('research source requires evidence refs')
        payload = {
            'source_id': str(source_id),
            'kind': SourceKind(kind).value,
            'locator': str(locator),
            'title': str(title),
            'retrieved_at': str(retrieved_at),
            'source_version': str(source_version),
            'retrieved_epoch': int(retrieved_epoch),
            'max_age_epochs': int(max_age_epochs),
            'mode': EvidenceMode(mode).value,
            'quality': int(SourceQuality(quality)),
            'evidence_refs': list(evidence),
        }
        row = ResearchSource(
            source_id=payload['source_id'], kind=SourceKind(payload['kind']), locator=payload['locator'],
            title=payload['title'], retrieved_at=payload['retrieved_at'], source_version=payload['source_version'],
            retrieved_epoch=payload['retrieved_epoch'], max_age_epochs=payload['max_age_epochs'],
            mode=EvidenceMode(payload['mode']), quality=SourceQuality(payload['quality']),
            evidence_refs=evidence, digest=canonical_digest(payload),
        )
        existing = self._sources.get(row.source_id)
        if existing is not None:
            if existing != row:
                raise ValueError('research source id cannot be rebound')
            return existing
        self._sources[row.source_id] = row
        return row

    def get_source(self, source_id: str) -> ResearchSource:
        try:
            return self._sources[str(source_id)]
        except KeyError as exc:
            raise KeyError(f'unknown research source: {source_id}') from exc

    def record_finding(
        self,
        *,
        finding_id: str,
        producer_agent_id: str,
        domain: ResearchDomain,
        claim_key: str,
        normalized_value: str,
        statement: str,
        source_ids: tuple[str, ...],
        history_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> ResearchFinding:
        if not all(str(x).strip() for x in (finding_id, producer_agent_id, claim_key, normalized_value, statement)):
            raise ValueError('research finding identity, producer, claim, value and statement must be explicit')
        try:
            profile = self.profiles.get(producer_agent_id)
        except KeyError as exc:
            raise PermissionError('only a registered Research identity can author findings') from exc
        domain = ResearchDomain(domain)
        if domain not in profile.domains:
            raise PermissionError('research identity is not authorized for finding domain')
        sources = tuple(str(x) for x in source_ids)
        evidence = tuple(str(x) for x in evidence_refs)
        history = tuple(str(x) for x in history_refs)
        if not sources or not evidence:
            raise ValueError('research finding requires source ids and evidence refs')
        source_rows = tuple(self.get_source(x) for x in sources)
        kinds = {row.kind for row in source_rows}
        if domain is ResearchDomain.REPOSITORY_ARCHAEOLOGY:
            if SourceKind.REPOSITORY_HISTORY not in kinds or not history:
                raise ValueError('repository archaeology requires repository-history provenance and history refs')
        elif domain is ResearchDomain.DOCS_API:
            if not (kinds & _DOCS_KINDS):
                raise ValueError('docs/API finding requires official docs/API/package/release/advisory provenance')
        elif domain is ResearchDomain.PRIOR_ART:
            if not (kinds & _PRIOR_ART_KINDS):
                raise ValueError('prior-art finding requires paper/prior-art provenance')
        payload = {
            'finding_id': str(finding_id),
            'producer_agent_id': profile.agent_id,
            'domain': domain.value,
            'claim_key': str(claim_key),
            'normalized_value': str(normalized_value),
            'statement': str(statement),
            'source_ids': list(sources),
            'history_refs': list(history),
            'evidence_refs': list(evidence),
            'created_epoch': self.current_epoch,
        }
        row = ResearchFinding(
            finding_id=payload['finding_id'], producer_agent_id=profile.agent_id, domain=domain,
            claim_key=payload['claim_key'], normalized_value=payload['normalized_value'], statement=payload['statement'],
            source_ids=sources, history_refs=history, evidence_refs=evidence,
            created_epoch=self.current_epoch, digest=canonical_digest(payload),
        )
        existing = self._findings.get(row.finding_id)
        if existing is not None:
            if existing != row:
                raise ValueError('research finding id cannot be rebound')
            return existing
        self._findings[row.finding_id] = row
        return row

    def get_finding(self, finding_id: str) -> ResearchFinding:
        try:
            return self._findings[str(finding_id)]
        except KeyError as exc:
            raise KeyError(f'unknown research finding: {finding_id}') from exc

    def findings_for_claim(self, claim_key: str) -> tuple[ResearchFinding, ...]:
        return tuple(sorted(
            (row for row in self._findings.values() if row.claim_key == str(claim_key)),
            key=lambda row: row.finding_id,
        ))

    def is_source_fresh(self, source_id: str) -> bool:
        row = self.get_source(source_id)
        return 0 <= self.current_epoch - row.retrieved_epoch <= row.max_age_epochs

    def is_finding_fresh(self, finding_id: str) -> bool:
        row = self.get_finding(finding_id)
        return all(self.is_source_fresh(source_id) for source_id in row.source_ids)

    def _latest_live_resolution(self, claim_key: str, fresh_ids: set[str]) -> ContradictionResolution | None:
        for row in reversed(self._resolutions):
            if row.claim_key == str(claim_key) and row.selected_finding_id in fresh_ids:
                return row
        return None

    def assess_claim(self, claim_key: str) -> ClaimAssessment:
        rows = self.findings_for_claim(claim_key)
        if not rows:
            return ClaimAssessment(str(claim_key), ClaimDisposition.UNKNOWN, (), ())
        fresh = tuple(row for row in rows if self.is_finding_fresh(row.finding_id))
        if not fresh:
            return ClaimAssessment(
                str(claim_key), ClaimDisposition.STALE,
                tuple(row.finding_id for row in rows),
                tuple(sorted({row.normalized_value for row in rows})),
            )
        values = tuple(sorted({row.normalized_value for row in fresh}))
        if len(values) == 1:
            return ClaimAssessment(
                str(claim_key), ClaimDisposition.SUPPORTED,
                tuple(row.finding_id for row in fresh), values,
                selected_finding_id=fresh[0].finding_id,
            )
        fresh_ids = {row.finding_id for row in fresh}
        resolution = self._latest_live_resolution(claim_key, fresh_ids)
        if resolution is not None:
            return ClaimAssessment(
                str(claim_key), ClaimDisposition.SUPPORTED,
                tuple(row.finding_id for row in fresh), values,
                selected_finding_id=resolution.selected_finding_id,
                resolution_id=resolution.resolution_id,
            )
        return ClaimAssessment(
            str(claim_key), ClaimDisposition.CONTRADICTED,
            tuple(row.finding_id for row in fresh), values,
        )

    def _finding_quality(self, finding: ResearchFinding) -> SourceQuality:
        return max((self.get_source(x).quality for x in finding.source_ids), default=SourceQuality.SECONDARY)

    def resolve_contradiction(
        self,
        *,
        claim_key: str,
        resolver_agent_id: str,
        selected_finding_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> ContradictionResolution:
        if str(resolver_agent_id) != 'research.chief':
            raise PermissionError('only Research Chief may resolve live research contradictions')
        self.profiles.get(resolver_agent_id)
        if not str(reason).strip() or not evidence_refs:
            raise ValueError('research contradiction resolution requires reason and evidence refs')
        assessment = self.assess_claim(claim_key)
        if assessment.disposition is not ClaimDisposition.CONTRADICTED:
            raise ValueError('claim is not an unresolved live contradiction')
        if str(selected_finding_id) not in assessment.finding_ids:
            raise ValueError('selected research finding is not a live contradiction candidate')
        selected = self.get_finding(selected_finding_id)
        if not self.is_finding_fresh(selected.finding_id):
            raise ValueError('selected research finding is stale')
        competitors = tuple(self.get_finding(x) for x in assessment.finding_ids)
        selected_quality = self._finding_quality(selected)
        alternative_qualities = [self._finding_quality(x) for x in competitors if x.finding_id != selected.finding_id]
        if alternative_qualities and selected_quality < max(alternative_qualities):
            raise ValueError('selected finding cannot under-rank a higher-quality live alternative')
        self._resolution_counter += 1
        resolution_id = f'research-resolution-{self._resolution_counter:08d}'
        evidence = tuple(str(x) for x in evidence_refs)
        competing_ids = tuple(sorted(x.finding_id for x in competitors))
        payload = {
            'resolution_id': resolution_id,
            'claim_key': str(claim_key),
            'resolver_agent_id': 'research.chief',
            'selected_finding_id': selected.finding_id,
            'competing_finding_ids': list(competing_ids),
            'reason': str(reason),
            'evidence_refs': list(evidence),
            'created_epoch': self.current_epoch,
        }
        row = ContradictionResolution(
            resolution_id=resolution_id, claim_key=str(claim_key), resolver_agent_id='research.chief',
            selected_finding_id=selected.finding_id, competing_finding_ids=competing_ids,
            reason=str(reason), evidence_refs=evidence, created_epoch=self.current_epoch,
            digest=canonical_digest(payload),
        )
        self._resolutions.append(row)
        return row

    def resolutions(self) -> tuple[ContradictionResolution, ...]:
        return tuple(self._resolutions)

    def to_state(self) -> dict[str, Any]:
        return {
            'profiles': self.profiles.to_state(),
            'current_epoch': self.current_epoch,
            'sources': [self._sources[key].to_state() for key in sorted(self._sources)],
            'findings': [self._findings[key].to_state() for key in sorted(self._findings)],
            'resolutions': [row.to_state() for row in self._resolutions],
            'resolution_counter': self._resolution_counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        state: Mapping[str, Any],
    ) -> 'ResearchProvenanceLedger':
        profiles = ResearchProfileRegistry.from_state(registry, state.get('profiles', {}))
        sources = tuple(ResearchSource.from_state(x) for x in state.get('sources', ()))
        findings = tuple(ResearchFinding.from_state(x) for x in state.get('findings', ()))
        resolutions = tuple(ContradictionResolution.from_state(x) for x in state.get('resolutions', ()))
        result = cls(
            registry=registry, profiles=profiles, sources=sources, findings=findings,
            resolutions=resolutions, current_epoch=int(state.get('current_epoch', 1)),
            resolution_counter=int(state.get('resolution_counter', len(resolutions))),
        )
        if len(result._sources) != len(sources) or len(result._findings) != len(findings):
            raise ValueError('duplicate research source/finding id in serialized state')
        for finding in findings:
            try:
                profile = profiles.get(finding.producer_agent_id)
            except KeyError as exc:
                raise PermissionError('serialized research finding has non-Research producer') from exc
            if finding.domain not in profile.domains:
                raise PermissionError('serialized research finding domain is not authorized for producer')
            for source_id in finding.source_ids:
                result.get_source(source_id)
        for resolution in resolutions:
            if resolution.resolver_agent_id != 'research.chief':
                raise PermissionError('serialized contradiction resolution has invalid resolver')
            result.get_finding(resolution.selected_finding_id)
            for finding_id in resolution.competing_finding_ids:
                result.get_finding(finding_id)
        return result
