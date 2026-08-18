# R2.58 Autonomous Intervention Discovery — Design

## Status
Approved for inline execution by the user's instruction to continue building Nolane-AI without intermediate approval stops.

## Problem
R2.57 demonstrates that a learned cognitive vocabulary can transfer to an independently sourced `ufunclab.linearstep` oracle, but its external harness manually fixes the two endpoint-output inputs to 0 and 1. That authored intervention exposes the latent progress variable and is explicitly named as a remaining autonomy gap. The system therefore learns a useful representation only after the host has already chosen the decisive experiment.

## Goal
Add a zero-trainable-parameter active intervention layer that searches a bounded, side-effect-free intervention DSL over oracle inputs, discovers a useful probe without semantic field labels or source access, verifies the probe on unseen intervention contexts, and promotes it only when it causally improves downstream synthesis under a frozen budget.

The capability is deliberately bounded. R2.58 is evidence for autonomous experiment selection inside a finite pure-input intervention language, not arbitrary scientific discovery, open-ended subgoal invention, or general coding autonomy.

## Core invariants
- I/O-only oracle access. No source, AST, bytecode, signature semantics, docstrings, reflection, imports from the target package inside the learner, or evaluator code inspection.
- Candidate generation is independent of field names: only tuple position, arity, and an explicit finite anchor set may affect enumeration order.
- Interventions are pure context rewrites. They cannot invoke tools, mutate files, network state, processes, clocks, randomness, or external state.
- Probe selection uses training/probe-validation data only. Full challenge and heldout cases remain sealed until after selection.
- A probe cannot be promoted merely because it is easy to synthesize. It must be non-constant, verify on unseen probe contexts, and cause a downstream solve that the matched no-seed baseline misses under the same synthesis budget.
- Candidate accounting includes every oracle call and synthesis candidate considered.
- Selection is deterministic and content-addressed.
- Invalid or non-causal candidates remain rejected; there is no narrative promotion path.

## Architecture

### 1. Intervention DSL
Create `cogcoder/r258_intervention_discovery.py`.

`InterventionSpec` stores an ordered tuple of positional field indices and anchor values. Its `intervention_id` is SHA-256 over the positional assignment, never a semantic label. `bind(field_names)` resolves positions to names only at execution time. `apply(context, field_names)` returns a copy with the selected positions overwritten.

`enumerate_interventions(field_names, anchor_values, arity=2)` emits every ordered choice of distinct field positions and ordered distinct anchor values. Enumeration is position-stable, so renaming fields leaves the candidate sequence and winning positional intervention invariant.

### 2. Probe synthesis and validation
For each intervention candidate:
1. Apply it to every probe-training context.
2. Query the oracle and build an `OperatorExample` corpus over only the non-intervened fields.
3. Reject constant-output candidates.
4. Synthesize the probe with the R2.57 vocabulary under a frozen depth/candidate budget.
5. Require the matched R2.56 base grammar to fail for the same probe when the R2.57 vocabulary succeeds.
6. Verify the synthesized probe on separate probe-validation contexts under the same intervention.

The learner is not told what the probe means. It sees only positional input fields, anchor values, and oracle outputs.

### 3. Causal downstream utility gate
A probe that passes local validation is tested as a seed for the full R2.57 synthesis problem:
- run the no-seed vocabulary baseline on the downstream training set under the frozen full-task budget;
- run the same synthesizer with only the candidate probe expression as a seed;
- accept the intervention only if no-seed fails and seeded synthesis succeeds exactly on downstream training;
- record candidate counts and oracle calls.

This is a causal ablation: the intervention earns promotion only if its learned representation changes the downstream outcome under matched grammar and budget.

### 4. Deterministic selection
Among causally useful candidates, rank by:
1. seeded full-task candidate count;
2. probe candidate count;
3. probe validation oracle calls;
4. positional intervention digest.

The winning receipt records all considered candidate IDs, rejection reasons, selected positional bindings, synthesized probe expression, used abstraction IDs, and accounting totals.

### 5. Authored benchmark
Create `benchmarks/kfigg/r258_autonomous_intervention_discovery.py`.

Use an opaque five-input clamped affine-step oracle structurally equivalent to the external target. Run at least three field-name permutations and one argument-order permutation. The intervention learner receives no semantic role names. Required results:
- autonomous discovery succeeds in every permutation;
- the winning intervention maps to the two endpoint-output roles under each permutation;
- the positional winner changes consistently with argument-order permutation rather than with names;
- no-seed downstream baseline fails under the frozen budget;
- seeded downstream synthesis succeeds exactly;
- a deliberately non-causal intervention is rejected;
- probe validation has zero false accepts;
- trainable parameter count remains 0.

### 6. External transfer
Create `research/r258_external_intervention_transfer.py` and reuse the same pinned `WarrenWeckesser/ufunclab@f1fbe6769850823a1976ccc28d14cd966130b645` oracle.

Unlike R2.57, the harness may not directly set `fa=0, fb=1` as the chosen probe. It supplies only:
- the opaque ordered field tuple;
- finite anchor set `(0, 1)`;
- generic probe-training and probe-validation contexts;
- downstream training/challenge/heldout cases.

The learner must search all legal positional two-field interventions, select one causally useful probe, then solve the full task. Final challenge and heldout requirements remain 8/8 and 24/24 exact. The matched no-seed R2.57 vocabulary baseline must fail under the same full-task budget.

## Testing
- RED→GREEN TDD for positional/content-addressed interventions, rename invariance, pure application, constant rejection, validation, causal utility, deterministic selection, and accounting.
- Frozen authored benchmark with multiple renamings/permutations.
- External ufunclab transfer in clean CI.
- R2.57 and protected R2.56→R2.41 lineage regressions.
- Python 3.11 and 3.13 focused matrix.
- Nolane World W5 audit; W5 may remain false and does not block accepting the bounded capability.

## Claim boundary
`Autonomous bounded pure-input intervention discovery with causal downstream utility and one independently sourced I/O-only transfer.`

Do not claim arbitrary intervention invention, arbitrary latent representation discovery, general scientific autonomy, open-ended cognition, AGI, or frontier-model equivalence.
