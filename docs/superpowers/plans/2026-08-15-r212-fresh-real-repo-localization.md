# R2.12 Fresh Real-Repository Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and externally evaluate a leakage-controlled, zero-neural-parameter file localizer on 20 frozen real SWE-rebench V2 tasks.

**Architecture:** A deterministic issue-to-repository ranker extracts issue anchors, scores paths/content/symbols, and performs bounded dependency propagation. GitHub Actions separates prediction from gold scoring: the predictor sees only issue/repo/base-commit fields; the evaluator downloads the full immutable dataset only after predictions have been written.

**Tech Stack:** Python 3.11 standard library, git CLI, pytest, HTTPS + git CLI only in CI acquisition, GitHub Actions.

## Global Constraints

- Dataset: `SWE-rebench/SWE-rebench-V2/sample.json` at immutable Git commit `dd8b58f385783b189a96dd09c22153c843b0e2f9` (20 rows).
- Exactly 20 external tasks are required for an accepted result.
- Predictor must never receive `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, PR description, interfaces, or gold-derived metadata.
- R2.12 adds exactly 0 neural parameters; effective neural parameter count remains 79,450,489.
- Frozen thresholds from the design may not change after external scoring.
- External coding/AGI claims remain disabled.

---

### Task 1: Leak-safe task schema and gold parser

**Files:**
- Create: `cogcoder/r212_real_repo_protocol.py`
- Test: `tests/test_r212_real_repo_protocol.py`

**Interfaces:**
- Produces `PublicRepoTask`, `redact_dataset_row(row)`, `extract_gold_patch_files(patch)`.

- [ ] Write tests proving redaction retains only allowed fields and refuses missing required fields.
- [ ] Run `pytest -q tests/test_r212_real_repo_protocol.py` and observe RED because the module is absent.
- [ ] Implement immutable public-task schema and diff header parser.
- [ ] Re-run the test and require GREEN.

### Task 2: Deterministic real-repository ranker

**Files:**
- Create: `cogcoder/r212_real_repo_localizer.py`
- Test: `tests/test_r212_real_repo_localizer.py`

**Interfaces:**
- Consumes `PublicRepoTask` and a checked-out repository directory.
- Produces `FileScore` rows and `rank_repository_files(repo_dir, problem_statement, mode)` where mode is `path` or `hybrid`.

- [ ] Write RED tests for identifier/path anchors, content/symbol evidence, vendor exclusion, dependency propagation, filename-renaming determinism, and stable tie-breaking.
- [ ] Implement lexical tokenization, anchor extraction, tracked-file filtering, file scoring, local dependency resolution, and bounded propagation.
- [ ] Require all ranker tests GREEN.

### Task 3: Prediction and scoring separation

**Files:**
- Create: `scripts/r212_prepare_public_manifest.py`
- Create: `scripts/r212_predict_real_repo.py`
- Create: `scripts/r212_score_predictions.py`
- Test: `tests/test_r212_pipeline_contract.py`

**Interfaces:**
- Prepare writes only public fields to JSON.
- Predict consumes public JSON and emits top-20 path/hybrid rankings plus deterministic hashes.
- Score consumes finalized predictions plus full gold rows and emits aggregate/per-language metrics.

- [ ] Write RED tests proving prediction input with forbidden gold fields is rejected and scoring does not mutate predictions.
- [ ] Implement the three scripts and repository materialization with exact-commit verification and explicit failure records.
- [ ] Require contract tests GREEN.

### Task 4: Freeze protocol before external scoring

**Files:**
- Create: `research/R2_12_PRE_MEASURE_LOCK.json`
- Create: `tests/test_r212_lock_contract.py`

**Interfaces:**
- Lock records dataset/revision/split, source SHA-256 hashes, thresholds, file filters, candidate parameter count, and claim boundary.

- [ ] Compute SHA-256 of protocol/localizer/predictor/scorer source.
- [ ] Write the lock with acceptance thresholds from the design.
- [ ] Add and run a contract test that verifies hashes and exact thresholds.

### Task 5: External GitHub Actions gate

**Files:**
- Create: `.github/workflows/r212-real-repo-localization.yml`
- Create after measurement: `research/R2_12_PHASE_A_RESULT.json`
- Create after measurement: `R2_12_DELIVERY.md`
- Create after measurement: `R2_12_RELEASE_MANIFEST.json`
- Modify after accepted/rejected result: `README.md`

**Interfaces:**
- CI obtains the immutable dataset revision, redacts it, predicts on exact base commits, seals predictions, then separately scores against gold.

- [ ] Run local unit/regression tests and compile before integration.
- [ ] Commit the sealed source/lock/workflow to `main` without a result claim.
- [ ] Let GitHub Actions run the external panel and download its artifact.
- [ ] Compare CI result with lock; mark Phase A accepted or rejected without changing thresholds.
- [ ] Add result/delivery/manifest and claim-boundary README update in a follow-up evidence commit if the external measurement cannot exist before CI.

### Task 6: AGI-readiness and recovery artifact

**Files:**
- Create: `research/AGI_READINESS_R2_12.md`
- Create artifact: `Nolane-AI-R2.12-Fresh-Real-Repository-Localization-Phase-A-COMPLETE.zip`

**Interfaces:**
- AGI rubric reuses the established weighted dimensions; only dimensions with new external evidence may change.

- [ ] Score AGI-readiness conservatively from the measured evidence, explicitly distinguishing an engineering readiness percentage from probability of AGI.
- [ ] Build COMPLETE ZIP from exact GitHub source plus CI reproduction, lock/result, tests/docs and accepted R2.10 weight/delta.
- [ ] Verify ZIP `testzip`, internal SHA256SUMS and top-level SHA-256.
- [ ] Persist the ZIP to ChatGPT Library.
