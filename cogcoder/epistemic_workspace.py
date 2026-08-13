from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .knowledge_types import EvidenceChunk

_CLAIM = re.compile(r'^\s*(.+?)\s+--([^>-]+)-->\s+(.+?)\s*$')
_VERSION_TOKEN = re.compile(r'(\d+|[A-Za-z]+)')


def _version_key(version: str) -> tuple:
    parts = []
    for token in _VERSION_TOKEN.findall(str(version)):
        parts.append((0, int(token)) if token.isdigit() else (1, token.casefold()))
    return tuple(parts) or ((1, str(version).casefold()),)


@dataclass(frozen=True)
class ClaimRecord:
    subject: str
    relation: str
    object: str
    chunk_id: str
    source_uri: str
    version: str
    score: float
    trust_score: float


@dataclass(frozen=True)
class Belief:
    subject: str
    relation: str
    object: str | None
    confidence: float
    contested: bool
    independent_sources: int
    evidence_chunk_ids: tuple[str, ...]
    superseded_chunk_ids: tuple[str, ...]
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class EpistemicConflict:
    subject: str
    relation: str
    objects: tuple[str, ...]
    current_chunk_ids: tuple[str, ...]


class EpistemicWorkspace:
    trainable_parameter_count = 0

    def __init__(self, *, contest_margin: float = 0.08):
        self.contest_margin = float(contest_margin)
        self._chunks: dict[str, EvidenceChunk] = {}
        self._claims: list[ClaimRecord] = []

    def ingest(self, chunk: EvidenceChunk) -> bool:
        if hashlib.sha256(chunk.text.encode()).hexdigest() != chunk.content_sha256:
            raise ValueError('evidence content hash mismatch')
        previous = self._chunks.get(chunk.chunk_id)
        if previous is not None:
            if previous != chunk:
                raise ValueError('chunk id collision')
            return False
        self._chunks[chunk.chunk_id] = chunk
        match = _CLAIM.match(chunk.text.strip())
        if match:
            self._claims.append(ClaimRecord(match.group(1).strip(), match.group(2).strip(), match.group(3).strip(), chunk.chunk_id, chunk.source_uri, chunk.version, float(chunk.score), float(chunk.trust_score)))
        return True

    def ingest_many(self, chunks: Iterable[EvidenceChunk]) -> int:
        return sum(1 for chunk in chunks if self.ingest(chunk))

    def verify_provenance(self) -> bool:
        return all(hashlib.sha256(chunk.text.encode()).hexdigest() == chunk.content_sha256 for chunk in self._chunks.values())

    def _current_claims(self, subject: str, relation: str) -> tuple[list[ClaimRecord], list[ClaimRecord]]:
        relevant = [c for c in self._claims if c.subject == subject and c.relation == relation]
        by_source: dict[str, list[ClaimRecord]] = defaultdict(list)
        for claim in relevant:
            by_source[claim.source_uri].append(claim)
        current, superseded = [], []
        for rows in by_source.values():
            best_key = max(_version_key(row.version) for row in rows)
            latest = [row for row in rows if _version_key(row.version) == best_key]
            latest.sort(key=lambda row: (-row.trust_score, -row.score, row.chunk_id))
            current.append(latest[0])
            keep = latest[0].chunk_id
            superseded.extend(row for row in rows if row.chunk_id != keep)
        current.sort(key=lambda row: (row.source_uri, row.chunk_id))
        superseded.sort(key=lambda row: row.chunk_id)
        return current, superseded

    def belief(self, subject: str, relation: str) -> Belief:
        current, superseded = self._current_claims(subject, relation)
        if not current:
            return Belief(subject, relation, None, 0.0, True, 0, (), tuple(x.chunk_id for x in superseded), ())
        grouped: dict[str, list[ClaimRecord]] = defaultdict(list)
        for claim in current:
            grouped[claim.object].append(claim)
        scored = []
        for obj, rows in grouped.items():
            support = sum(0.7 * row.trust_score + 0.3 * row.score for row in rows)
            scored.append((support, len({row.source_uri for row in rows}), obj, rows))
        scored.sort(key=lambda row: (-row[0], -row[1], row[2]))
        top_support, sources, obj, rows = scored[0]
        total = sum(row[0] for row in scored)
        confidence = top_support / total if total > 0 else 0.0
        second = scored[1][0] if len(scored) > 1 else 0.0
        contested = len(scored) > 1 and (top_support - second) <= self.contest_margin * max(1.0, top_support)
        alternatives = tuple(row[2] for row in scored[1:])
        return Belief(subject, relation, obj, confidence, contested, sources, tuple(sorted(row.chunk_id for row in rows)), tuple(row.chunk_id for row in superseded), alternatives)

    def conflicts(self) -> tuple[EpistemicConflict, ...]:
        keys = sorted({(claim.subject, claim.relation) for claim in self._claims})
        out = []
        for subject, relation in keys:
            current, _ = self._current_claims(subject, relation)
            objects = tuple(sorted({claim.object for claim in current}))
            if len(objects) > 1:
                out.append(EpistemicConflict(subject, relation, objects, tuple(sorted(claim.chunk_id for claim in current))))
        return tuple(out)

    def missing_queries(self, subject: str, relation: str) -> tuple[str, ...]:
        belief = self.belief(subject, relation)
        if belief.object is None:
            return (f'{subject} {relation} current authoritative',)
        if belief.contested:
            options = ' '.join((belief.object,) + belief.alternatives)
            return (f'{subject} {relation} current authoritative resolve {options}',)
        return ()

    def chunks(self) -> tuple[EvidenceChunk, ...]:
        return tuple(self._chunks.values())
