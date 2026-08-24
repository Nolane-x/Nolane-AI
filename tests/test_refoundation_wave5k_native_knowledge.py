from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT


ROOT = Path(__file__).resolve().parents[1]


def test_wave5k_historical_document_validation_and_deterministic_retrieval_oracle() -> None:
    from cogcoder.knowledge_store import InMemoryKnowledgeStore
    from cogcoder.knowledge_types import KnowledgeDocument

    with pytest.raises(ValueError, match="document fields must be non-empty"):
        KnowledgeDocument("", "memory://doc", "text")
    with pytest.raises(ValueError, match="document fields must be non-empty"):
        KnowledgeDocument("doc", "", "text")
    with pytest.raises(ValueError, match="document fields must be non-empty"):
        KnowledgeDocument("doc", "memory://doc", "   ")
    with pytest.raises(ValueError, match=r"trust_score must be in \[0,1\]"):
        KnowledgeDocument("doc", "memory://doc", "text", trust_score=1.01)

    documents = (
        KnowledgeDocument("doc-a", "memory://a", "alpha beta gamma " * 12, version="7", trust_score=0.9),
        KnowledgeDocument("doc-b", "memory://b", "delta epsilon alpha " * 10, version="2", trust_score=0.6),
    )
    store_a = InMemoryKnowledgeStore(documents, chunk_chars=64, overlap=8)
    store_b = InMemoryKnowledgeStore(documents, chunk_chars=64, overlap=8)
    assert store_a.trainable_parameter_count == 0

    with pytest.raises(ValueError, match="chunk_chars too small"):
        InMemoryKnowledgeStore(documents, chunk_chars=63)
    with pytest.raises(ValueError, match="query must be non-empty"):
        store_a.search("   ")
    with pytest.raises(ValueError, match="k must be positive"):
        store_a.search("alpha", k=0)

    first = store_a.search("alpha gamma", k=4)
    second = store_b.search("alpha gamma", k=4)
    assert first == second
    assert first
    for row in first:
        assert hashlib.sha256(row.text.encode()).hexdigest() == row.content_sha256
        expected_id = hashlib.sha256(
            f"{row.source_uri}|{row.version}|{row.start}|{row.content_sha256}".encode()
        ).hexdigest()[:24]
        assert row.chunk_id == expected_id
        assert 0.0 <= row.score <= 1.0
        assert row.lexical_score >= 0.0
        assert row.semantic_score >= 0.0
        assert 0.0 <= row.trust_score <= 1.0


def test_wave5k_historical_composite_dedup_and_ordering_oracle() -> None:
    from cogcoder.knowledge_store import CompositeKnowledgeStore, InMemoryKnowledgeStore
    from cogcoder.knowledge_types import KnowledgeDocument

    document = KnowledgeDocument("doc", "memory://same", "alpha beta gamma " * 20, trust_score=0.8)
    source_a = InMemoryKnowledgeStore((document,), chunk_chars=80, overlap=10)
    source_b = InMemoryKnowledgeStore((document,), chunk_chars=80, overlap=10)
    composite = CompositeKnowledgeStore((source_a, source_b))
    assert composite.trainable_parameter_count == 0

    rows = composite.search("alpha beta", k=6)
    assert rows
    assert len({row.content_sha256 for row in rows}) == len(rows)
    assert rows == sorted(rows, key=lambda row: (-row.score, -row.trust_score, row.chunk_id))


def test_wave5k_historical_evidence_ledger_oracle() -> None:
    from cogcoder.knowledge_ledger import EvidenceLedger
    from cogcoder.knowledge_types import EvidenceChunk

    def chunk(chunk_id: str, text: str, *, score: float = 0.8, trust: float = 0.9) -> EvidenceChunk:
        return EvidenceChunk(
            chunk_id,
            "doc",
            "memory://ledger",
            text,
            hashlib.sha256(text.encode()).hexdigest(),
            "1",
            0,
            len(text),
            score,
            score,
            0.0,
            trust,
        )

    ledger = EvidenceLedger()
    first = chunk("chunk-a", "Nolane --owner--> Agent-A", score=0.9)
    second = chunk("chunk-b", "Nolane --owner--> Agent-B", score=0.7)
    third = chunk("chunk-c", "unstructured evidence", score=0.95, trust=1.0)

    assert ledger.ingest(first)
    assert not ledger.ingest(first)
    with pytest.raises(ValueError, match="chunk id collision"):
        ledger.ingest(chunk("chunk-a", "different text"))

    tampered = EvidenceChunk(
        "tampered",
        "doc",
        "memory://ledger",
        "changed",
        hashlib.sha256(b"original").hexdigest(),
        "1",
        0,
        7,
        1.0,
        1.0,
        0.0,
        1.0,
    )
    with pytest.raises(ValueError, match="evidence content hash mismatch"):
        ledger.ingest(tampered)

    assert ledger.ingest(second)
    assert ledger.ingest(third)
    assert ledger.verify()
    conflicts = ledger.conflicts()
    assert len(conflicts) == 1
    assert conflicts[0].subject == "Nolane"
    assert conflicts[0].relation == "owner"
    assert conflicts[0].objects == ("Agent-A", "Agent-B")
    assert conflicts[0].chunk_ids == ("chunk-a", "chunk-b")
    assert tuple(row.chunk_id for row in ledger.chunks()) == ("chunk-a", "chunk-b", "chunk-c")

    bounded = ledger.working_set(max_chunks=2, max_chars=64)
    assert len(bounded) <= 2
    assert sum(len(row.text) for row in bounded) <= 64
    assert ledger.working_set(max_chunks=0) == []
    assert ledger.working_set(max_chars=0) == []


def test_wave5k_historical_callback_and_anchor_oracle() -> None:
    from cogcoder.knowledge_adapters import CallbackKnowledgeSource, extract_generic_query_anchors
    from cogcoder.knowledge_types import EvidenceChunk, KnowledgeDocument

    with pytest.raises(TypeError, match="search_fn must be callable"):
        CallbackKnowledgeSource(None)

    source = CallbackKnowledgeSource(
        lambda query, k: [KnowledgeDocument("doc", "memory://callback", "Nolane alpha beta gamma")]
    )
    assert source.trainable_parameter_count == 0
    rows = source.search("Nolane", k=3)
    assert len(rows) == 1
    assert rows[0].document_id == "doc"

    text = "verified evidence"
    good = EvidenceChunk(
        "good",
        "doc",
        "memory://callback",
        text,
        hashlib.sha256(text.encode()).hexdigest(),
        "1",
        0,
        len(text),
        0.5,
        0.4,
        0.1,
        0.8,
    )
    chunk_source = CallbackKnowledgeSource(lambda query, k: [good])
    assert chunk_source.search("evidence", k=1) == [good]

    bad = EvidenceChunk(
        "bad",
        "doc",
        "memory://callback",
        "tampered",
        hashlib.sha256(b"other").hexdigest(),
        "1",
        0,
        8,
        0.5,
        0.4,
        0.1,
        0.8,
    )
    with pytest.raises(ValueError, match="callback returned tampered evidence"):
        CallbackKnowledgeSource(lambda query, k: [bad]).search("evidence")
    with pytest.raises(TypeError, match="only KnowledgeDocument or only EvidenceChunk"):
        CallbackKnowledgeSource(lambda query, k: [KnowledgeDocument("d", "memory://d", "text"), good]).search("text")
    with pytest.raises(ValueError, match="query must be non-empty"):
        source.search(" ")
    with pytest.raises(ValueError, match="k must be positive"):
        source.search("Nolane", k=0)

    assert extract_generic_query_anchors(
        "The Nolane Engine uses EvidenceLedger with HTTPBridge and That Context. Nolane repeats."
    ) == ("Nolane", "Engine", "EvidenceLedger", "HTTPBridge", "Context")


def test_wave5k_knowledge_is_canonical_native_and_versioned() -> None:
    row = build_component_implementation_ledger()["external.knowledge"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.memory.knowledge"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.knowledge")) == "0.0.1"


def test_wave5k_public_knowledge_objects_bridge_to_canonical_identity() -> None:
    from cogcoder.knowledge_adapters import CallbackKnowledgeSource as LegacyCallback
    from cogcoder.knowledge_adapters import extract_generic_query_anchors as legacy_extract_anchors
    from cogcoder.knowledge_ledger import Conflict as LegacyConflict
    from cogcoder.knowledge_ledger import EvidenceLedger as LegacyLedger
    from cogcoder.knowledge_store import CompositeKnowledgeStore as LegacyComposite
    from cogcoder.knowledge_store import InMemoryKnowledgeStore as LegacyInMemory
    from cogcoder.knowledge_store import KnowledgeSource as LegacySource
    from cogcoder.knowledge_types import EvidenceChunk as LegacyChunk
    from cogcoder.knowledge_types import KnowledgeDocument as LegacyDocument
    from nolane.memory.knowledge import (
        CallbackKnowledgeSource,
        CompositeKnowledgeStore,
        Conflict,
        EvidenceChunk,
        EvidenceLedger,
        InMemoryKnowledgeStore,
        KnowledgeDocument,
        KnowledgeSource,
        extract_generic_query_anchors,
    )

    pairs = (
        (LegacyDocument, KnowledgeDocument),
        (LegacyChunk, EvidenceChunk),
        (LegacySource, KnowledgeSource),
        (LegacyInMemory, InMemoryKnowledgeStore),
        (LegacyComposite, CompositeKnowledgeStore),
        (LegacyConflict, Conflict),
        (LegacyLedger, EvidenceLedger),
        (LegacyCallback, CallbackKnowledgeSource),
        (legacy_extract_anchors, extract_generic_query_anchors),
    )
    assert all(legacy is canonical for legacy, canonical in pairs)
    for _, canonical in pairs:
        assert canonical.__module__ == "nolane.memory.knowledge"


def test_wave5k_canonical_knowledge_has_no_historical_or_r254_reverse_imports() -> None:
    import nolane.memory.knowledge as knowledge

    source_path = Path(knowledge.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        for module in modules:
            if module.startswith("cogcoder.knowledge") or module.startswith("cogcoder.r254") or "r254_cognitive_retrieval" in module:
                offenders.append(f"{node.lineno}:{module}")
    assert offenders == [], "canonical Knowledge reverse-imports historical authority: " + "; ".join(offenders)


def test_wave5k_inventory_maps_only_dedicated_knowledge_lineage() -> None:
    census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
    expected = "nolane/memory/knowledge.py"
    for path in (
        "cogcoder/knowledge_types.py",
        "cogcoder/knowledge_store.py",
        "cogcoder/knowledge_ledger.py",
        "cogcoder/knowledge_adapters.py",
    ):
        assert census.get(path).canonical_destination == expected
    assert census.get("cogcoder/r254_code_knowledge.py").canonical_destination != expected


def test_wave5k_debt_reduces_only_historical_knowledge() -> None:
    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1

    assert len(non_native) == 34
    assert counts == {
        "compatibility_facade": 25,
        "frozen_asset": 1,
        "historical_only": 6,
        "legacy_internal": 2,
    }
    assert ledger["external.knowledge"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["external.context"].status is ImplementationStatus.COMPATIBILITY_FACADE
    assert ledger["external.epistemic"].status is ImplementationStatus.HISTORICAL_ONLY
