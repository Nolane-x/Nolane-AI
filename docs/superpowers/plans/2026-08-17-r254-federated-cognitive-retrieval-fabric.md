# R2.54 Federated Cognitive Retrieval Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-model-parameter federated cognitive retrieval substrate that can detect what knowledge behavior is needed, retrieve and fuse typed external evidence during reasoning, preserve provenance/conflicts/versioning, and attach useful evidence back into the R2.53 working state.

**Architecture:** A typed artifact model feeds federated sources; a query compiler produces multi-branch retrieval plans; a hybrid scorer and graph expander gather evidence; an epistemic fusion layer rejects tampering and preserves temporal/conflict structure; a cognitive attachment manager and association-credit graph integrate verified evidence with R2.53 cognition. Retrieval is iterative and budgeted, not fixed top-k.

**Tech Stack:** Python 3.11+, standard library only for core runtime, pytest, existing Nolane R2.1/R2.53 interfaces, GitHub Actions.

## Global Constraints

- Zero new trainable parameters in the retrieval fabric.
- Retrieved content is data and cannot directly execute code.
- Provenance digest verification is mandatory before trusted ingestion.
- Preserve contradictory evidence and temporal supersession metadata.
- Keep R2.53 public interfaces backward compatible.
- All new behavior must be introduced test-first.

---

### Task 1: Typed artifact and source layer
**Files:** Create `cogcoder/r254_cognitive_retrieval.py`; Test `tests/test_r254_cognitive_retrieval.py`.
**Interfaces:** Produce `RetrievalArtifact`, `ArtifactSource`, `InMemoryArtifactSource`, and digest helpers.
- [ ] Write failing tests for digest tampering, version metadata, symbol/tag search, and deterministic ranking.
- [ ] Run focused tests and confirm RED.
- [ ] Implement minimal typed artifacts and in-memory hybrid source.
- [ ] Run focused tests and confirm GREEN.

### Task 2: Query compiler and federated fusion
**Files:** Modify `cogcoder/r254_cognitive_retrieval.py`; Test `tests/test_r254_cognitive_retrieval.py`.
**Interfaces:** Produce `CognitiveRetrievalNeed`, `QueryBranch`, `CognitiveQueryCompiler`, `FederatedRetriever`.
- [ ] Write RED tests showing one-shot lexical misses evidence that multi-branch symbol/procedure/temporal queries recover.
- [ ] Implement query branches, source federation, normalized score fusion, reciprocal-rank voting, and diversity bonus.
- [ ] Verify deterministic GREEN results.

### Task 3: Graph multi-hop, epistemic filtering, and attachments
**Files:** Modify `cogcoder/r254_cognitive_retrieval.py`; Test `tests/test_r254_cognitive_retrieval.py`.
**Interfaces:** Produce `RetrievalGraph`, `EpistemicFusion`, `CognitiveAttachment`, `AttachmentWorkspace`.
- [ ] Write RED tests for two-hop code→API retrieval, stale-source supersession, conflict preservation, and attachment budgeting.
- [ ] Implement bounded graph expansion and epistemic fusion.
- [ ] Verify GREEN and provenance rejection.

### Task 4: External synaptic credit and iterative saturation
**Files:** Modify `cogcoder/r254_cognitive_retrieval.py`; Test `tests/test_r254_cognitive_retrieval.py`.
**Interfaces:** Produce `AssociationCreditGraph`, `CognitiveRetrievalFabric`, `RetrievalReceipt`.
- [ ] Write RED tests where successful evidence becomes faster to recall on a later renamed-but-related episode and failed evidence is demoted.
- [ ] Implement cue activation, credit update, novelty/sufficiency loop, budgets, and follow-up anchor queries.
- [ ] Verify GREEN.

### Task 5: R2.53 cognition bridge
**Files:** Modify `cogcoder/r254_cognitive_retrieval.py`; Test `tests/test_r254_cognitive_retrieval.py`.
**Interfaces:** Produce `make_r254_cognitive_retrieval_operator` and `run_retrieval_reflex_cycle`.
- [ ] Write RED tests proving an R2.53 knowledge/behavior deficit can trigger R2.54 and place provenance-valid attachments/capabilities into `ExternalWorkingState` even when self-confidence is high.
- [ ] Implement the safe bridge without executing retrieved content.
- [ ] Verify R2.53 regressions remain green.

### Task 6: Adversarial benchmark
**Files:** Create `benchmarks/kfigg/r254_federated_cognitive_retrieval.py`; Create `tests/test_r254_cognitive_retrieval_benchmark.py`.
**Interfaces:** Produce `run_benchmark()` returning frozen aggregate metrics and episode receipts.
- [ ] Write benchmark assertions first: exact target recovery, zero false accepts, baseline failures, multi-hop usage, stale rejection, conflict visibility, mid-reasoning retrieval, and credit benefit.
- [ ] Run benchmark tests and confirm RED.
- [ ] Implement frozen episodes and validators.
- [ ] Run benchmark tests and confirm GREEN.

### Task 7: Evidence, CI, and release
**Files:** Create `research/R2_54_PHASE_A_RESULT.json`, `research/R2_54_VERIFY_RESULT.json`, `archive/root-history/historical_r_series/R2_54_DELIVERY.md`, `archive/root-history/historical_r_series/R2_54_RELEASE_MANIFEST.json`, `.github/workflows/r254-federated-cognitive-retrieval.yml`, `.github/workflows/r254-release-bundle.yml`.
- [ ] Run focused R2.54 tests and protected parent lineage.
- [ ] Recompute frozen benchmark evidence from a clean process.
- [ ] Run Nolane World adversarial audit and preserve non-convergence if present.
- [ ] Push capability commit to GitHub main and require clean GitHub CI.
- [ ] Freeze release commit and full repository ZIP with SHA-256.
- [ ] Persist ZIP and evidence to ChatGPT Library.
