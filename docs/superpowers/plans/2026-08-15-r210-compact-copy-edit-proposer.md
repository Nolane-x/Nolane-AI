# R2.10 Compact Copy-Edit Proposer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train and lock a <300k-parameter language/task-id-free neural copy-edit scorer that improves R2.9 under a frozen Python→JavaScript executable heldout protocol.

**Architecture:** Canonicalize code/edit roles into a shared token space, encode buggy context and candidate replacement with a shared GRU, fuse public execution evidence, rank constrained candidates, and feed that ordering into unchanged R2.9 search. A frozen 48-case JavaScript panel compares the learned scorer against an unranked baseline under the same two-evaluation budget.

**Tech Stack:** Python 3.11, PyTorch, pytest, existing R2.8/R2.9 runtime.

## Global Constraints

- Training corpus uses Python-rendered tasks only.
- Frozen heldout panel uses JavaScript-rendered tasks only.
- No language id, task id, filename id, candidate id, or gold-patch id enters model features.
- Candidate ids and identifiers must be rename invariant.
- Add <=300,000 neural parameters and keep total <80,000,000.
- R2.9 evaluator remains sole terminal-success authority.
- External coding and AGI claims remain false.

---

### Task 1: Canonical representation and candidate enumeration

**Files:**
- Create: `cogcoder/r210_copy_edit_features.py`
- Test: `tests/test_r210_copy_edit_features.py`

**Interfaces:**
- Produces `CanonicalEditExample`, `canonicalize_source()`, `encode_evidence()`, `enumerate_copy_edit_candidates()`.

- [ ] Write failing tests for Python/JavaScript canonical equivalence, identifier renaming invariance, candidate-id exclusion, and gold-independent public records.
- [ ] Run focused tests and confirm RED.
- [ ] Implement minimal canonical tokenization, role normalization, evidence encoding, and candidate enumeration.
- [ ] Re-run and confirm GREEN.

### Task 2: Compact neural candidate scorer

**Files:**
- Create: `cogcoder/r210_copy_edit_model.py`
- Test: `tests/test_r210_copy_edit_model.py`

**Interfaces:**
- Produces `CopyEditProposalConfig`, `CopyEditProposalNet`, `proposal_parameter_count()`, `rank_candidates()`.

- [ ] Write failing shape/mask/determinism/parameter-ceiling tests.
- [ ] Confirm RED.
- [ ] Implement shared embedding+GRU encoders, evidence MLP, fusion scorer, masked ranking.
- [ ] Confirm GREEN and exact parameter count <=300,000.

### Task 3: Python training curriculum and frozen JavaScript panel

**Files:**
- Create: `benchmarks/codeworld/r210_copy_edit_curriculum.py`
- Test: `tests/test_r210_curriculum.py`

**Interfaces:**
- Produces `build_r210_training_rows()` and `build_r210_heldout_cases()` with 48 heldout JavaScript executable tasks.

- [ ] Write tests proving train language is Python only, heldout language is JavaScript only, seeds/identifiers are disjoint, heldout count is 48, and no answer fields appear in public model inputs.
- [ ] Implement deterministic semantic-family generation and executable adapters.
- [ ] Confirm GREEN.

### Task 4: Freeze gate and train proposer

**Files:**
- Create: `research/R2_10_PRETRAIN_LOCK.json`
- Create: `scripts/train_r210_copy_edit_proposer.py`
- Test: `tests/test_r210_training.py`

**Interfaces:**
- Training returns scorer state, parameter count, train ranking accuracy, seed, epochs, and data counts; save bundle appends `r210_copy_edit_delta` to the R2.7 checkpoint.

- [ ] Write/freeze lock before training-result inspection.
- [ ] Write failing training/bundle tests.
- [ ] Train with deterministic seed and listwise cross-entropy.
- [ ] Save candidate checkpoint only if parameter ceiling is satisfied.

### Task 5: Locked executable measurement

**Files:**
- Create: `scripts/measure_r210_copy_edit.py`
- Create: `research/R2_10_PHASE_A_RESULT.json`
- Test: `tests/test_r210_measure.py`

**Interfaces:**
- Measurement emits top1 accuracy, proposer+R2.9 solve rate, baseline solve rate, improvement pp, rename invariance, false accepts, parameter counts, and claim boundary.

- [ ] Measure exactly once against the frozen heldout panel.
- [ ] Accept only if every lock threshold passes; otherwise record rejection without threshold edits.
- [ ] Reproduce measurement from saved checkpoint and require exact aggregate equality.

### Task 6: CI, delivery, full regression, and milestone package

**Files:**
- Create: `.github/workflows/r210-copy-edit.yml`
- Create: `R2_10_DELIVERY.md`
- Create: `R2_10_RELEASE_MANIFEST.json`
- Modify: `README.md`

- [ ] Run R2.8+R2.9+R2.10 focused regression and compileall.
- [ ] Integrate one atomic commit to `main` only after exact-source verification.
- [ ] Require GitHub Actions success on the exact commit.
- [ ] Build full project ZIP with checkpoint, locks/results/tests/docs/provenance/checksums.
- [ ] Persist ZIP to ChatGPT Library.
