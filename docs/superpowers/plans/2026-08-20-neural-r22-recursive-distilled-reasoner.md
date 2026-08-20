# Neural R2.2 Recursive Distilled Reasoner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train and validate a small weight-shared recursive neural successor to Neural R2.1a that produces a real neural-only held-out gain.

**Architecture:** Reuse the existing `RecursiveLatentIntelligenceCore` design as the R2.2 reasoning block, place it residually on top of frozen R2.1a outputs, train from verified public trajectories with symmetry-safe and depth-aware objectives, then freeze before a new untouched fresh split. R2.1a remains immutable control and is promoted only if the exact frozen R2.2 candidate passes every release gate.

**Tech Stack:** Python 3.11/3.13, PyTorch, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-20-neural-r22-recursive-distilled-reasoner-design.md`

## Global Constraints

- Parent one-weight SHA-256 is `4f0b366e2401127e50b7fdbca651601b0a4b972004812c9f32043b82f0e3091b` and must remain unchanged.
- R2.1a delta SHA-256 is `3bbd63c9cb20e180b78588e15a21e4132b41d80118c6ce229231967a91bfc9c4` and must remain unchanged.
- Fresh indices 900–919 are consumed and forbidden for R2.2 tuning.
- New fresh evaluation begins at index 1000 and occurs only after candidate freeze.
- Evaluation is neural-only with identical environment/control shell for baseline and candidate.
- Physical parameter count is reported from exact serialized tensors; legacy-effective accounting is never presented as physical count.

---

### Task 1: R2.2 policy contracts

**Files:**
- Create: `model/neural-r2.2/cogcoder/r22_policy.py`
- Test: `model/neural-r2.2/tests/test_r22_policy.py`

**Interfaces:**
- Consumes: public R2.1a/R2.0e tensors and base policy outputs.
- Produces: `RecursiveDistilledReasoner.forward(..., reasoning_steps, adaptive_halting=False)` returning action logits, depth trajectory, halt metadata, effect/progress/uncertainty/stop/success predictions.

- [ ] Write failing tests for exact parent no-op initialization, set-equivariance over action permutation, one shared reasoning-cell parameter identity across depth, bounded adaptive halting, finite depth-12 outputs, and parameter ceiling.
- [ ] Run tests and confirm RED because `r22_policy` does not exist.
- [ ] Implement the smallest residual policy satisfying those contracts by wrapping/extending the existing recursive core rather than duplicating step-specific weights.
- [ ] Run focused tests to GREEN and commit.

### Task 2: Verified distillation objective

**Files:**
- Create: `model/neural-r2.2/cogcoder/r22_training.py`
- Test: `model/neural-r2.2/tests/test_r22_training.py`

**Interfaces:**
- Produces: `R22Targets`, `r22_loss`, `configure_r22_training`, `make_r22_optimizer`, and `train_r22_step`.

- [ ] Write failing tests for set-valued symmetry-safe targets, proof-weight rejection of zero-authority batches, counterfactual margin loss, anytime/depth-monotonic loss, ponder targets, preservation loss, and gradient flow.
- [ ] Run tests to verify RED.
- [ ] Implement losses and two-stage freeze/joint optimizer with lower upstream LR.
- [ ] Run focused tests to GREEN and commit.

### Task 3: Checkpoint and truthful accounting

**Files:**
- Create: `model/neural-r2.2/cogcoder/r22_checkpoint.py`
- Test: `model/neural-r2.2/tests/test_r22_checkpoint.py`

**Interfaces:**
- Produces: save/load delta, build/load one-weight, parent SHA binding, recursive physical tensor counting.

- [ ] Write failing round-trip, wrong-parent fail-closed, physical-count, and compatibility-accounting tests.
- [ ] Run RED.
- [ ] Implement exact parent/delta binding and separate physical vs legacy-effective fields.
- [ ] Run GREEN and commit.

### Task 4: Data collection and training runner

**Files:**
- Create: `model/neural-r2.2/research/train_r22_recursive.py`
- Create: `model/neural-r2.2/research/r22_runtime.py`

**Interfaces:**
- Consumes: frozen R2.1a one-weight and FIGG-18 train/dev procedural tasks.
- Produces: verified public training rows, dev metrics, best frozen candidate.

- [ ] Add a deterministic collector that reproduces the R2.1a public tensor path and uses verifier/oracle trajectories only as training labels.
- [ ] Ensure causal pre-evidence ambiguity uses set-valued acceptable actions instead of hidden role identity.
- [ ] Warm up the recursive core at sampled depths 1–6.
- [ ] Optionally joint-train only R2.1a router / selected executive top modules if dev ablation proves benefit.
- [ ] Select by dev total + preservation constraints; never inspect new fresh range.
- [ ] Freeze exact candidate and write pre-fresh SHA lock.

### Task 5: Standalone fresh evaluation

**Files:**
- Create: `model/neural-r2.2/research/eval_r22_fresh_locked.py`
- Test: `model/neural-r2.2/tests/test_r22_evaluation_isolation.py`

**Interfaces:**
- Produces: baseline/candidate results on fresh indices 1000–1019 for each FIGG-18 family and depth ablations 1/2/4/8/12.

- [ ] Write a test that rejects evaluation code importing/dispatching the external active-causal controller as candidate authority.
- [ ] Freeze candidate before running fresh.
- [ ] Evaluate R2.1a and R2.2 under identical neural-only runtime.
- [ ] Record per-family solved/steps, depth curve, calibration, SHA, and `weights_modified_after_fresh=false`.
- [ ] Admit candidate only if the spec promotion gate passes.

### Task 6: CI, release evidence, and merge

**Files:**
- Create: `.github/workflows/neural-r22-recursive-distilled-reasoner.yml`
- Create/update under `model/neural-r2.2/`: `ARCHITECTURE.json`, `CURRENT_BEST.json`, `README.md`, evidence JSON, verifier, SHA manifest.

- [ ] Add Python 3.11/3.13 compile + architecture + pytest workflow.
- [ ] Verify local full R2.2 tests from clean source.
- [ ] Open PR against current main and require exact-head CI success.
- [ ] If fresh gate passes, package exact frozen one-weight + source/evidence and merge with expected head SHA; otherwise keep R2.1a as current best and merge only research infrastructure if it is independently useful.
- [ ] Verify post-merge main tree and package SHA, then persist the milestone ZIP in Library.