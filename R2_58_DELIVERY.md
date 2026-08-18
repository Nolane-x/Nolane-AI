# Nolane-AI R2.58 Delivery — Autonomous Intervention Discovery

Status: **ACCEPTED_BOUNDED_CAPABILITY**

R2.58 removes a specific autonomy gap left explicit by R2.57: the external transfer no longer receives a host-selected endpoint-output field pair as the decisive probe. A zero-trainable-parameter intervention layer now searches a finite positional pure-input DSL, synthesizes the induced probe with the verified R2.57 vocabulary, validates it on separate probe contexts, and awards reuse credit only when a matched-budget causal ablation changes downstream synthesis from failure to success.

## Mechanism

- positional, content-addressed intervention identities independent of semantic field names
- positional schema canonicalization before probe and downstream synthesis, eliminating lexical field-name ordering as a search confound in this path
- pure copy-on-apply input rewrites; no filesystem, process, network, clock, randomness, or other effectful intervention semantics
- non-constant probe requirement
- R2.56 base-probe failure + R2.57 vocabulary-probe success requirement
- separate probe-validation contexts
- matched no-seed failure versus seeded downstream success causal gate
- deterministic winner ranking and complete oracle/synthesis-candidate accounting
- zero new trainable parameters

## Frozen authored evidence

`R2_58_PHASE_A_RESULT.json` recomputes exactly in hosted CI:

- configurations represented: **3** (2 full searches + 1 rename replay)
- discoveries: **3/3**
- matched no-seed failures: **3/3**
- seeded downstream successes: **3/3**
- probe validation: **12/12 exact**
- wrong-role false accepts: **0**
- explicitly rejected non-causal candidates: **6**
- rename invariance: PASS
- argument-permutation role tracking: PASS
- authored oracle calls: **410**
- synthesis candidates considered: **261,169**

## Hosted verification

Capability main commit: `a7651f83f23ab3c021985f362e98c644323ecd6c`. The PR verification merge ref and final capability commit share the exact tree `0a901ba3bde95b6166d453ec8b00ca33a034d5cf`.

Hosted run `32112974493` completed successfully:

- focused R2.58 tests: **11/11**
- protected R2.57→R2.41 relevant tests: **175/175**
- total hosted relevant tests: **186/186**
- Python 3.11 / 3.13 focused behavior: success / success
- frozen Phase-A recomputation: exact

## Independent ufunclab transfer

Pinned external source: `WarrenWeckesser/ufunclab@f1fbe6769850823a1976ccc28d14cd966130b645`, callable `ufunclab.linearstep`.

The learner receives I/O only. It is given an opaque five-position schema, a finite anchor set `(0, 1)`, generic probe contexts, and the downstream examples. The harness does **not** select the endpoint-output field pair.

- legal intervention candidates considered: **20**
- host-selected intervention: **false**
- discovered position set: **[3, 4]**
- no-seed R2.57 vocabulary baseline: **FAIL** at **1,000** candidates
- selected seeded downstream synthesis: **PASS** in **203** candidates
- probe validation: **4/4 exact**
- challenge: **8/8 exact**
- heldout: **24/24 exact**
- total oracle calls: **251**
- intervention-discovery oracle calls: **211**
- synthesis candidates considered: **136,969**
- external artifact: `9315608064`

## Nolane World 0.8.0

World `world4_2513f45435574d2d` produced a valid audit digest `b6ec9a6c284ce8c9b957b81200a763a1f5796faa3eb68d25f8bda70dab203f9e`. W5 remains **FAIL**, score **0**, with unresolved requirements including independent challenger/counterfactual-world and broader verification evidence. This non-convergence is intentionally preserved.

## Readiness

Internal Coding-AGI engineering-readiness: **47.8/100**, up **+0.3** from R2.57's 47.5. The movement is intentionally small: R2.58 removes the hand-selected intervention within a clean external transfer and adds a causal selection gate, but the external family is still the same narrow numeric family used by R2.57, while anchors, probe-context families, and evaluator grammar remain host-designed.

This score is an engineering heuristic, not an AGI probability.

## Claim boundary

R2.58 demonstrates **bounded autonomous pure-input intervention discovery with causal downstream utility** on one independently sourced I/O-only numeric family. It does not establish arbitrary experiment invention, arbitrary latent-representation discovery, effectful interventions, broad repository coding autonomy, open-ended cognition, AGI, or frontier-model equivalence.
