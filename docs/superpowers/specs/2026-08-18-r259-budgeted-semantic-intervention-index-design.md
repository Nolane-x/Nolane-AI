# R2.59 Budgeted Semantic Intervention Index — Design

## Status
Approved for inline execution by the user's standing instruction to continue building Nolane-AI directly, coordinate with concurrent agents, and prefer quality over speed without intermediate approval stops.

## Problem
R2.58 removes host selection of the decisive probe, but it pays for nearly the same synthesis search separately for each intervention candidate. The frozen authored gate counts 261,169 synthesis candidates and the hosted external transfer counts 136,969 for only 20 legal interventions. This makes the autonomy gain difficult to scale to wider intervention spaces.

R2.58 also receives an explicit `anchor_values` argument even though the downstream synthesis task already declares a finite constant basis. The intervention learner should not require a second task-specific anchor channel when it can derive a deterministic anchor basis from already-public task grammar.

## Goal
Add a zero-trainable-parameter, fail-closed intervention search layer that preserves R2.58 positional/rename invariance and causal verification while amortizing probe search across intervention candidates. Probe expressions are indexed once per free-position projection by their observed semantic vector, then intervention-generated target vectors perform exact semantic lookup. Verified seed expressions share downstream synthesis receipts through a content-addressed cache.

The release must demonstrate a causal solve under a strict global synthesis budget that the frozen R2.58 exhaustive accounting exceeds by a large margin, without weakening challenge/heldout gates.

## Core invariants
- Preserve R2.58 `PositionalSchema`; semantic field names never affect candidate identity or search order.
- I/O-only oracle access; no source, signature semantics, reflection, bytecode, docstrings, filesystem, network, subprocess, clock or randomness.
- Intervention anchors are derived deterministically from `downstream_need.constants`; no separate host-selected anchor list is required by the primary API.
- The probe index is built from the promoted learned vocabulary and free canonical fields. A promoted seed must actually call at least one learned abstraction.
- Semantic vectors are canonicalized with finite numeric tolerance and content-addressed; duplicate semantics are evaluated once per free-position projection.
- Probe training and probe validation remain disjoint. Final downstream challenge/heldout data remain sealed until after selection.
- No-seed downstream synthesis is still run under the same downstream task budget. A candidate receives causal credit only if no-seed fails and seeded synthesis succeeds.
- All probe-index candidate construction, downstream synthesis candidates, oracle calls, cache hits/misses and budget exhaustion are recorded.
- `max_total_synthesis_candidates` is a hard global budget. Search must abstain rather than silently exceed it.
- Unknown/invalid/non-finite oracle behavior fails closed.

## Architecture

### 1. Semantic probe index
Create `cogcoder/r259_semantic_intervention_index.py`.

For each distinct set of non-intervened canonical positions, build a bounded learned-vocabulary probe index once. Start from free `Field` atoms and enumerate `AbstractionCall` compositions breadth-first with deterministic round-robin scheduling across learned abstractions. Evaluate each expression on the projected probe-training contexts and keep only the first minimal expression for each semantic vector.

The index deliberately does not re-enumerate the full R2.56 raw operator grammar for every intervention. R2.59's new claim is search amortization over already-promoted R2.57 vocabulary; R2.58 already established the matched R2.56-base failure boundary.

### 2. Intervention target lookup
Enumerate R2.58 positional interventions using anchors derived from `downstream_need.constants`. For each intervention, query the oracle on probe-training contexts, reject invalid/constant targets, canonicalize the target semantic vector, then look it up in the cached probe index for that free-position projection.

A hit must be non-trivial and use a learned abstraction. Validate the expression on separate probe-validation contexts before it can seed downstream synthesis.

### 3. Downstream causal cache
Run the canonical no-seed downstream baseline once. For every distinct verified seed digest, run downstream synthesis at most once and cache its receipt. Repeated interventions exposing the same representation reuse that receipt. A seed is admissible only if no-seed fails and seeded synthesis succeeds exactly on downstream training.

### 4. Global budget ledger
Track a single synthesis-candidate ledger containing:
- no-seed downstream candidates;
- every probe-index expression admitted for evaluation;
- each unique seeded downstream synthesis candidate count.

Before each bounded search stage, allocate only the remaining budget. If no candidate can be causally verified before the ledger reaches `max_total_synthesis_candidates`, return a structured `budget_exhausted` abstention.

### 5. Frozen benchmark
Create `benchmarks/kfigg/r259_budgeted_semantic_intervention_index.py` on the same opaque clamped affine-step family used by R2.58 so the only changed variable is search architecture. Require:
- exact autonomous intervention discovery;
- positional rename and argument-role permutation invariance;
- no-seed failure and seeded success;
- zero false accepts on non-causal/invalid interventions;
- hard global synthesis budget respected;
- R2.59 synthesis candidates at least 8x lower than the frozen R2.58 authored per-full-search average and below an absolute preregistered ceiling;
- trainable parameter count 0.

### 6. External transfer
Reuse pinned `WarrenWeckesser/ufunclab@f1fbe6769850823a1976ccc28d14cd966130b645` only as a controlled matched-distribution efficiency test, not as new breadth evidence. The R2.59 harness may receive the same opaque positional schema, probe contexts and downstream examples as R2.58, but must not receive a separate intervention anchor list. It derives the anchor basis from the downstream need constants.

Require challenge 8/8 and heldout 24/24 exact, no-seed failure, seeded success, host-selected intervention false, and a strict global synthesis budget well below R2.58's 136,969 candidates.

## Testing
- TDD for anchor derivation, positional identity, semantic canonicalization, index reuse, duplicate semantic elimination, seed caching, validation, global budget abstention and invalid-oracle fail-closed behavior.
- Frozen authored benchmark and matched R2.58 efficiency ablation.
- External ufunclab transfer in clean CI.
- Full protected R2.58→R2.41 relevant lineage.
- Python 3.11/3.13 focused matrix.
- Nolane World W5 audit. W5 non-convergence remains acceptable and must not be fabricated away.

## Claim boundary
`Budgeted semantic-indexed reuse for R2.58-style autonomous pure-input intervention discovery, with causal downstream verification and matched-distribution efficiency evidence.`

Do not claim a new external task distribution, arbitrary anchor invention, arbitrary intervention language growth, effectful experiment design, general coding autonomy, AGI, or frontier-model equivalence.
