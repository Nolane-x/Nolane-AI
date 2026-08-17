# Nolane-AI R2.41 — Multi-Macro Competition + Semantic Shift Detection

**Decision:** ACCEPTED (bounded Phase A evidence)  
**AGI engineering-readiness:** **26.7 → 27.9 / 100 (+1.2)**

> `27.9/100` is an internal engineering-readiness rubric, not a scientific probability that Nolane-AI is “27.9% AGI”.

## Capability added

R2.41 moves beyond R2.40's one-macro applicability gate. It learns multiple compression-positive typed predicate macros, gives each macro an independent trust state, keeps a raw reasoning arm available, and uses an evidence ledger with leave-one-macro-out causal attribution when high-confidence observations become inconsistent with the current posterior. A culprit macro can be quarantined and its historical evidence rolled back without deleting or contaminating peer abstractions.

No seed, family/domain, target, truth, heldout identity or evaluator-only actual reliability is available to the router. Posterior/margin plus the frozen counterexample check remain the only acceptance authority.

## Frozen development evidence

- learned macro library: **6 non-equivalent macros**;
- competitive calibrated route: **6/6 correct**;
- same-router unconditional multi-macro ablation: **4/6**;
- no-macro: **6/6**;
- R2.38 binary: **6/6**;
- zero false accepts;
- all six learned macro IDs plus raw fallback exercised;
- all three semantic-shift episodes selectively quarantined one macro while preserving peers;
- reported shift reliability: **0.97**.

## Frozen heldout

Fresh seeds `881/883/887` under `held_clean` + `held_semantic_shift`:
- competitive calibrated: **6/6 correct**;
- same-router unconditional multi-macro: **5/6**;
- no-macro: **6/6**;
- R2.38 binary: **6/6**;
- zero false accepts;
- **6 distinct learned macro IDs** exercised plus raw fallback;
- semantic-shift reported reliability floor: **0.965**;
- macro-local demotion + peer preservation occurred on fresh heldout;
- all frozen causal/safety/budget/non-bit gates PASS;
- **6/6 independent canonical replays exact**.

Final verifier: **8/8 checks PASS**.

## Nolane World v5

World preregistered six predictions before heldout. The frozen experiment was submitted only after verifier evidence existed; prediction-before-experiment order remained valid. Deep review ended with audit valid (**54 events**) and World intentionally non-converged. Six hard blockers remained rather than being manufactured away: trusted active residency, independent attested compute, unresolved critical unknowns, insufficient validated information gain, remaining value-of-thought, and open proof obligations.

## Boundary and next falsifier

R2.41 supports a bounded claim: several learned abstractions can compete under a shared query budget, and a high-confidence semantic mismatch can be causally attributed to one historical macro while preserving peers. It does **not** establish universal abstraction transfer or AGI.

The next strong target is **R2.42 — Cross-Family Macro Composition**: move from choosing among independent macros to composing multiple learned abstractions in a structurally non-isomorphic heldout family, with the same preregistration/replay/safety discipline.
