# R2.64 Learned Contextual Causal Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a zero-parameter learned contextual composition layer that removes R2.62's fixed one-step composition assumption without overlapping peer R2.63 repository multi-edit work.

**Architecture:** Build a deterministic composition synthesizer over two probe outputs plus only positions untouched by both interventions, enforce matched single-probe and R2.62 fixed-op falsifiers, then synthesize the selected probe functions and substitute them into the learned composition expression. Freeze authored positional-invariance evidence and a pinned I/O-only `ufunclab.step` transfer.

**Tech Stack:** Python 3.11/3.13, pytest, existing Nolane-AI R2.56 DSL/R2.58 interventions/R2.59 anchor derivation/R2.62 experiment infrastructure, GitHub Actions, Nolane World 0.8.0.

**Spec:** `docs/superpowers/specs/2026-08-18-r264-learned-contextual-composition-design.md`

## Global Constraints

- New code lives in an additive `r264_*` namespace and must not modify peer R2.63 implementation files.
- Zero new trainable parameters.
- Composition may access only probe outputs and original positions untouched by every selected intervention.
- R2.62 fixed-op and both matched single-probe composition baselines must fail before full-program acceptance.
- Invalid/non-finite behavior and exhausted budgets fail closed.
- External oracle source remains callable-I/O only inside the learner.
- No acceptance or readiness movement before hosted source-lock, lineage, external and Nolane World evidence.

---

### Task 1: Lock the RED composition contract

**Files:**
- Create: `tests/test_r264_learned_contextual_composition.py`
- Create: `tests/test_r264_external_contextual_transfer.py`

**Interfaces:**
- Consumes: R2.56 expression types, R2.58 `InterventionSpec`, R2.62 fixed-op baseline semantics.
- Produces: executable behavioral contract for the R2.64 public API.

- [ ] Write a test where two synthetic intervention profiles require a conditional using shared untouched context and where all six R2.62 fixed operators fail.
- [ ] Write a test requiring both single-probe ablation searches to fail.
- [ ] Write rename/permutation and fail-closed budget/non-finite tests.
- [ ] Write a local external-shaped `step` test with challenge/heldout separation.
- [ ] Run `PYTHONPATH=. pytest -q tests/test_r264_*.py` and verify RED specifically because `cogcoder.r264_learned_contextual_composition` does not exist.

### Task 2: Implement deterministic contextual expression synthesis

**Files:**
- Create: `cogcoder/r264_learned_contextual_composition.py`
- Test: `tests/test_r264_learned_contextual_composition.py`

**Interfaces:**
- Produces `synthesize_contextual_expression(fields, constants, examples, max_depth, max_candidates)` and receipt/accounting helpers used by structure discovery.

- [ ] Enumerate atomics and depth-1 trusted DSL expressions with semantic deduplication.
- [ ] Prioritize depth-2 conditionals whose condition is a boolean-valued depth-1 expression and whose branches are semantically distinct numeric candidates.
- [ ] Count every candidate and evaluation; stop exactly at the hard candidate budget.
- [ ] Reject non-finite results and type-invalid expressions without accepting them.
- [ ] Run focused tests until deterministic synthesis behavior is GREEN.

### Task 3: Discover contextual complementary structure

**Files:**
- Modify: `cogcoder/r264_learned_contextual_composition.py`
- Test: `tests/test_r264_learned_contextual_composition.py`

**Interfaces:**
- Produces `discover_contextual_composition_structure(...)` and immutable structure/program receipts.

- [ ] Canonicalize fields by position and enumerate finite interventions from need-derived anchors.
- [ ] Build intervention output profiles on frozen discovery/selection contexts.
- [ ] For each pair, expose only probe outputs plus the intersection of free positional fields.
- [ ] Synthesize a composition expression and require both probe placeholders to occur.
- [ ] Reject any pair solved by an R2.62 fixed one-step composition.
- [ ] Run matched single-probe composition searches and reject if either passes.
- [ ] Rank passing programs deterministically by expression complexity, intervention IDs and digest.
- [ ] Verify rename/program-ID invariance and fail-closed negative cases.

### Task 4: Synthesize executable probes and final expression

**Files:**
- Modify: `cogcoder/r264_learned_contextual_composition.py`
- Test: `tests/test_r264_learned_contextual_composition.py`

**Interfaces:**
- Produces `synthesize_contextual_composition_program(...) -> ContextualCompositionSynthesisReceipt`.

- [ ] Synthesize each selected intervention output from that intervention's free positional projection.
- [ ] Validate each probe expression on separate probe-validation contexts.
- [ ] Substitute `__p0`/`__p1` and shared canonical fields into the learned composition expression.
- [ ] Externalize the final expression back to original field names.
- [ ] Require exact final validation and preserve matched candidate-budget accounting.
- [ ] Run focused tests GREEN.

### Task 5: Freeze authored R2.64 evidence

**Files:**
- Create: `benchmarks/kfigg/r264_learned_contextual_composition.py`
- Create: `tests/test_r264_contextual_composition_benchmark.py`
- Create: `R2_64_PHASE_A_RESULT.json`

**Interfaces:**
- Produces deterministic `run_benchmark()` evidence with canonical, rename and permutation configurations plus negatives.

- [ ] Implement mixed-sign band-selector episodes with a required contextual conditional composition.
- [ ] Demonstrate R2.62 fixed-op failure, matched singleton failures and full R2.64 exactness.
- [ ] Freeze positional rename and role-permutation invariants.
- [ ] Freeze budget/non-finite/terminal-contradiction abstentions.
- [ ] Recompute the JSON twice and require byte-identical output.

### Task 6: Add pinned external `ufunclab.step` transfer

**Files:**
- Create: `research/r264_external_contextual_transfer.py`
- Modify: `tests/test_r264_external_contextual_transfer.py`

**Interfaces:**
- Produces `run_external_transfer(step_callable, source_id, source_commit)` with I/O-only evidence.

- [ ] Use mixed-sign flow/fa/fhigh contexts including equality cases.
- [ ] Keep discovery/selection, challenge and heldout rows disjoint.
- [ ] Assert no host-selected intervention pair and derive anchors from the public downstream need.
- [ ] Require both singleton baselines and the R2.62 fixed-op baseline to fail.
- [ ] Require full learned composition challenge/heldout exactness and zero trainable parameters.
- [ ] Run local callable-shaped tests GREEN.

### Task 7: Hosted verification, World audit and release

**Files:**
- Create: `.github/workflows/r264-learned-contextual-composition.yml`
- Create after hosted evidence: `R2_64_PRE_HOSTED_LOCK.json`, `R2_64_EXTERNAL_TRANSFER.json`, `R2_64_VERIFY_RESULT.json`, `R2_64_WORLD_FINAL.json`, `R2_64_DELIVERY.md`, `R2_64_RELEASE_MANIFEST.json`, `R2_63_TO_R2_64_EVOLUTION.md`
- Modify only after evidence: `R2_READINESS_RECALIBRATION.md`
- Create: `.github/workflows/r264-release-bundle.yml`

**Interfaces:**
- Produces the accepted bounded capability only if all independent gates are green.

- [ ] Rebase the additive R2.64 tree on the latest accepted parent after peer R2.63 lands.
- [ ] Freeze SHA-256 source lock for core/benchmark/research/tests/spec/plan/workflow.
- [ ] Run hosted focused tests and exact Phase-A recomputation on Python 3.11 and 3.13.
- [ ] Install pinned `ufunclab` and recompute external transfer exactly.
- [ ] Run the protected accepted-parent lineage.
- [ ] Record external artifact ID/digest and canonical hosted run IDs.
- [ ] Advance/audit the dedicated Nolane World W5 session without fabricating convergence; preserve W5=false if blockers remain.
- [ ] Update readiness conservatively only after causal/external evidence is real.
- [ ] Build and integrity-test the full repository ZIP release artifact.
