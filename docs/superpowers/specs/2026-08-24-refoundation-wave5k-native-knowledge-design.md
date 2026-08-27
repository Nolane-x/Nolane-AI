# Refoundation Epoch 0 — Wave 5K Native Knowledge Design

## Parent acceptance
Wave 5K starts from exact hosted-green Wave 5J head `c694e27c89c5c86c139271e97c51ff76110cb842`.

## Objective
Establish the first canonical implementation authority for `external.knowledge` at `nolane.memory.knowledge` by reconstructing the dedicated historical R2 Knowledge lineage without conflating it with later Cognitive Retrieval / repository-indexing extensions.

`external.knowledge` enters Wave 5K as `HISTORICAL_ONLY`: it has no active facade, no canonical module, and no write authority. Therefore this wave is a forensic extraction into a new native owner, not a facade cutover.

The complete minimum semantic unit is:
- `KnowledgeDocument`
- `EvidenceChunk`
- `KnowledgeSource`
- `InMemoryKnowledgeStore`
- `CompositeKnowledgeStore`
- `Conflict`
- `EvidenceLedger`
- `CallbackKnowledgeSource`
- `extract_generic_query_anchors`

Historical implementation-only helpers needed to preserve exact behavior remain implementation details of the canonical owner.

## Source lineage
The authoritative behavior oracle for this extraction is the dedicated historical R2 lineage:
- `cogcoder/knowledge_types.py`
- `cogcoder/knowledge_store.py`
- `cogcoder/knowledge_ledger.py`
- `cogcoder/knowledge_adapters.py`

`cogcoder/r254_code_knowledge.py` is explicitly **not** part of the minimum Knowledge owner. It imports `r254_cognitive_retrieval` and produces `RetrievalArtifact`; that source is retained as historical provenance for the later Retrieval/Cognitive extraction rather than used to smuggle a reverse dependency into canonical Knowledge.

## Canonical boundary
The canonical owner is `nolane.memory.knowledge` with:
- `COMPONENT_ID = "external.knowledge"`
- `COMPONENT_VERSION = "0.0.1"`
- explicit migration provenance covering the four dedicated historical Knowledge sources.

The component manifest already defines `external.knowledge` as a `knowledge-v1` provenance-aware reusable knowledge fabric whose declared upstream component boundary is `external.evidence`. The native module may use standard-library primitives and already accepted canonical dependencies, but must not import executable authority from `cogcoder.knowledge_*`, `cogcoder.r254_*`, historical Cognitive Retrieval, Planning, Context, or other later subsystems.

Wave 5K preserves the historical `EvidenceChunk` API rather than replacing it with `EvidenceRecord`: the two records have different semantics. No artificial dependency is introduced merely to make the source import graph mirror the semantic component graph.

## Preserved behavior
Wave 5K preserves the dedicated R2 Knowledge behavior exactly:
- `KnowledgeDocument` requires non-empty document/source/text and trust in `[0,1]`;
- deterministic character-window chunking;
- SHA-256 content binding for every chunk;
- deterministic `chunk_id` from source URI, version, start offset, and content digest;
- zero trainable parameters for in-memory/composite/callback retrieval;
- lexical BM25-like scoring plus deterministic character-trigram cosine similarity;
- trust score contribution and deterministic score/tie ordering;
- non-empty query and positive `k` validation;
- composite cross-source deduplication by content SHA-256, retaining the highest utility/trust/id result;
- evidence-ledger tamper rejection and chunk-ID collision rejection;
- idempotent duplicate evidence ingest;
- deterministic extraction of `subject --relation--> object` conflicts;
- bounded working sets ordered by score × trust, then trust, score, and ID;
- insertion-order `chunks()` projection;
- callback normalization from homogeneous `KnowledgeDocument` or homogeneous `EvidenceChunk` rows;
- callback tamper detection and deterministic result ordering;
- deterministic generic capitalized query-anchor extraction with historical stop-token filtering.

No neural parameters, embeddings, network calls, database calls, or asynchronous side effects are added.

## Compatibility and provenance
After cutover:
- the four dedicated `cogcoder/knowledge_*.py` modules become compatibility bridges to exact canonical object identities where they expose public Knowledge API;
- compatibility bridges preserve historical import locations without retaining implementation authority;
- inventory provenance maps each of the four dedicated historical files to `nolane/memory/knowledge.py`;
- `cogcoder/r254_code_knowledge.py` receives no false canonical destination to `nolane/memory/knowledge.py`;
- no historical source is deleted or moved;
- `external.knowledge` moves from `HISTORICAL_ONLY` to `CANONICAL_NATIVE` with write authority;
- only `external.knowledge` advances from `0.0.0` to `0.0.1`.

## Non-goals
Wave 5K does not migrate R2.54 Cognitive Retrieval, Context, Planning, Epistemic, Cognitive Library, Causal/Experimentation, Individual Evolution, coding, execution, evaluation, or Neural subsystems. It does not introduce semantic/vector embeddings or redesign the historical ranking formula.

## RED contract
Before production code, Wave 5K tests must prove the historical behavior oracle remains green while the intended architecture is red because:
- `external.knowledge` is still `HISTORICAL_ONLY`;
- `nolane.memory.knowledge` does not yet own the classes/functions;
- version remains `0.0.0`;
- inventory lacks the four canonical destination receipts;
- non-native debt remains 35 rather than the conditional target 34.

## Conditional debt delta
Wave 5J accepted debt is:
- compatibility facade: 25
- legacy internal: 2
- historical only: 7
- frozen asset: 1
- total non-native: 35

If and only if the official repository audit proves this extraction closes exactly `external.knowledge`, Wave 5K target becomes:
- compatibility facade: **25**
- legacy internal: **2**
- historical only: **6**
- frozen asset: **1**
- total non-native: **34**

The generated audit, not this design document, is authoritative for the accepted debt count.

## Acceptance
One exact post-cleanup head must prove:
1. canonical Knowledge class/function ownership and `0.0.1` version;
2. exact historical bridge identities for all public dedicated R2 Knowledge surfaces;
3. preserved deterministic retrieval, provenance, ledger, conflict, bounded-working-set, callback and anchor behavior;
4. no executable reverse import from canonical Knowledge into historical Knowledge/R2.54/Cognitive Retrieval;
5. inventory provenance for the four dedicated sources without falsely claiming R2.54 code-knowledge ownership;
6. official audit freshness and the resulting debt delta;
7. no temporary write carrier remains;
8. full Refoundation workflow success on the exact clean head for Python 3.11 and 3.13, including zero-loss evidence, organization/campaign/execution regressions, and frozen Neural R2.3 contracts.
