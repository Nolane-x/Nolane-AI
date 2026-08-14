# R2.6 Invariant Program Induction — Design

Date: 2026-08-14
Status: approved continuation design
Parent accepted system: R2.4 Long-Horizon Replanning
Neural parameter budget: 78,779,253 effective parameters; R2.6 adds 0 neural parameters in this phase

## 1. Problem statement

R2.5 improved exact ARC-AGI-2 training coverage from 45/1000 to 76/1000 while keeping a two-attempt, 64-program budget, but the frozen public scoring run solved 0/120. This is strong evidence that increasing DSL coverage and exact demonstration fit alone is not a reliable route to distribution transfer.

R2.6 therefore changes the optimization target. A candidate program is not valuable merely because it explains all visible demonstrations. It must also survive task-internal generalization tests that are fixed before measurement.

The consumed R2.5 public score is never used as a development target, tuning signal, task source, or acceptance gate for R2.6.

## 2. Approaches considered

### A. Continue expanding the R2.5 DSL
Pros: easiest path to higher TRAIN coverage; reuses the mature typed runtime.
Cons: directly repeats the failure mode exposed by 76/1000 TRAIN versus 0/120 public. Rejected as the primary R2.6 strategy.

### B. Add a learned neural ARC head
Pros: could learn ranking and latent task families that hand-written DSL search misses.
Cons: introduces a new training problem before the symbolic generalization failure is understood, increases confounding, and violates the current preference for parameter-disciplined evidence. Deferred.

### C. Invariant program induction with a generalization firewall — selected
Keep the useful R2.5 operators, but change candidate admission and ranking. Programs must pass deterministic leave-one-demonstration-out and metamorphic consistency checks when those checks are applicable. Development uses a preregistered split inside the official 1,000-task training corpus. The objective becomes held-out task transfer, not full-TRAIN fit count.

## 3. Data protocol

ARC source remains pinned to revision `f3283f727488ad98fe575ea6a5ac981e4a188e49`.

The 1,000 official `data/training` task IDs are partitioned without reading task contents:

- Compute `sha256(task_filename_utf8)`.
- Convert the first 8 hex digits to an integer.
- `bucket = value % 5`.
- buckets 0–3 are R2.6 DEVELOPMENT.
- bucket 4 is R2.6 INTERNAL_HELDOUT.

This produces an approximately 80/20 deterministic split and prevents hand-selection. The exact task IDs and counts are materialized by CI after the split rule is committed.

The INTERNAL_HELDOUT task contents are not used for operator design. They may be scored only by frozen candidate revisions under the preregistered gate.

The already-consumed R2.5 public 120-task result is archival evidence only and remains closed to R2.6 feedback.

## 4. Baseline and gates

Before R2.6 capability changes, run the frozen R2.5 candidate on the new DEVELOPMENT and INTERNAL_HELDOUT partitions. This establishes a same-protocol baseline.

R2.6 phase-A acceptance requires all of the following:

1. Internal-heldout solved-task count strictly exceeds the frozen R2.5 baseline by at least 2 tasks OR by at least 20% relative, whichever threshold is smaller but at least 1 task.
2. Development score does not fall by more than 25% relative to the R2.5 baseline.
3. Every emitted R2.6-only candidate passes the applicable generalization firewall.
4. Metamorphic unit suite has zero failures.
5. No use of R2.5 public task outputs, IDs, or score decomposition as a tuning signal.
6. Runtime on DEVELOPMENT is no more than 2.0x the same-protocol frozen R2.5 baseline unless an explicit negative-result record is committed before further tuning.
7. Two attempts per test input and 64 candidate programs remain fixed.

Passing phase A is not external evidence and does not promote R2.6 over R2.4.

## 5. Generalization firewall

### 5.1 Leave-one-demonstration-out evidence
For tasks with at least three training pairs, a candidate family must demonstrate task-internal transfer:

- For each training pair i, infer the candidate family/parameters from all other pairs.
- Apply the inferred candidate to pair i.
- The held-out output must match exactly.

To control compute, this is performed only for R2.6 candidate families that expose a deterministic `infer(pairs) -> programs` interface. Legacy R2.5 candidates are retained as a comparison channel but receive no R2.6 generalization bonus.

For two-pair tasks, LOEO is underdetermined and therefore not used as a hard rejection criterion.

### 5.2 Metamorphic consistency
R2.6 uses deterministic transformations that should preserve abstract task semantics when applied consistently to both input and output:

- color-role permutation over non-background colors;
- horizontal reflection;
- 90-degree rotation for square-grid tasks where dimensions remain valid.

A R2.6 candidate family receives invariance credit only if inference on the transformed demonstrations yields a prediction equivalent to transforming the original prediction. Unsupported transformations are skipped rather than counted as failures.

Metamorphic checks are not used to invent additional ground-truth outputs; they test equivariance/consistency of the inducer itself.

## 6. Canonical task representation

R2.6 introduces a task-level role representation rather than independently renaming colors per grid.

For each color across all visible demonstration grids, compute a role signature from observable statistics only:

- background frequency/rank;
- input/output presence pattern;
- total frequency rank;
- connected-component count and area summaries;
- border/corner incidence;
- changed-cell participation between same-shaped input/output pairs.

Colors are ordered by the role signature and then by deterministic tie-breakers. The representation never assumes that raw numeric color IDs carry semantics.

The canonicalizer is advisory for new R2.6 families and metamorphic comparison. It does not rewrite legacy R2.5 programs in place.

## 7. Candidate ranking

R2.6 ranks candidates lexicographically by evidence before raw fit complexity:

1. exact fit to all visible demonstrations (mandatory for emitted programs),
2. LOEO pass count / applicability,
3. metamorphic consistency count / applicability,
4. shorter description length / program cost,
5. deterministic program signature.

A program that cannot exactly fit visible demonstrations is never emitted merely because it scores well on invariance.

## 8. Components

### `cogcoder/r26_split.py`
Pure filename-based split rule. No task-content dependency.

### `cogcoder/r26_meta.py`
Deterministic grid/task metamorphic transforms plus inverse/equivalence utilities.

### `cogcoder/r26_canonical.py`
Task-level color-role signatures and canonical role mapping.

### `cogcoder/r26_firewall.py`
LOEO and metamorphic validation API. Does not own the underlying DSL.

### `cogcoder/r26_candidate.py`
Wraps selected R2.5 candidate families and future R2.6 invariant families. Produces evidence-bearing candidate records.

### `cogcoder/r26_score.py`
Two-attempt scorer with fixed 64-program cap and explicit R2.5 baseline mode.

### Research locks/results
`research/R2_6_PRETRAIN_LOCK.json`, split manifest, baseline result, gate result, and negative-result files are immutable evidence artifacts.

## 9. TDD sequence

1. Split determinism and content-independence.
2. Metamorphic transform round-trips.
3. Task-level color-role canonicalization under color permutation.
4. LOEO accepts a genuinely transferable inducer and rejects a demonstration-memorizing inducer.
5. Metamorphic firewall accepts an equivariant family and rejects a raw-color-ID-dependent family.
6. Score budget remains two attempts / 64 programs.
7. Baseline measurement before any R2.6 candidate promotion.

Each production behavior is introduced only after its corresponding RED test is observed in CI or the isolated local workspace.

## 10. Failure handling

- If R2.6 lowers TRAIN fit but improves internal-heldout transfer, this is considered scientifically positive and may continue.
- If it raises DEVELOPMENT but not INTERNAL_HELDOUT, record it as another overfit result and do not promote.
- If the firewall rejects nearly all candidates, improve abstraction interfaces rather than weakening the heldout gate after seeing results.
- Thresholds and split rule cannot be changed after the INTERNAL_HELDOUT gate is first opened; a changed protocol requires R2.6b with a new lock.

## 11. Claim boundary

R2.6 phase-A success would show better transfer on a preregistered held-out subset of ARC-AGI-2 training tasks. It would not establish ARC-AGI-2 public performance, AGI, or superiority over large language models. External promotion requires new independent evidence after a source/budget freeze.
