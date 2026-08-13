# R2.1 Cognition-Time Retrieval Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a zero-parameter cognition-time retrieval fabric that can repeatedly access external knowledge during a reasoning/generation trajectory and outperform retrieve-once under matched retrieval budgets.

**Architecture:** Freeze accepted R2.0i. Add deterministic source, provenance ledger, retrieval microcycle, generation hook, and a procedural multi-hop knowledge benchmark. Retrieval is a runtime capability with no neural parameter growth; no-source mode is exact R2.0i fallback.

**Tech Stack:** Python 3.12 standard library, PyTorch only where existing R2.0i needs it, pytest, SHA-256, JSON/JSONL.

## Global Constraints
- R2.0i neural parameters remain exactly 78,779,253.
- New R2.1a trainable parameters = 0.
- No network dependency inside core modules.
- No hidden/private benchmark fields may enter retrieval queries.
- Every evidence item is provenance-bound and conflict-preserving.
- Retrieval may occur between any two cognition/generation steps.
- Same query/corpus/config must produce deterministic ranking.
- No-source integration must be behavior-identical to R2.0i.

---

### Task 1: Knowledge contracts and deterministic hybrid store
**Files:** Create `cogcoder/knowledge_types.py`, `cogcoder/knowledge_store.py`; test `tests/test_r21_knowledge_store.py`.
**Interfaces:** `KnowledgeDocument`, `EvidenceChunk`, `KnowledgeSource.search(query, k)`, `InMemoryKnowledgeStore`, `CompositeKnowledgeStore`.
- [ ] Write RED tests for deterministic ranking, lexical+semantic recovery, source hashes, dedupe, empty query rejection, and zero trainable state.
- [ ] Run focused test and confirm RED.
- [ ] Implement immutable contracts, deterministic chunking, BM25-like lexical score, hashed char-ngram vector score, reciprocal-rank fusion.
- [ ] Run focused test GREEN.

### Task 2: Provenance and contradiction ledger
**Files:** Create `cogcoder/knowledge_ledger.py`; test `tests/test_r21_knowledge_ledger.py`.
**Interfaces:** `EvidenceLedger.ingest`, `working_set`, `conflicts`, `verify`.
- [ ] RED tests: tampered content rejected, duplicate chunk idempotent, contradictory claims retained, bounded packet deterministic.
- [ ] Implement append-only ledger and simple normalized subject/relation/object claim fingerprints for explicit `A -> relation -> B` benchmark facts while leaving arbitrary text untouched.
- [ ] GREEN focused tests.

### Task 3: Retrieval microcycle and generation hook
**Files:** Create `cogcoder/retrieval_microcycle.py`, `cogcoder/generation_retrieval.py`; tests `tests/test_r21_retrieval_microcycle.py`, `tests/test_r21_generation_retrieval.py`.
**Interfaces:** `KnowledgeNeed`, `RetrievalState`, `CognitionTimeRetriever.step`, `GenerationRetrievalHook.before_step/after_step`.
- [ ] RED tests for retrieval on uncertainty/query drift, no retrieval when confidence high and no drift, anchor-based re-query, strict budget, deterministic stop, and retrieval occurring between synthetic token/generation steps.
- [ ] Implement minimal zero-param controller and hook.
- [ ] GREEN focused tests.

### Task 4: KFIGG-21 multi-hop retrieval benchmark
**Files:** Create `cogcoder/kfigg21.py`, `scripts/evaluate_r21_retrieval_gate.py`; test `tests/test_r21_kfigg21.py`.
**Interfaces:** `make_kfigg21_case`, `solve_retrieve_once`, `solve_interleaved`, `evaluate_kfigg21`.
- [ ] RED tests guaranteeing 2–4 hop chains, distractors, no answer in the question, exact answer verifier, matched top-k/call budgets.
- [ ] Implement deterministic generator and solvers. Interleaved solver must derive next query only from question + already retrieved evidence.
- [ ] GREEN focused tests.
- [ ] Preregister train/dev/fresh seeds and acceptance >=15 pp over retrieve-once, zero provenance failures.
- [ ] Run train gate; reject or proceed without tuning.
- [ ] If accepted, run DEV, write pre-fresh lock, then open FRESH once.

### Task 5: R2.0i opt-in integration and release
**Files:** Create `cogcoder/r21_runtime.py`, `tests/test_r21_r20i_integration.py`, `research/R2_1_REALITY_REPORT.md`, `research/R2_1_CURRENT_BEST.json`, `scripts/verify_r21_release.py`, `.github/workflows/r21-integrity.yml`.
**Interfaces:** `R21Runtime` wraps an accepted R2.0i runtime plus optional knowledge source.
- [ ] RED test no-source exact action/solve reproduction on locked smoke tasks.
- [ ] Implement opt-in knowledge runtime; do not alter accepted R2.0i weight.
- [ ] GREEN integration tests and compile gate.
- [ ] Publish source/results/docs to `main` only after evidence exists.
- [ ] Create COMPLETE ZIP containing one strongest weight + R2.1 runtime source/evidence; verify ZIP SHA/unzip test.
- [ ] Attempt Library persistence and report backend errors if any; never claim persistence without successful tool result.
