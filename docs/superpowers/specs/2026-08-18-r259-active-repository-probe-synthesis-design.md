# R2.59 Active Diagnostic Repository Probe Synthesis — Design

## Status
Approved for inline execution by the user's standing instruction to continue strengthening Nolane-AI without intermediate approval stops.

## Problem
R2.46–R2.52 can maintain a repository patch version space and reveal sparse counterexamples, but the diagnostic inputs themselves come from a pre-existing test universe and are exposed in a fixed hidden order. When four sparse tests leave multiple multi-file patch hypotheses alive, the runtime does not choose the next experiment that best distinguishes them.

R2.58 adds bounded intervention discovery for pure I/O functions. R2.59 transfers that active-experiment principle into repository repair: use the current executable patch hypotheses as a world model, predict their behavior on legal candidate inputs, choose the input with highest deterministic disagreement, query an I/O-only reference oracle once, then independently verify the unique surviving repository patch.

## Goal
Add a zero-trainable-parameter active repository diagnostic layer that turns ambiguous executable patch version spaces into verified atomic patch decisions with fewer selection-oracle calls than target-independent probe choice, while preserving abstention and zero false terminal accepts.

## Claim boundary
Passing R2.59 establishes bounded active diagnostic input selection over an existing finite executable repository-patch version space. It does not establish general repository coding, unrestricted test generation, open-ended program synthesis, effectful experimentation, or AGI.

## Architecture

### 1. Content-addressed repository probes
Create `cogcoder/r259_active_repository_probes.py`.

`RepositoryProbe(args)` stores only JSON-scalar positional arguments. Its `probe_id` is SHA-256 over canonical argument content. `enumerate_probe_inputs(arity, values)` deduplicates and canonicalizes the finite value vocabulary before Cartesian enumeration, so caller value order cannot alter the probe set.

### 2. Candidate execution model
R2.59 consumes existing `RepositoryPatchCandidate` objects from R2.52. Each candidate is compiled through `compile_repository_candidate`. Candidate identity, list order, macro IDs, and user-visible names are excluded from diagnostic ranking. Search behavior is based only on executable predictions and content-derived behavior digests.

Compilation or execution failure is a candidate outcome class rather than a terminal success path.

### 3. Active diagnostic scoring
After filtering against the supplied sparse `PatchTest` observations, every legal unqueried probe is executed against every surviving candidate.

The predictions induce a partition of the survivor set. The probe ranking is deterministic and candidate-ID invariant:

1. minimize the largest outcome partition (minimax ambiguity);
2. minimize total collision mass `sum(bucket_size^2)`;
3. maximize number of distinct outcome partitions;
4. break ties by content-addressed `probe_id`.

Only the winning probe is sent to the reference oracle. Merely scoring candidate predictions consumes no oracle labels.

### 4. Bounded active CEGIS loop
`solve_repository_patch_with_active_probes(...)` repeats active probe selection under a hard `max_selection_oracle_calls` budget.

For each selected probe:
- query the I/O-only oracle exactly once;
- retain candidates whose predicted outcome matches the oracle;
- record the partition signature and survivor reduction;
- never reuse a probe.

Failure modes are fail-closed:
- empty version space → abstain;
- no informative legal probe → abstain without unnecessary oracle calls;
- exhausted selection budget → abstain;
- oracle outcome outside the candidate version space → abstain;
- oracle error → abstain.

### 5. Independent final verification
A candidate is not accepted merely because active diagnosis leaves one survivor. The unique survivor must be run against every provided final verification input, and each expected output is obtained independently from the reference oracle.

Any mismatch or oracle failure causes abstention. `false_terminal_accepts` therefore remains zero by construction in the accepted path.

### 6. Accounting
Receipts expose:
- initial/final survivor counts;
- selection-oracle calls;
- verification-oracle calls;
- total oracle calls;
- candidate evaluations;
- selected probe and partition signature per active round;
- verification failures;
- zero trainable parameters.

Selection labels and independent verification labels are accounted separately so final exhaustive verification cannot be mistaken for search feedback.

## Frozen authored repository benchmark
Create `benchmarks/kfigg/r259_active_repository_probe_transfer.py` on the protected R2.52 six-episode heldout repository family.

The benchmark preserves:
- 75 patch candidates;
- 5–6 file repositories;
- call depth 4–5;
- opaque identifiers;
- four initial sparse observations;
- 2,401 legal four-argument inputs;
- exact multi-file target patch generated independently from the learner.

Crucially, R2.59 probe inputs are generated from the fixed Cartesian input domain without reading target outputs. Target outputs are queried only for the actively selected probe and final independent verification.

Pre-registered comparisons:
- **Active:** one maximally discriminating query budget.
- **Random-one-probe:** one target-independent hash-selected query under the same selection-oracle budget.
- **Passive-initial-only:** no additional query; abstain unless sparse evidence already leaves one hypothesis.

Required properties include candidate-ID/order invariance, zero false accepts, full 2,401-case final verification, and no target-output leakage into probe generation.

## Testing
- RED→GREEN TDD for probe identity, enumeration invariance, maximal disagreement, candidate-ID/order invariance, indistinguishable-hypothesis abstention, budget exhaustion, and oracle accounting.
- Frozen R2.59 six-episode benchmark.
- R2.58 and protected R2.57→R2.41 regressions.
- Python 3.11 and 3.13 focused determinism.
- Nolane World 0.8.0 adversarial audit; W5 may remain false.

## Scientific discipline
R2.59 receives a finite host-provided input vocabulary/domain and an already enumerated patch candidate set. Therefore any readiness movement requires evidence beyond this authored benchmark. Mechanism-only success may be accepted with no readiness increase. A future external transfer must be independently sourced and must preserve matched selection-oracle causal ablations.
