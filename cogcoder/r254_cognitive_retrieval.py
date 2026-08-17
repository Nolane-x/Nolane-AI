from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Protocol, Sequence

_TOKEN = re.compile(r"[\w.:-]+", re.UNICODE)
_CLAIM = re.compile(r"^\s*(.+?)\s+--([^>-]+)-->\s+(.+?)\s*$")
_VERSION_TOKEN = re.compile(r"(\d+|[A-Za-z]+)")


def _nonempty(value: str, name: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f'{name} must be non-empty')
    return value


def _unit(value: float, name: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f'{name} must be in [0,1]')
    return value


def _terms(text: str) -> list[str]:
    return [token.casefold() for token in _TOKEN.findall(str(text))]


def _char_ngrams(text: str, n: int = 3) -> Counter[str]:
    normalized = ' '.join(_terms(text))
    if len(normalized) < n:
        return Counter({normalized: 1}) if normalized else Counter()
    return Counter(normalized[index:index + n] for index in range(len(normalized) - n + 1))


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _version_key(version: str) -> tuple[tuple[int, object], ...]:
    parts: list[tuple[int, object]] = []
    for token in _VERSION_TOKEN.findall(str(version)):
        parts.append((0, int(token)) if token.isdigit() else (1, token.casefold()))
    return tuple(parts) or ((1, str(version).casefold()),)


def content_digest(text: str) -> str:
    return hashlib.sha256(str(text).encode('utf-8')).hexdigest()


@dataclass(frozen=True, slots=True)
class ArtifactRelation:
    target_id: str
    relation: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        _nonempty(self.target_id, 'target_id')
        _nonempty(self.relation, 'relation')
        _unit(self.weight, 'weight')


@dataclass(frozen=True, slots=True)
class RetrievalArtifact:
    artifact_id: str
    kind: str
    text: str
    source_uri: str
    version: str = '1'
    trust_score: float = 1.0
    tags: frozenset[str] = frozenset()
    symbols: frozenset[str] = frozenset()
    relations: tuple[ArtifactRelation, ...] = ()
    valid_from: str | None = None
    valid_to: str | None = None
    content_sha256: str = ''

    def __post_init__(self) -> None:
        _nonempty(self.artifact_id, 'artifact_id')
        _nonempty(self.kind, 'kind')
        _nonempty(self.text, 'text')
        _nonempty(self.source_uri, 'source_uri')
        _nonempty(self.version, 'version')
        _unit(self.trust_score, 'trust_score')
        if self.content_sha256 and len(self.content_sha256) != 64:
            raise ValueError('content_sha256 must be a SHA-256 hex digest')

    def verify_digest(self) -> bool:
        return bool(self.content_sha256) and content_digest(self.text) == self.content_sha256


def make_artifact(
    *,
    artifact_id: str,
    kind: str,
    text: str,
    source_uri: str,
    version: str = '1',
    trust_score: float = 1.0,
    tags: frozenset[str] = frozenset(),
    symbols: frozenset[str] = frozenset(),
    relations: Iterable[ArtifactRelation | tuple[str, str, float]] = (),
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> RetrievalArtifact:
    converted = []
    for relation in relations:
        if isinstance(relation, ArtifactRelation):
            converted.append(relation)
        else:
            target, relation_name, weight = relation
            converted.append(ArtifactRelation(str(target), str(relation_name), float(weight)))
    return RetrievalArtifact(
        artifact_id=str(artifact_id),
        kind=str(kind),
        text=str(text),
        source_uri=str(source_uri),
        version=str(version),
        trust_score=float(trust_score),
        tags=frozenset(map(str, tags)),
        symbols=frozenset(map(str, symbols)),
        relations=tuple(converted),
        valid_from=valid_from,
        valid_to=valid_to,
        content_sha256=content_digest(text),
    )


@dataclass(frozen=True, slots=True)
class CognitiveRetrievalNeed:
    objective: str
    deficit_kind: str
    query: str
    unresolved_requirements: tuple[str, ...] = ()
    context_tags: frozenset[str] = frozenset()
    symbols: frozenset[str] = frozenset()
    required_kinds: frozenset[str] = frozenset()
    representation_id: str = 'default'
    current_time: str | None = None
    min_sufficiency: float = 0.62

    def __post_init__(self) -> None:
        _nonempty(self.objective, 'objective')
        _nonempty(self.deficit_kind, 'deficit_kind')
        _nonempty(self.query, 'query')
        _unit(self.min_sufficiency, 'min_sufficiency')

    def cues(self) -> frozenset[str]:
        values = {f'deficit:{self.deficit_kind}', f'representation:{self.representation_id}'}
        values.update(f'tag:{tag}' for tag in self.context_tags)
        values.update(f'symbol:{symbol}' for symbol in self.symbols)
        values.update(f'kind:{kind}' for kind in self.required_kinds)
        return frozenset(values)


@dataclass(frozen=True, slots=True)
class QueryBranch:
    branch_type: str
    query: str
    tags: frozenset[str] = frozenset()
    symbols: frozenset[str] = frozenset()
    artifact_kinds: frozenset[str] = frozenset()
    weight: float = 1.0

    def __post_init__(self) -> None:
        _nonempty(self.branch_type, 'branch_type')
        _nonempty(self.query, 'query')
        if float(self.weight) <= 0:
            raise ValueError('branch weight must be positive')


class CognitiveQueryCompiler:
    trainable_parameter_count = 0

    def compile(self, need: CognitiveRetrievalNeed) -> tuple[QueryBranch, ...]:
        rows: list[QueryBranch] = []

        def add(branch_type: str, query: str, *, weight: float = 1.0, kinds: Iterable[str] | None = None) -> None:
            query = ' '.join(str(query).split())
            if not query:
                return
            candidate = QueryBranch(
                branch_type,
                query,
                need.context_tags,
                need.symbols,
                frozenset(need.required_kinds if kinds is None else map(str, kinds)),
                float(weight),
            )
            key = (candidate.branch_type, candidate.query, candidate.artifact_kinds)
            if key not in {(row.branch_type, row.query, row.artifact_kinds) for row in rows}:
                rows.append(candidate)

        add('semantic', f'{need.query} {need.objective}', weight=1.0)
        for requirement in need.unresolved_requirements[:3]:
            add('requirement', f'{requirement} {need.query}', weight=1.1)
        if need.symbols:
            add('symbol', f"{' '.join(sorted(need.symbols))} {need.query}", weight=1.35)
        behavioral = need.deficit_kind in {'skill_gap', 'tool_gap', 'capability_gap', 'routing_uncertainty'} or 'procedure' in need.required_kinds
        if behavioral:
            kinds = need.required_kinds or frozenset({'procedure', 'tool'})
            add('procedure', f'verified procedure operator skill {need.query} {need.objective}', weight=1.25, kinds=kinds)
        if need.deficit_kind in {'temporal_conflict', 'contradiction'}:
            add('temporal', f'current latest authoritative version conflict {need.query}', weight=1.2)
        if need.deficit_kind in {'code_analysis_gap', 'representation_mismatch'}:
            add('structural', f'call import dependency dataflow {need.query}', weight=1.15, kinds=need.required_kinds or {'code', 'documentation'})
        return tuple(rows)

    def follow_up(self, need: CognitiveRetrievalNeed, anchors: Iterable[str], *, round_index: int) -> tuple[QueryBranch, ...]:
        anchor_text = ' '.join(dict.fromkeys(str(anchor) for anchor in anchors if str(anchor).strip()))
        if not anchor_text:
            return self.compile(need)
        return (
            QueryBranch('anchor', f'{need.query} {anchor_text}', need.context_tags, need.symbols, need.required_kinds, 1.25 + 0.05 * int(round_index)),
            QueryBranch('anchor-verify', f'authoritative verify counterexample {anchor_text} {need.objective}', need.context_tags, need.symbols, need.required_kinds, 1.15),
        )


@dataclass(frozen=True, slots=True)
class SourceHit:
    artifact: RetrievalArtifact
    source_id: str
    branch_type: str
    branch_query: str
    score: float
    lexical_score: float
    semantic_score: float
    symbol_score: float
    tag_score: float
    kind_score: float
    rank: int = 0
    association_score: float = 0.0
    graph_depth: int = 0
    rationale: tuple[str, ...] = ()


class ArtifactSource(Protocol):
    source_id: str

    def search(self, branch: QueryBranch, *, k: int) -> list[SourceHit]: ...

    def get(self, artifact_id: str) -> RetrievalArtifact | None: ...


class InMemoryArtifactSource:
    trainable_parameter_count = 0

    def __init__(self, source_id: str, artifacts: Sequence[RetrievalArtifact]) -> None:
        self.source_id = _nonempty(source_id, 'source_id')
        self._artifacts: dict[str, RetrievalArtifact] = {}
        for artifact in artifacts:
            if not artifact.verify_digest():
                raise ValueError(f'artifact digest mismatch: {artifact.artifact_id}')
            previous = self._artifacts.get(artifact.artifact_id)
            if previous is not None and previous != artifact:
                raise ValueError(f'artifact identity collision: {artifact.artifact_id}')
            self._artifacts[artifact.artifact_id] = artifact
        self._rows: list[tuple[RetrievalArtifact, list[str], Counter[str]]] = []
        self._df: Counter[str] = Counter()
        for artifact in self._artifacts.values():
            terms = _terms(' '.join((artifact.text, ' '.join(artifact.tags), ' '.join(artifact.symbols))))
            ngrams = _char_ngrams(artifact.text)
            self._rows.append((artifact, terms, ngrams))
            self._df.update(set(terms))
        self._avgdl = sum(len(terms) for _artifact, terms, _ngrams in self._rows) / max(1, len(self._rows))

    def get(self, artifact_id: str) -> RetrievalArtifact | None:
        return self._artifacts.get(str(artifact_id))

    def search(self, branch: QueryBranch, *, k: int) -> list[SourceHit]:
        if int(k) < 1:
            raise ValueError('k must be positive')
        query_terms = _terms(branch.query)
        query_ngrams = _char_ngrams(branch.query)
        n_rows = max(1, len(self._rows))
        scored: list[tuple[float, str, SourceHit]] = []
        for artifact, terms, ngrams in self._rows:
            tf = Counter(terms)
            dl = max(1, len(terms))
            lexical = 0.0
            for term in query_terms:
                df = self._df.get(term, 0)
                idf = math.log(1.0 + (n_rows - df + 0.5) / (df + 0.5))
                freq = tf.get(term, 0)
                if freq:
                    lexical += idf * (freq * 2.2) / (freq + 1.2 * (0.25 + 0.75 * dl / max(self._avgdl, 1e-9)))
            semantic = _cosine(query_ngrams, ngrams)
            symbol_overlap = len(branch.symbols.intersection(artifact.symbols))
            symbol_score = 1.0 if symbol_overlap else 0.0
            if symbol_overlap:
                symbol_score += 0.25 * (symbol_overlap - 1)
            tag_union = branch.tags.union(artifact.tags)
            tag_score = len(branch.tags.intersection(artifact.tags)) / max(1, len(tag_union))
            kind_score = 0.0
            if branch.artifact_kinds:
                kind_score = 1.0 if artifact.kind in branch.artifact_kinds else -0.45
            raw = (
                0.62 * lexical
                + 1.4 * semantic
                + 4.0 * symbol_score
                + 1.6 * tag_score
                + 1.8 * kind_score
                + 0.45 * artifact.trust_score
            ) * float(branch.weight)
            rationale = []
            if symbol_score:
                rationale.append('symbol-match')
            if tag_score:
                rationale.append('tag-match')
            if kind_score > 0:
                rationale.append('kind-match')
            hit = SourceHit(
                artifact,
                self.source_id,
                branch.branch_type,
                branch.query,
                raw,
                lexical,
                semantic,
                symbol_score,
                tag_score,
                kind_score,
                rationale=tuple(rationale),
            )
            scored.append((raw, artifact.artifact_id, hit))
        scored.sort(key=lambda row: (-row[0], row[1]))
        out = []
        for index, (_score, _artifact_id, hit) in enumerate(scored[: int(k)], start=1):
            out.append(SourceHit(
                artifact=hit.artifact,
                source_id=hit.source_id,
                branch_type=hit.branch_type,
                branch_query=hit.branch_query,
                score=hit.score,
                lexical_score=hit.lexical_score,
                semantic_score=hit.semantic_score,
                symbol_score=hit.symbol_score,
                tag_score=hit.tag_score,
                kind_score=hit.kind_score,
                rank=index,
                association_score=hit.association_score,
                graph_depth=hit.graph_depth,
                rationale=hit.rationale,
            ))
        return out


class CallbackArtifactSource:
    """Host bridge for fresh external knowledge providers.

    The callback is allowed to fetch/search outside the process, but every returned artifact must
    already be wrapped in the same provenance-checked schema used by local sources. Results are
    cached so graph expansion and later association recall can resolve them without another host call.
    """

    trainable_parameter_count = 0

    def __init__(self, source_id: str, fetcher) -> None:
        self.source_id = _nonempty(source_id, 'source_id')
        if not callable(fetcher):
            raise TypeError('fetcher must be callable')
        self.fetcher = fetcher
        self._cache: dict[str, RetrievalArtifact] = {}
        self._errors: list[str] = []

    def get(self, artifact_id: str) -> RetrievalArtifact | None:
        return self._cache.get(str(artifact_id))

    def drain_errors(self) -> tuple[str, ...]:
        rows = tuple(self._errors)
        self._errors.clear()
        return rows

    def search(self, branch: QueryBranch, *, k: int) -> list[SourceHit]:
        if int(k) < 1:
            raise ValueError('k must be positive')
        try:
            rows = self.fetcher(branch, int(k))
        except (TimeoutError, ConnectionError, OSError) as exc:
            error = f'{self.source_id}:{type(exc).__name__}:{exc}'
            if error not in self._errors:
                self._errors.append(error)
            return []
        if rows is None:
            rows = ()
        out: list[SourceHit] = []
        query_terms = Counter(_terms(branch.query))
        query_ngrams = _char_ngrams(branch.query)
        for raw in rows:
            host_score = None
            rationale: tuple[str, ...] = ('host-provider',)
            if isinstance(raw, RetrievalArtifact):
                artifact = raw
            elif isinstance(raw, tuple) and raw and isinstance(raw[0], RetrievalArtifact):
                artifact = raw[0]
                if len(raw) > 1:
                    host_score = float(raw[1])
                if len(raw) > 2:
                    rationale = tuple(map(str, raw[2]))
            else:
                raise TypeError('callback source must return RetrievalArtifact or (artifact, score, rationale) tuples')
            if not artifact.verify_digest():
                raise ValueError(f'artifact digest mismatch: {artifact.artifact_id}')
            previous = self._cache.get(artifact.artifact_id)
            if previous is not None and previous != artifact:
                raise ValueError(f'artifact identity collision: {artifact.artifact_id}')
            self._cache[artifact.artifact_id] = artifact
            artifact_terms = Counter(_terms(' '.join((artifact.text, ' '.join(artifact.tags), ' '.join(artifact.symbols)))))
            overlap = sum(min(value, artifact_terms.get(term, 0)) for term, value in query_terms.items())
            lexical = overlap / max(1, sum(query_terms.values()))
            semantic = _cosine(query_ngrams, _char_ngrams(artifact.text))
            symbol_score = 1.0 if branch.symbols.intersection(artifact.symbols) else 0.0
            tag_score = len(branch.tags.intersection(artifact.tags)) / max(1, len(branch.tags.union(artifact.tags)))
            kind_score = 0.0 if not branch.artifact_kinds else (1.0 if artifact.kind in branch.artifact_kinds else -0.45)
            provider = artifact.trust_score if host_score is None else host_score
            score = float(branch.weight) * (
                1.0 * lexical + 1.4 * semantic + 4.0 * symbol_score + 1.5 * tag_score + 1.8 * kind_score + 2.0 * provider
            )
            out.append(SourceHit(
                artifact=artifact,
                source_id=self.source_id,
                branch_type=branch.branch_type,
                branch_query=branch.query,
                score=score,
                lexical_score=lexical,
                semantic_score=semantic,
                symbol_score=symbol_score,
                tag_score=tag_score,
                kind_score=kind_score,
                rationale=rationale,
            ))
        out.sort(key=lambda row: (-row.score, -row.artifact.trust_score, row.artifact.artifact_id))
        ranked = []
        for index, row in enumerate(out[: int(k)], start=1):
            ranked.append(SourceHit(
                artifact=row.artifact, source_id=row.source_id, branch_type=row.branch_type,
                branch_query=row.branch_query, score=row.score, lexical_score=row.lexical_score,
                semantic_score=row.semantic_score, symbol_score=row.symbol_score, tag_score=row.tag_score,
                kind_score=row.kind_score, rank=index, rationale=row.rationale,
            ))
        return ranked


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    artifact: RetrievalArtifact
    source_id: str
    score: float
    branch_types: tuple[str, ...]
    branch_queries: tuple[str, ...]
    lexical_score: float
    semantic_score: float
    symbol_score: float
    tag_score: float
    kind_score: float
    association_score: float = 0.0
    graph_depth: int = 0
    rationale: tuple[str, ...] = ()


class FederatedRetriever:
    trainable_parameter_count = 0

    def __init__(self, sources: Sequence[ArtifactSource]) -> None:
        if not sources:
            raise ValueError('at least one artifact source is required')
        self.sources = tuple(sources)

    def resolve(self, artifact_id: str) -> tuple[tuple[str, RetrievalArtifact], ...]:
        out = []
        for source in self.sources:
            artifact = source.get(artifact_id)
            if artifact is not None:
                out.append((source.source_id, artifact))
        return tuple(out)

    def retrieve(self, branches: Sequence[QueryBranch], *, k: int = 8, association: Mapping[str, float] | None = None) -> tuple[RetrievalHit, ...]:
        if int(k) < 1:
            raise ValueError('k must be positive')
        association = dict(association or {})
        grouped: dict[tuple[str, str], list[SourceHit]] = defaultdict(list)
        raw_hits: list[SourceHit] = []
        per_branch_k = max(int(k), 4)
        for branch in branches:
            for source in self.sources:
                hits = source.search(branch, k=per_branch_k)
                raw_hits.extend(hits)
                for hit in hits:
                    grouped[(hit.source_id, hit.artifact.artifact_id)].append(hit)

        # Agreement across independent source URIs boosts mutually supporting claims without collapsing provenance.
        claim_support: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for hit in raw_hits:
            match = _CLAIM.match(hit.artifact.text.strip())
            if match:
                key = (match.group(1).strip(), match.group(2).strip(), match.group(3).strip())
                # Query-branch repetition is not independent evidence.  Only distinct provenance
                # URIs count toward agreement support.
                claim_support[key].add(hit.artifact.source_uri)

        fused: list[RetrievalHit] = []
        for (source_id, artifact_id), rows in grouped.items():
            artifact = rows[0].artifact
            max_raw = max(row.score for row in rows)
            rrf = sum(float(getattr(next(branch for branch in branches if branch.branch_type == row.branch_type and branch.query == row.branch_query), 'weight', 1.0)) / (60.0 + row.rank) for row in rows)
            agreement = 0.0
            match = _CLAIM.match(artifact.text.strip())
            if match:
                support = len(claim_support[(match.group(1).strip(), match.group(2).strip(), match.group(3).strip())])
                agreement = 0.35 * max(0, support - 1)
            association_score = float(association.get(artifact_id, 0.0))
            score = max_raw + 4.0 * rrf + agreement + 1.25 * association_score
            rationale = tuple(dict.fromkeys(reason for row in rows for reason in row.rationale))
            if agreement:
                rationale += ('independent-support',)
            if association_score > 0:
                rationale += ('association-credit',)
            fused.append(RetrievalHit(
                artifact=artifact,
                source_id=source_id,
                score=score,
                branch_types=tuple(dict.fromkeys(row.branch_type for row in rows)),
                branch_queries=tuple(dict.fromkeys(row.branch_query for row in rows)),
                lexical_score=max(row.lexical_score for row in rows),
                semantic_score=max(row.semantic_score for row in rows),
                symbol_score=max(row.symbol_score for row in rows),
                tag_score=max(row.tag_score for row in rows),
                kind_score=max(row.kind_score for row in rows),
                association_score=association_score,
                graph_depth=0,
                rationale=rationale,
            ))
        fused.sort(key=lambda row: (-row.score, -row.artifact.trust_score, row.artifact.artifact_id, row.source_id))
        return tuple(fused[: int(k)])


@dataclass(frozen=True, slots=True)
class EvidenceConflict:
    subject: str
    relation: str
    objects: tuple[str, ...]
    artifact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FusionResult:
    accepted_hits: tuple[RetrievalHit, ...]
    accepted_artifact_ids: tuple[str, ...]
    superseded_artifact_ids: tuple[str, ...]
    conflicts: tuple[EvidenceConflict, ...]
    source_diversity: int
    evidence_score: float


class EpistemicFusion:
    trainable_parameter_count = 0

    def fuse(self, hits: Sequence[RetrievalHit]) -> FusionResult:
        valid = [hit for hit in hits if hit.artifact.verify_digest()]
        by_claim_source: dict[tuple[str, str, str], list[RetrievalHit]] = defaultdict(list)
        non_claims: list[RetrievalHit] = []
        for hit in valid:
            match = _CLAIM.match(hit.artifact.text.strip())
            if match:
                key = (match.group(1).strip(), match.group(2).strip(), hit.artifact.source_uri)
                by_claim_source[key].append(hit)
            else:
                non_claims.append(hit)
        superseded: list[str] = []
        current: list[RetrievalHit] = list(non_claims)
        for rows in by_claim_source.values():
            rows = sorted(rows, key=lambda hit: (_version_key(hit.artifact.version), hit.artifact.trust_score, hit.score, hit.artifact.artifact_id), reverse=True)
            current.append(rows[0])
            superseded.extend(hit.artifact.artifact_id for hit in rows[1:])
        current.sort(key=lambda hit: (-hit.score, -hit.artifact.trust_score, hit.artifact.artifact_id, hit.source_id))

        claim_groups: dict[tuple[str, str], list[tuple[str, RetrievalHit]]] = defaultdict(list)
        for hit in current:
            match = _CLAIM.match(hit.artifact.text.strip())
            if match:
                claim_groups[(match.group(1).strip(), match.group(2).strip())].append((match.group(3).strip(), hit))
        conflicts = []
        for (subject, relation), rows in sorted(claim_groups.items()):
            objects = tuple(dict.fromkeys(value for value, _hit in rows))
            if len(objects) > 1:
                conflicts.append(EvidenceConflict(subject, relation, objects, tuple(hit.artifact.artifact_id for _value, hit in rows)))

        max_score = max((hit.score for hit in current), default=0.0)
        source_diversity = len({hit.artifact.source_uri for hit in current})
        if not current:
            evidence_score = 0.0
        else:
            coverage = min(1.0, len(current) / 3.0)
            trust = sum(hit.artifact.trust_score for hit in current[:5]) / min(5, len(current))
            score_component = 1.0 - math.exp(-max(0.0, max_score) / 4.0)
            diversity_component = min(1.0, source_diversity / 2.0)
            conflict_penalty = 0.15 if conflicts else 0.0
            evidence_score = min(1.0, max(0.0, 0.3 * coverage + 0.3 * trust + 0.25 * score_component + 0.15 * diversity_component - conflict_penalty))
        return FusionResult(
            accepted_hits=tuple(current),
            accepted_artifact_ids=tuple(hit.artifact.artifact_id for hit in current),
            superseded_artifact_ids=tuple(sorted(set(superseded))),
            conflicts=tuple(conflicts),
            source_diversity=source_diversity,
            evidence_score=evidence_score,
        )


@dataclass(frozen=True, slots=True)
class CognitiveAttachment:
    artifact_id: str
    kind: str
    text: str
    source_uri: str
    version: str
    activation: float
    trust_score: float
    rationale: tuple[str, ...]
    content_sha256: str


class AttachmentWorkspace:
    trainable_parameter_count = 0

    def __init__(self, *, max_attachments: int = 8, max_chars: int = 8000) -> None:
        if int(max_attachments) < 1 or int(max_chars) < 1:
            raise ValueError('attachment budgets must be positive')
        self.max_attachments = int(max_attachments)
        self.max_chars = int(max_chars)
        self._rows: dict[str, CognitiveAttachment] = {}

    def attach(self, artifact: RetrievalArtifact, *, activation: float, rationale: Iterable[str]) -> CognitiveAttachment:
        if not artifact.verify_digest():
            raise ValueError('artifact digest mismatch')
        row = CognitiveAttachment(
            artifact.artifact_id,
            artifact.kind,
            artifact.text,
            artifact.source_uri,
            artifact.version,
            float(activation),
            artifact.trust_score,
            tuple(map(str, rationale)),
            artifact.content_sha256,
        )
        previous = self._rows.get(row.artifact_id)
        if previous is None or (row.activation, row.trust_score) > (previous.activation, previous.trust_score):
            self._rows[row.artifact_id] = row
        return row

    def active(self) -> tuple[CognitiveAttachment, ...]:
        candidates = sorted(self._rows.values(), key=lambda row: (-row.activation, -row.trust_score, row.artifact_id))
        out = []
        chars = 0
        for row in candidates:
            if len(out) >= self.max_attachments:
                break
            if chars + len(row.text) > self.max_chars:
                continue
            out.append(row)
            chars += len(row.text)
        return tuple(out)

    def clear(self) -> None:
        self._rows.clear()


class AssociationCreditGraph:
    trainable_parameter_count = 0

    def __init__(self) -> None:
        self._weights: dict[str, dict[str, float]] = defaultdict(dict)
        self._counts: Counter[tuple[str, str]] = Counter()

    def record(self, cues: Iterable[str], artifact_ids: Iterable[str], *, success: bool) -> None:
        delta = 1.0 if success else -1.0
        for cue in set(map(str, cues)):
            for artifact_id in set(map(str, artifact_ids)):
                key = (cue, artifact_id)
                self._counts[key] += 1
                current = self._weights[cue].get(artifact_id, 0.0)
                learning_rate = 1.0 / math.sqrt(self._counts[key])
                self._weights[cue][artifact_id] = max(-2.0, min(2.0, current + delta * learning_rate))

    def activation(self, cues: Iterable[str], artifact_id: str) -> float:
        cues = tuple(set(map(str, cues)))
        if not cues:
            return 0.0
        values = [self._weights.get(cue, {}).get(str(artifact_id), 0.0) for cue in cues]
        nonzero = [value for value in values if value]
        if not nonzero:
            return 0.0
        return sum(nonzero) / math.sqrt(len(cues))

    def candidates(self, cues: Iterable[str], *, min_activation: float = 0.05) -> dict[str, float]:
        artifact_ids = {artifact_id for cue in set(map(str, cues)) for artifact_id in self._weights.get(cue, {})}
        rows = {artifact_id: self.activation(cues, artifact_id) for artifact_id in artifact_ids}
        return {artifact_id: score for artifact_id, score in rows.items() if score >= float(min_activation)}

    def snapshot(self) -> dict[str, object]:
        return {
            'weights': {
                cue: {artifact_id: self._weights[cue][artifact_id] for artifact_id in sorted(self._weights[cue])}
                for cue in sorted(self._weights)
            },
            'counts': [
                {'cue': cue, 'artifact_id': artifact_id, 'count': int(self._counts[(cue, artifact_id)])}
                for cue, artifact_id in sorted(self._counts)
            ],
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> 'AssociationCreditGraph':
        graph = cls()
        if 'weights' in snapshot:
            raw_weights = snapshot.get('weights', {})
            raw_counts = snapshot.get('counts', ())
        else:
            # Backward-compatible import for early R2.54 development snapshots.
            raw_weights = snapshot
            raw_counts = ()
        if not isinstance(raw_weights, Mapping):
            raise TypeError('association snapshot weights must be a mapping')
        for cue, rows in raw_weights.items():
            if not isinstance(rows, Mapping):
                raise TypeError('association cue rows must be mappings')
            for artifact_id, value in rows.items():
                numeric = float(value)
                if not math.isfinite(numeric) or not -2.0 <= numeric <= 2.0:
                    raise ValueError('association weight out of bounds')
                graph._weights[str(cue)][str(artifact_id)] = numeric
                graph._counts[(str(cue), str(artifact_id))] = 1
        for row in raw_counts if isinstance(raw_counts, Sequence) else ():
            if not isinstance(row, Mapping):
                continue
            cue = str(row.get('cue', ''))
            artifact_id = str(row.get('artifact_id', ''))
            count = int(row.get('count', 0))
            if cue and artifact_id and count > 0:
                graph._counts[(cue, artifact_id)] = count
        return graph


@dataclass(frozen=True, slots=True)
class RetrievalPolicyDecision:
    mode: str
    seed_k: int
    max_rounds: int
    graph_depth: int


class AdaptiveRetrievalPolicy:
    """Choose retrieval shape from the cognitive deficit instead of using one fixed top-k."""

    trainable_parameter_count = 0

    def decide(
        self,
        need: CognitiveRetrievalNeed,
        *,
        max_results: int,
        max_rounds: int,
        max_graph_depth: int,
    ) -> RetrievalPolicyDecision:
        if need.deficit_kind in {'code_analysis_gap', 'representation_mismatch', 'causal_gap'}:
            return RetrievalPolicyDecision(
                'structural',
                max(1, min(int(max_results), 2)),
                max(1, min(int(max_rounds), 2)),
                min(int(max_graph_depth), 3),
            )
        if need.deficit_kind in {'knowledge_gap', 'temporal_conflict', 'contradiction', 'information_acquisition_gap'}:
            return RetrievalPolicyDecision(
                'evidence',
                max(1, min(int(max_results), max(6, min(10, int(max_results))))),
                max(1, int(max_rounds)),
                min(int(max_graph_depth), 1),
            )
        if need.deficit_kind in {'skill_gap', 'tool_gap', 'capability_gap', 'routing_uncertainty'} or 'procedure' in need.required_kinds:
            return RetrievalPolicyDecision(
                'procedural',
                max(1, min(int(max_results), 6)),
                max(1, min(int(max_rounds), 2)),
                0,
            )
        return RetrievalPolicyDecision(
            'balanced',
            max(1, min(int(max_results), 5)),
            max(1, min(int(max_rounds), 2)),
            min(int(max_graph_depth), 1),
        )


@dataclass(frozen=True, slots=True)
class RetrievalReceipt:
    need: CognitiveRetrievalNeed
    rounds: int
    source_calls: int
    retrieved_artifact_ids: tuple[str, ...]
    accepted_artifact_ids: tuple[str, ...]
    superseded_artifact_ids: tuple[str, ...]
    conflicts: tuple[EvidenceConflict, ...]
    attachments: tuple[CognitiveAttachment, ...]
    sufficient: bool
    evidence_score: float
    source_diversity: int
    graph_hops_used: int
    association_hits: int
    cues: frozenset[str]
    stop_reason: str
    policy_mode: str
    policy_seed_k: int
    policy_graph_depth: int
    source_failures: tuple[str, ...] = ()


class CognitiveRetrievalFabric:
    trainable_parameter_count = 0

    def __init__(
        self,
        sources: Sequence[ArtifactSource],
        *,
        max_rounds: int = 3,
        max_results: int = 12,
        max_graph_depth: int = 2,
        max_graph_nodes: int = 16,
        max_attachments: int = 8,
        max_attachment_chars: int = 8000,
        compiler: CognitiveQueryCompiler | None = None,
        credit: AssociationCreditGraph | None = None,
        policy: AdaptiveRetrievalPolicy | None = None,
    ) -> None:
        if int(max_rounds) < 1 or int(max_results) < 1 or int(max_graph_depth) < 0 or int(max_graph_nodes) < 0:
            raise ValueError('invalid retrieval budgets')
        self.max_rounds = int(max_rounds)
        self.max_results = int(max_results)
        self.max_graph_depth = int(max_graph_depth)
        self.max_graph_nodes = int(max_graph_nodes)
        self.compiler = compiler or CognitiveQueryCompiler()
        self.retriever = FederatedRetriever(sources)
        self.fusion = EpistemicFusion()
        self.credit = credit or AssociationCreditGraph()
        self.policy = policy or AdaptiveRetrievalPolicy()
        self.workspace = AttachmentWorkspace(max_attachments=max_attachments, max_chars=max_attachment_chars)

    def _expand_graph(self, hits: Sequence[RetrievalHit], *, max_depth: int | None = None) -> tuple[list[RetrievalHit], int]:
        graph_depth_limit = self.max_graph_depth if max_depth is None else max(0, min(self.max_graph_depth, int(max_depth)))
        if graph_depth_limit <= 0 or self.max_graph_nodes <= 0:
            return [], 0
        hit_by_id = {hit.artifact.artifact_id: hit for hit in hits}
        emitted = set(hit_by_id)
        frontier = [
            (hit, 0, frozenset({hit.artifact.artifact_id}))
            for hit in hits[: min(4, len(hits))]
        ]
        out: list[RetrievalHit] = []
        max_depth = 0
        traversed_edges = 0
        while frontier and traversed_edges < self.max_graph_nodes:
            parent, depth, path = frontier.pop(0)
            if depth >= graph_depth_limit:
                continue
            for relation in sorted(parent.artifact.relations, key=lambda row: (-row.weight, row.relation, row.target_id)):
                if relation.target_id in path:
                    continue
                resolved = self.retriever.resolve(relation.target_id)
                if not resolved:
                    continue
                traversed_edges += 1
                source_id, artifact = resolved[0]
                next_depth = depth + 1
                max_depth = max(max_depth, next_depth)
                existing = hit_by_id.get(artifact.artifact_id)
                if existing is not None:
                    graph_parent = RetrievalHit(
                        artifact=existing.artifact,
                        source_id=existing.source_id,
                        score=max(existing.score, parent.score * (0.72 ** next_depth) * relation.weight),
                        branch_types=existing.branch_types + ('graph',),
                        branch_queries=existing.branch_queries + (relation.relation,),
                        lexical_score=existing.lexical_score,
                        semantic_score=existing.semantic_score,
                        symbol_score=existing.symbol_score,
                        tag_score=existing.tag_score,
                        kind_score=existing.kind_score,
                        association_score=existing.association_score,
                        graph_depth=max(existing.graph_depth, next_depth),
                        rationale=existing.rationale + (f'graph:{relation.relation}', f'from:{parent.artifact.artifact_id}'),
                    )
                else:
                    score = max(0.01, parent.score * (0.72 ** next_depth) * relation.weight + 0.2 * artifact.trust_score)
                    graph_parent = RetrievalHit(
                        artifact=artifact,
                        source_id=source_id,
                        score=score,
                        branch_types=('graph',),
                        branch_queries=(relation.relation,),
                        lexical_score=0.0,
                        semantic_score=0.0,
                        symbol_score=0.0,
                        tag_score=0.0,
                        kind_score=0.0,
                        graph_depth=next_depth,
                        rationale=(f'graph:{relation.relation}', f'from:{parent.artifact.artifact_id}'),
                    )
                    if artifact.artifact_id not in emitted:
                        out.append(graph_parent)
                        emitted.add(artifact.artifact_id)
                        hit_by_id[artifact.artifact_id] = graph_parent
                frontier.append((graph_parent, next_depth, path | {artifact.artifact_id}))
                if traversed_edges >= self.max_graph_nodes:
                    break
        return out, max_depth

    @staticmethod
    def _anchors(hits: Sequence[RetrievalHit]) -> tuple[str, ...]:
        anchors: list[str] = []
        for hit in hits[:5]:
            anchors.extend(sorted(hit.artifact.symbols))
            anchors.extend(sorted(hit.artifact.tags))
            match = _CLAIM.match(hit.artifact.text.strip())
            if match:
                anchors.extend((match.group(1).strip(), match.group(2).strip(), match.group(3).strip()))
        return tuple(dict.fromkeys(anchor for anchor in anchors if anchor))

    @staticmethod
    def _kind_coverage(need: CognitiveRetrievalNeed, hits: Sequence[RetrievalHit]) -> bool:
        if not need.required_kinds:
            return bool(hits)
        present = {hit.artifact.kind for hit in hits}
        return need.required_kinds <= present

    def retrieve(self, need: CognitiveRetrievalNeed) -> RetrievalReceipt:
        self.workspace.clear()
        cues = need.cues()
        association = self.credit.candidates(cues)
        association_hits = 0
        source_calls = 0
        source_failures: list[str] = []
        for source in self.retriever.sources:
            drain = getattr(source, 'drain_errors', None)
            if callable(drain):
                drain()
        retrieved_ids: list[str] = []
        accumulated: dict[tuple[str, str], RetrievalHit] = {}
        graph_hops_used = 0
        fusion = FusionResult((), (), (), (), 0, 0.0)
        stop_reason = 'round_budget_exhausted'
        branches = self.compiler.compile(need)
        actual_rounds = 0
        policy = self.policy.decide(
            need,
            max_results=self.max_results,
            max_rounds=self.max_rounds,
            max_graph_depth=self.max_graph_depth,
        )

        for round_index in range(1, policy.max_rounds + 1):
            actual_rounds = round_index
            round_hits = list(self.retriever.retrieve(branches, k=policy.seed_k, association=association))
            for source in self.retriever.sources:
                drain = getattr(source, 'drain_errors', None)
                if callable(drain):
                    for error in drain():
                        if error not in source_failures:
                            source_failures.append(error)
            source_calls += len(branches) * len(self.retriever.sources)
            association_hits += len({hit.artifact.artifact_id for hit in round_hits if hit.association_score > 0.0})

            # Credit can directly activate a previously verified artifact even if current lexical phrasing is weak.
            for artifact_id, activation in sorted(association.items(), key=lambda row: (-row[1], row[0])):
                for source_id, artifact in self.retriever.resolve(artifact_id):
                    key = (source_id, artifact_id)
                    if key not in {(hit.source_id, hit.artifact.artifact_id) for hit in round_hits}:
                        round_hits.append(RetrievalHit(
                            artifact=artifact,
                            source_id=source_id,
                            score=1.25 * activation + 0.45 * artifact.trust_score,
                            branch_types=('association',),
                            branch_queries=tuple(sorted(cues)),
                            lexical_score=0.0,
                            semantic_score=0.0,
                            symbol_score=0.0,
                            tag_score=0.0,
                            kind_score=1.0 if not need.required_kinds or artifact.kind in need.required_kinds else 0.0,
                            association_score=activation,
                            rationale=('association-credit',),
                        ))
                        association_hits += 1

            graph_hits, graph_depth = self._expand_graph(round_hits, max_depth=policy.graph_depth)
            graph_hops_used = max(graph_hops_used, graph_depth)
            round_hits.extend(graph_hits)
            for hit in round_hits:
                key = (hit.source_id, hit.artifact.artifact_id)
                previous = accumulated.get(key)
                if previous is None or hit.score > previous.score:
                    accumulated[key] = hit
                if hit.artifact.artifact_id not in retrieved_ids:
                    retrieved_ids.append(hit.artifact.artifact_id)

            combined = sorted(accumulated.values(), key=lambda hit: (-hit.score, -hit.artifact.trust_score, hit.artifact.artifact_id, hit.source_id))
            fusion = self.fusion.fuse(combined)
            kind_coverage = self._kind_coverage(need, fusion.accepted_hits)
            sufficient = kind_coverage and fusion.evidence_score >= need.min_sufficiency
            if sufficient:
                stop_reason = 'evidence_sufficient'
                break
            anchors = self._anchors(fusion.accepted_hits)
            if not anchors:
                stop_reason = 'no_novel_anchors'
                break
            branches = self.compiler.follow_up(need, anchors, round_index=round_index)

        accepted = list(fusion.accepted_hits)
        max_score = max((hit.score for hit in accepted), default=1.0)
        for hit in accepted:
            normalized = 0.0 if max_score <= 0 else min(1.0, max(0.0, hit.score / max_score))
            association_bonus = max(0.0, self.credit.activation(cues, hit.artifact.artifact_id))
            activation = 0.55 * normalized + 0.25 * hit.artifact.trust_score + 0.20 * min(1.0, association_bonus)
            self.workspace.attach(hit.artifact, activation=activation, rationale=hit.rationale + hit.branch_types)
        attachments = self.workspace.active()
        sufficient = self._kind_coverage(need, fusion.accepted_hits) and fusion.evidence_score >= need.min_sufficiency
        return RetrievalReceipt(
            need=need,
            rounds=actual_rounds,
            source_calls=source_calls,
            retrieved_artifact_ids=tuple(retrieved_ids),
            accepted_artifact_ids=fusion.accepted_artifact_ids,
            superseded_artifact_ids=fusion.superseded_artifact_ids,
            conflicts=fusion.conflicts,
            attachments=attachments,
            sufficient=sufficient,
            evidence_score=fusion.evidence_score,
            source_diversity=fusion.source_diversity,
            graph_hops_used=graph_hops_used,
            association_hits=association_hits,
            cues=cues,
            stop_reason=stop_reason,
            policy_mode=policy.mode,
            policy_seed_k=policy.seed_k,
            policy_graph_depth=policy.graph_depth,
            source_failures=tuple(source_failures),
        )

    def record_outcome(self, receipt: RetrievalReceipt, *, success: bool, used_artifact_ids: Iterable[str] | None = None) -> None:
        used = tuple(receipt.accepted_artifact_ids if used_artifact_ids is None else map(str, used_artifact_ids))
        self.credit.record(receipt.cues, used, success=bool(success))


@dataclass(frozen=True, slots=True)
class ReflexRetrievalReceipt:
    triggered: bool
    deficit_kind: str | None
    success: bool
    reason: str
    retrieval: RetrievalReceipt | None


class CognitiveRetrievalReflexController:
    """Continuously bind retrieval to objective cognition signals.

    The controller observes the public R2.53 snapshot, chooses a retrieval-relevant deficit, and
    executes the safe R2.54 bridge automatically. It intentionally ignores raw model confidence
    as an authority: a high-confidence model can still trigger retrieval from objective evidence gaps.
    """

    trainable_parameter_count = 0
    _priority = (
        'knowledge_gap',
        'temporal_conflict',
        'contradiction',
        'code_analysis_gap',
        'representation_mismatch',
        'skill_gap',
        'tool_gap',
        'capability_gap',
        'episodic_gap',
        'counterexample_gap',
        'routing_uncertainty',
        'information_acquisition_gap',
    )

    def __init__(self, fabric: CognitiveRetrievalFabric, detector=None) -> None:
        from .r253_external_cognition import CognitiveDeficitDetector
        self.fabric = fabric
        self.detector = detector or CognitiveDeficitDetector()

    def run(self, state, snapshot) -> ReflexRetrievalReceipt:
        signals = self.detector.detect(snapshot)
        by_kind: dict[str, object] = {}
        for signal in signals:
            by_kind.setdefault(signal.kind, signal)
        selected = None
        for kind in self._priority:
            if kind in by_kind:
                selected = by_kind[kind]
                break
        if selected is None:
            return ReflexRetrievalReceipt(False, None, True, 'no_retrieval_relevant_deficit', None)
        operator = make_r254_cognitive_retrieval_operator(self.fabric)
        raw = dict(operator.executor(state, snapshot, selected))
        public = state.context.get('r254_retrieval_receipt')
        retrieval = None
        # Preserve the typed receipt through a side channel when possible. The public state keeps
        # only JSON-safe evidence; the controller return keeps the exact typed receipt unavailable
        # to the model unless the host chooses to expose it.
        query = str(state.context.get('knowledge_query', '')).strip()
        if not query:
            query = ' '.join(map(str, snapshot.unresolved_requirements)).strip() or snapshot.objective
        if raw.get('success'):
            # Reconstructing by another retrieval would spend budget; instead expose only the public
            # attachment view in working state and return success without a duplicate host call.
            state.context['r254_reflex_attachments'] = list((public or {}).get('attachments', ())) if isinstance(public, Mapping) else []
        return ReflexRetrievalReceipt(
            True,
            selected.kind,
            bool(raw.get('success', False)),
            str(raw.get('reason', 'retrieval_executed' if raw.get('success') else 'retrieval_failed')),
            retrieval,
        )


def make_r254_cognitive_retrieval_operator(
    fabric: CognitiveRetrievalFabric,
    *,
    operator_id: str = 'knowledge.r254_federated_cognitive_retrieve',
):
    """Expose the R2.54 retrieval fabric as a safe R2.53 primitive.

    Retrieved content is attached as evidence/data. The adapter never interprets retrieved procedure
    step names as executable capabilities and never registers remote code.
    """
    from .r253_external_cognition import CognitiveOperatorSpec

    def execute(state, snapshot, signal):
        query = str(state.context.get('knowledge_query', '')).strip()
        if not query:
            query = ' '.join(map(str, snapshot.unresolved_requirements)).strip() or snapshot.objective
        context_tags = frozenset(map(str, state.context.get('retrieval_context_tags', ())))
        symbols = frozenset(map(str, state.context.get('retrieval_symbols', ())))
        required_kinds = frozenset(map(str, state.context.get('retrieval_required_kinds', ())))
        if signal.kind in {'skill_gap', 'tool_gap'} and not required_kinds:
            required_kinds = frozenset({'procedure'})
        need = CognitiveRetrievalNeed(
            objective=snapshot.objective,
            deficit_kind=signal.kind,
            query=query,
            unresolved_requirements=tuple(map(str, snapshot.unresolved_requirements)),
            context_tags=context_tags,
            symbols=symbols,
            required_kinds=required_kinds,
            representation_id=snapshot.representation_id,
            min_sufficiency=0.45 if snapshot.evidence_coverage < 0.25 else 0.58,
        )
        receipt = fabric.retrieve(need)
        if not receipt.attachments:
            return {
                'success': False,
                'reason': receipt.stop_reason,
                'updates': {'r254_retrieval_receipt': _receipt_public(receipt)},
                'evidence': (),
                'provides': set(),
            }
        for attachment in receipt.attachments:
            if attachment.artifact_id not in state.evidence:
                state.evidence.append(attachment.artifact_id)
        procedure_candidates = [
            {
                'artifact_id': row.artifact_id,
                'kind': row.kind,
                'source_uri': row.source_uri,
                'version': row.version,
                'activation': row.activation,
                'trust_score': row.trust_score,
                'rationale': tuple(row.rationale),
                'content': row.text,
                'content_sha256': row.content_sha256,
            }
            for row in receipt.attachments if row.kind == 'procedure'
        ]
        state.context.update({
            'r254_retrieval_receipt': _receipt_public(receipt),
            'knowledge_chunk_ids': tuple(row.artifact_id for row in receipt.attachments),
            'knowledge_texts': tuple(row.text for row in receipt.attachments),
            'retrieved_procedure_candidates': procedure_candidates,
        })
        return {
            'success': True,
            'updates': {
                'r254_retrieval_receipt': _receipt_public(receipt),
                'knowledge_chunk_ids': tuple(row.artifact_id for row in receipt.attachments),
                'knowledge_texts': tuple(row.text for row in receipt.attachments),
                'retrieved_procedure_candidates': procedure_candidates,
            },
            'evidence': tuple(row.artifact_id for row in receipt.attachments),
            'provides': {'evidence', 'external_knowledge'},
        }

    return CognitiveOperatorSpec(
        operator_id=operator_id,
        family='factual_knowledge',
        tags=frozenset({'knowledge', 'retrieval', 'cognition-time', 'federated', 'graph', 'procedural'}),
        requires=frozenset(),
        provides=frozenset({'evidence', 'external_knowledge'}),
        cost=1.4,
        risk=0.01,
        side_effect_class='state_only',
        version='1',
        source_uri='nolane://r254-federated-cognitive-retrieval',
        executor=execute,
    )


def _receipt_public(receipt: RetrievalReceipt) -> dict[str, object]:
    return {
        'rounds': receipt.rounds,
        'source_calls': receipt.source_calls,
        'retrieved_artifact_ids': list(receipt.retrieved_artifact_ids),
        'accepted_artifact_ids': list(receipt.accepted_artifact_ids),
        'superseded_artifact_ids': list(receipt.superseded_artifact_ids),
        'conflicts': [
            {'subject': row.subject, 'relation': row.relation, 'objects': list(row.objects), 'artifact_ids': list(row.artifact_ids)}
            for row in receipt.conflicts
        ],
        'attachments': [
            {
                'artifact_id': row.artifact_id,
                'kind': row.kind,
                'source_uri': row.source_uri,
                'version': row.version,
                'activation': row.activation,
                'trust_score': row.trust_score,
                'content_sha256': row.content_sha256,
            }
            for row in receipt.attachments
        ],
        'sufficient': receipt.sufficient,
        'evidence_score': receipt.evidence_score,
        'source_diversity': receipt.source_diversity,
        'graph_hops_used': receipt.graph_hops_used,
        'association_hits': receipt.association_hits,
        'stop_reason': receipt.stop_reason,
        'policy_mode': receipt.policy_mode,
        'policy_seed_k': receipt.policy_seed_k,
        'policy_graph_depth': receipt.policy_graph_depth,
        'source_failures': list(receipt.source_failures),
    }


__all__ = [
    'ArtifactRelation',
    'RetrievalArtifact',
    'make_artifact',
    'CognitiveRetrievalNeed',
    'QueryBranch',
    'CognitiveQueryCompiler',
    'SourceHit',
    'RetrievalHit',
    'ArtifactSource',
    'InMemoryArtifactSource',
    'CallbackArtifactSource',
    'FederatedRetriever',
    'EvidenceConflict',
    'FusionResult',
    'EpistemicFusion',
    'CognitiveAttachment',
    'AttachmentWorkspace',
    'AssociationCreditGraph',
    'RetrievalPolicyDecision',
    'AdaptiveRetrievalPolicy',
    'RetrievalReceipt',
    'ReflexRetrievalReceipt',
    'CognitiveRetrievalReflexController',
    'CognitiveRetrievalFabric',
    'make_r254_cognitive_retrieval_operator',
]
