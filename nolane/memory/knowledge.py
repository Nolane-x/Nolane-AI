from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.knowledge"
COMPONENT_VERSION = "0.0.2"
MIGRATED_FROM = "cogcoder.knowledge_types"
MIGRATED_SOURCES = (
    "cogcoder/knowledge_types.py",
    "cogcoder/knowledge_store.py",
    "cogcoder/knowledge_ledger.py",
    "cogcoder/knowledge_adapters.py",
)

RELATION_SEMANTICS_PROTOCOL = "relation-semantics-registry-v1"
RELATION_SEMANTICS_PROJECTION_PROTOCOL = "relation-semantics-projection-v1"


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    source_uri: str
    text: str
    version: str = "1"
    trust_score: float = 1.0

    def __post_init__(self) -> None:
        if not self.document_id or not self.source_uri or not self.text.strip():
            raise ValueError("document fields must be non-empty")
        if not 0.0 <= float(self.trust_score) <= 1.0:
            raise ValueError("trust_score must be in [0,1]")


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    document_id: str
    source_uri: str
    text: str
    content_sha256: str
    version: str
    start: int
    end: int
    score: float
    lexical_score: float
    semantic_score: float
    trust_score: float


_TOKEN = re.compile(r"[\w]+", re.UNICODE)


def _terms(text: str) -> list[str]:
    return [value.casefold() for value in _TOKEN.findall(text)]


def _ngrams(text: str, n: int = 3) -> Counter[str]:
    normalized = " ".join(_terms(text))
    return Counter(normalized[index : index + n] for index in range(max(0, len(normalized) - n + 1)))


def _cos(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


class KnowledgeSource(Protocol):
    def search(self, query: str, k: int = 5) -> list[EvidenceChunk]: ...


class InMemoryKnowledgeStore:
    trainable_parameter_count = 0

    def __init__(
        self,
        documents: Sequence[KnowledgeDocument],
        *,
        chunk_chars: int = 800,
        overlap: int = 80,
    ) -> None:
        if chunk_chars < 64:
            raise ValueError("chunk_chars too small")
        self._rows = []
        for document in documents:
            start = 0
            while start < len(document.text):
                end = min(len(document.text), start + chunk_chars)
                text = document.text[start:end]
                content_sha256 = hashlib.sha256(text.encode()).hexdigest()
                chunk_id = hashlib.sha256(
                    f"{document.source_uri}|{document.version}|{start}|{content_sha256}".encode()
                ).hexdigest()[:24]
                self._rows.append(
                    (
                        document,
                        start,
                        end,
                        text,
                        content_sha256,
                        chunk_id,
                        _terms(text),
                        _ngrams(text),
                    )
                )
                if end == len(document.text):
                    break
                start = max(start + 1, end - overlap)
        self._df = Counter()
        for row in self._rows:
            self._df.update(set(row[6]))
        self._avgdl = sum(len(row[6]) for row in self._rows) / max(1, len(self._rows))

    def search(self, query: str, k: int = 5) -> list[EvidenceChunk]:
        if not query.strip():
            raise ValueError("query must be non-empty")
        if k < 1:
            raise ValueError("k must be positive")
        query_terms = _terms(query)
        query_ngrams = _ngrams(query)
        row_count = max(1, len(self._rows))
        scored = []
        for row in self._rows:
            document, start, end, text, content_sha256, chunk_id, terms, ngrams = row
            term_frequency = Counter(terms)
            document_length = max(1, len(terms))
            lexical = 0.0
            for term in query_terms:
                document_frequency = self._df.get(term, 0)
                inverse_document_frequency = math.log(
                    1 + (row_count - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                frequency = term_frequency.get(term, 0)
                lexical += (
                    inverse_document_frequency
                    * (frequency * 2.2)
                    / (
                        frequency
                        + 1.2
                        * (
                            1
                            - 0.75
                            + 0.75 * document_length / max(1e-9, self._avgdl)
                        )
                    )
                    if frequency
                    else 0.0
                )
            semantic = _cos(query_ngrams, ngrams)
            raw = lexical + 2.0 * semantic
            utility = raw + 0.25 * float(document.trust_score)
            scored.append((utility, lexical, semantic, float(document.trust_score), chunk_id, row))
        scored.sort(key=lambda value: (-value[0], -value[3], value[4]))
        top = scored[:k]
        maximum_raw = max([value[0] for value in top] or [1.0])
        output = []
        for raw, lexical, semantic, _trust, chunk_id, row in top:
            document, start, end, text, content_sha256, _, _, _ = row
            normalized = 0.0 if maximum_raw <= 0 else min(1.0, max(0.0, raw / maximum_raw))
            output.append(
                EvidenceChunk(
                    chunk_id,
                    document.document_id,
                    document.source_uri,
                    text,
                    content_sha256,
                    document.version,
                    start,
                    end,
                    normalized,
                    float(lexical),
                    float(semantic),
                    float(document.trust_score),
                )
            )
        return output


class CompositeKnowledgeStore:
    trainable_parameter_count = 0

    def __init__(self, sources: Sequence[KnowledgeSource]) -> None:
        self.sources = tuple(sources)

    def search(self, query: str, k: int = 5) -> list[EvidenceChunk]:
        rows = []
        for source in self.sources:
            rows.extend(source.search(query, k=k))
        best: dict[str, EvidenceChunk] = {}
        for row in rows:
            previous = best.get(row.content_sha256)
            if previous is None or (row.score, row.trust_score, row.chunk_id) > (
                previous.score,
                previous.trust_score,
                previous.chunk_id,
            ):
                best[row.content_sha256] = row
        return sorted(best.values(), key=lambda row: (-row.score, -row.trust_score, row.chunk_id))[:k]


_CLAIM = re.compile(r"^\s*(.+?)\s+--([^>-]+)-->\s+(.+?)\s*$")


@dataclass(frozen=True)
class Conflict:
    subject: str
    relation: str
    objects: tuple[str, ...]
    chunk_ids: tuple[str, ...]


class EvidenceLedger:
    def __init__(self) -> None:
        self._chunks: dict[str, EvidenceChunk] = {}
        self._claims = defaultdict(list)
        self._order: list[str] = []

    def __len__(self) -> int:
        return len(self._chunks)

    def ingest(self, chunk: EvidenceChunk) -> bool:
        if hashlib.sha256(chunk.text.encode()).hexdigest() != chunk.content_sha256:
            raise ValueError("evidence content hash mismatch")
        if chunk.chunk_id in self._chunks:
            if self._chunks[chunk.chunk_id] != chunk:
                raise ValueError("chunk id collision")
            return False
        self._chunks[chunk.chunk_id] = chunk
        self._order.append(chunk.chunk_id)
        match = _CLAIM.match(chunk.text.strip())
        if match:
            key = (match.group(1).strip(), match.group(2).strip())
            self._claims[key].append((match.group(3).strip(), chunk.chunk_id))
        return True

    def verify(self) -> bool:
        return all(
            hashlib.sha256(chunk.text.encode()).hexdigest() == chunk.content_sha256
            for chunk in self._chunks.values()
        )

    def conflicts(self) -> list[Conflict]:
        output = []
        for (subject, relation), values in sorted(self._claims.items()):
            objects = tuple(dict.fromkeys(value[0] for value in values))
            if len(objects) > 1:
                output.append(Conflict(subject, relation, objects, tuple(value[1] for value in values)))
        return output

    def semantic_conflicts(self, relation_semantics: "RelationSemanticsRegistry") -> list[Conflict]:
        """Return only conflicts authorized by current canonical relation semantics.

        The historical ``conflicts()`` API intentionally preserves its original same-key behavior.
        MULTI_VALUED relations coexist; UNSPECIFIED relations are ambiguity, not contradiction, and
        are handled fail-closed by the Truth/Epistemic v3 protocol.
        """
        if not isinstance(relation_semantics, RelationSemanticsRegistry):
            raise TypeError("semantic conflicts require canonical relation semantics registry")
        output = []
        for (subject, relation), values in sorted(self._claims.items()):
            objects = tuple(dict.fromkeys(value[0] for value in values))
            if len(objects) > 1 and relation_semantics.cardinality(relation) is RelationCardinality.EXCLUSIVE:
                output.append(Conflict(subject, relation, objects, tuple(value[1] for value in values)))
        return output

    def working_set(self, *, max_chunks: int = 8, max_chars: int = 6000) -> list[EvidenceChunk]:
        if max_chunks < 1 or max_chars < 1:
            return []
        rows = sorted(
            self._chunks.values(),
            key=lambda chunk: (
                -(chunk.score * chunk.trust_score),
                -chunk.trust_score,
                -chunk.score,
                chunk.chunk_id,
            ),
        )
        output = []
        characters = 0
        for chunk in rows:
            if len(output) >= max_chunks:
                break
            if characters + len(chunk.text) > max_chars:
                continue
            output.append(chunk)
            characters += len(chunk.text)
        return output

    def chunks(self) -> tuple[EvidenceChunk, ...]:
        return tuple(self._chunks[chunk_id] for chunk_id in self._order)


class CallbackKnowledgeSource:
    """Host bridge for live web/files/vector-DB/database retrieval.

    The adapter normalizes host results into provenance-bound EvidenceChunk
    records while retaining the deterministic historical R2 contract.
    """

    trainable_parameter_count = 0

    def __init__(self, search_fn) -> None:
        if not callable(search_fn):
            raise TypeError("search_fn must be callable")
        self.search_fn = search_fn

    def search(self, query: str, k: int = 5) -> list[EvidenceChunk]:
        if not query.strip():
            raise ValueError("query must be non-empty")
        if k < 1:
            raise ValueError("k must be positive")
        rows = list(self.search_fn(query, int(k)))
        if not rows:
            return []
        if all(isinstance(value, KnowledgeDocument) for value in rows):
            return InMemoryKnowledgeStore(rows, chunk_chars=800).search(query, k=min(k, len(rows)))
        if all(isinstance(value, EvidenceChunk) for value in rows):
            for value in rows:
                if hashlib.sha256(value.text.encode()).hexdigest() != value.content_sha256:
                    raise ValueError("callback returned tampered evidence")
            return sorted(rows, key=lambda value: (-value.score, -value.trust_score, value.chunk_id))[:k]
        raise TypeError("callback must return only KnowledgeDocument or only EvidenceChunk rows")


def extract_generic_query_anchors(text: str) -> tuple[str, ...]:
    """Return deterministic optional capitalized anchor hints for arbitrary prose."""

    stop = {
        "The",
        "This",
        "That",
        "These",
        "Those",
        "Where",
        "Which",
        "What",
        "When",
        "Who",
        "How",
        "A",
        "An",
    }
    return tuple(
        dict.fromkeys(
            token
            for token in re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", str(text))
            if token not in stop
        )
    )


def _relation_name(value: str) -> str:
    relation = str(value).strip()
    if not relation:
        raise ValueError("relation semantics relation must be explicit")
    return relation


def _relation_names(values: Sequence[str]) -> tuple[str, ...]:
    rows = tuple(sorted(_relation_name(value) for value in values))
    if len(set(rows)) != len(rows):
        raise ValueError("relation semantics projection relations must be unique")
    return rows


class RelationCardinality(str, Enum):
    EXCLUSIVE = "exclusive"
    MULTI_VALUED = "multi_valued"
    UNSPECIFIED = "unspecified"


@dataclass(frozen=True, slots=True)
class RelationSemanticsRevision:
    relation: str
    revision: int
    cardinality: RelationCardinality
    previous_digest: str
    digest: str

    @classmethod
    def create(
        cls,
        *,
        relation: str,
        revision: int,
        cardinality: RelationCardinality,
        previous_digest: str = "",
    ) -> "RelationSemanticsRevision":
        relation = _relation_name(relation)
        revision = int(revision)
        if revision < 1:
            raise ValueError("relation semantics revision must be positive")
        cardinality = RelationCardinality(cardinality)
        previous_digest = str(previous_digest).strip()
        if revision == 1 and previous_digest:
            raise ValueError("relation semantics first revision cannot declare predecessor")
        if revision > 1 and not previous_digest:
            raise ValueError("relation semantics later revision requires predecessor")
        payload = {
            "relation": relation,
            "revision": revision,
            "cardinality": cardinality.value,
            "previous_digest": previous_digest,
        }
        return cls(relation, revision, cardinality, previous_digest, canonical_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {
            "relation": self.relation,
            "revision": self.revision,
            "cardinality": self.cardinality.value,
            "previous_digest": self.previous_digest,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "RelationSemanticsRevision":
        row = cls.create(
            relation=str(state["relation"]),
            revision=int(state["revision"]),
            cardinality=RelationCardinality(str(state["cardinality"])),
            previous_digest=str(state.get("previous_digest", "")),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("relation semantics revision digest mismatch")
        return row


class RelationSemanticsRegistry:
    """Append-only cardinality authority owned by canonical ``external.knowledge``."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[RelationSemanticsRevision]] = {}

    def record(self, row: RelationSemanticsRevision) -> RelationSemanticsRevision:
        if not isinstance(row, RelationSemanticsRevision):
            raise TypeError("relation semantics registry accepts canonical revisions only")
        history = self._revisions.setdefault(row.relation, [])
        if not history:
            if row.revision != 1:
                raise ValueError("relation semantics revision sequence must start at 1")
            history.append(row)
            return row

        current = history[-1]
        if row.revision == current.revision:
            if row != current:
                raise ValueError("relation semantics revision collision")
            return current
        if row.revision != current.revision + 1:
            raise ValueError("relation semantics revision sequence must advance exactly once")
        if row.previous_digest != current.digest:
            raise ValueError("relation semantics predecessor mismatch")
        history.append(row)
        return row

    def revisions(self, relation: str) -> tuple[RelationSemanticsRevision, ...]:
        return tuple(self._revisions.get(_relation_name(relation), ()))

    def current(self, relation: str) -> RelationSemanticsRevision | None:
        rows = self.revisions(relation)
        return rows[-1] if rows else None

    def cardinality(self, relation: str) -> RelationCardinality:
        row = self.current(relation)
        return RelationCardinality.UNSPECIFIED if row is None else row.cardinality

    def projection_state(self, relations: Sequence[str]) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for relation in _relation_names(relations):
            current = self.current(relation)
            if current is None:
                rows.append({"relation": relation, "status": "unspecified"})
            else:
                rows.append({
                    "relation": relation,
                    "status": "registered",
                    "revision": current.to_state(),
                })
        return {"protocol": RELATION_SEMANTICS_PROJECTION_PROTOCOL, "relations": rows}

    def projection_digest(self, relations: Sequence[str]) -> str:
        return canonical_digest(self.projection_state(relations))

    def to_state(self) -> dict[str, Any]:
        rows = [
            row.to_state()
            for relation in sorted(self._revisions)
            for row in self._revisions[relation]
        ]
        return {"protocol": RELATION_SEMANTICS_PROTOCOL, "revisions": rows}

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "RelationSemanticsRegistry":
        if str(state.get("protocol", "")) != RELATION_SEMANTICS_PROTOCOL:
            raise ValueError("unsupported relation semantics registry protocol")
        parsed: list[RelationSemanticsRevision] = []
        seen: set[tuple[str, int]] = set()
        for value in state.get("revisions", ()):
            row = RelationSemanticsRevision.from_state(value)
            key = (row.relation, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized relation revision")
            seen.add(key)
            parsed.append(row)
        registry = cls()
        for row in sorted(parsed, key=lambda item: (item.relation, item.revision)):
            registry.record(row)
        return registry


__all__ = (
    "KnowledgeDocument",
    "EvidenceChunk",
    "KnowledgeSource",
    "InMemoryKnowledgeStore",
    "CompositeKnowledgeStore",
    "Conflict",
    "EvidenceLedger",
    "CallbackKnowledgeSource",
    "extract_generic_query_anchors",
    "RelationCardinality",
    "RelationSemanticsRevision",
    "RelationSemanticsRegistry",
    "RELATION_SEMANTICS_PROTOCOL",
    "RELATION_SEMANTICS_PROJECTION_PROTOCOL",
)
