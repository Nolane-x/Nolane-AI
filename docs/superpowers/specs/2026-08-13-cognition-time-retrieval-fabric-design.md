# R2.1 Cognition-Time Retrieval Fabric Design

## Goal
Give Nolane a zero-parameter external-knowledge fabric that can retrieve, verify, revise, and re-retrieve evidence *during* an ongoing cognition/generation trajectory rather than only once before reasoning.

## Constraints
- Accepted R2.0i neural core remains frozen at 78,779,253 effective parameters.
- R2.1a adds 0 neural parameters.
- With no registered knowledge source, R2.1 runtime must reproduce R2.0i behavior exactly.
- Retrieval inputs/outputs must be public and provenance-bound; no hidden benchmark fields.
- Every accepted evidence chunk carries source URI, content SHA-256, chunk ID, version, retrieval score, and trust score.
- Conflicting evidence is retained and surfaced; later retrieval cannot silently overwrite earlier contradictory evidence.
- The system must support retrieval between cognition/generation steps and repeated retrieval after query/belief drift.
- Host adapters may connect web, files, vector DBs, databases, or local corpora through one protocol.
- The built-in implementation has no network dependency and must be deterministic for a fixed corpus/query.
- Acceptance requires an interleaved-retrieval benchmark where retrieve-once cannot solve all multi-hop cases under the same per-call top-k budget.

## Architecture
1. `knowledge_types.py`: immutable knowledge/evidence contracts and provenance digests.
2. `knowledge_store.py`: source protocol plus deterministic in-memory and composite stores. Built-in retrieval uses hybrid BM25-like lexical scoring + hashed character-ngram cosine similarity; no trainable parameters.
3. `knowledge_ledger.py`: append-only evidence ledger with dedupe, conflict tracking, citation/provenance verification, and bounded working-set selection.
4. `retrieval_microcycle.py`: cognition-time controller. It decides when retrieval is useful from explicit uncertainty/query drift/novelty signals, issues queries, ingests evidence, extracts anchors, and can re-query using newly discovered anchors.
5. `generation_retrieval.py`: generic hook for any future decoder or current cognitive loop. Hosts call `before_step`/`after_step`; the fabric may retrieve between steps without assuming a particular tokenizer.
6. `kfigg21.py`: procedural knowledge maze. Each answer requires 2–4 hops across separate chunks, includes distractors and controlled contradictions, and exposes only a question + corpus. It compares retrieve-once, interleaved, and oracle-unbounded retrieval under matched top-k budgets.
7. R2.0i integration is opt-in. No knowledge source => exact fallback to accepted controller.

## Data flow
`current objective + partial derivation + uncertainty -> KnowledgeNeed -> source.search -> EvidenceChunk -> provenance verification -> EvidenceLedger -> anchor/query revision -> optional next microcycle -> bounded evidence packet -> cognition/generation step`.

The retrieval fabric never treats retrieval score as truth. Trust/provenance and contradiction state are separate fields. Retrieval can stop when no novel trusted evidence appears, when uncertainty is below threshold, when query drift is small, or when budget is exhausted.

## Evaluation
Primary internal gate: KFIGG-21 exact final-answer rate on fresh procedural worlds with identical corpus/top-k/retrieval-call budget. Acceptance requires interleaved retrieval to beat retrieve-once by >=15 absolute percentage points, no provenance failures, and <=1.5x median retrieved characters for solved examples after evidence compaction. This proves the retrieval mechanism, not AGI/general world knowledge.

External benchmark adapters remain a later gate; no claim of superiority to large models is permitted without matched head-to-head runs.
