# Nolane-AI R2.40 — Uncertainty-Aware Macro Applicability Calibration

**Decision:** ACCEPTED (bounded Phase A evidence)  
**AGI engineering-readiness:** **25.6 → 26.7 / 100 (+1.1)**

> `26.7/100` is an internal engineering-readiness rubric, not a scientific probability that Nolane-AI is “26.7% AGI”.

## Capability added

R2.39 proved that a reusable typed predicate macro could be learned from cross-episode compression, but fresh noisy heldout showed that unconditional macro reuse can overgeneralize. R2.40 adds a trajectory-local applicability posterior above the frozen macro library. It uses only observable diagnostics: verifier reliability metadata, posterior entropy/margin, macro-vs-raw agreement, prediction stability and relative search cost. A conservative lower-confidence bound controls whether macro reuse remains enabled or is latched to `defer_raw` for the rest of that episode.

No seed, family/domain, target, truth, heldout identity or evaluator-only actual reliability is available to the applicability policy. Posterior/margin and counterexample authority remain the only acceptance mechanism.

## Frozen development evidence

Fresh development seeds `701/709/719/727/733/739` under `cal_clean` + `cal_shift`:
- calibrated: **12/12 correct**;
- unconditional R2.39 macro: **11/12**;
- no-macro: **11/12**;
- R2.38 binary: **11/12**;
- zero false accepts;
- **20** macro routing decisions and **17** raw deferrals;
- **2** episodes deferred completely.

## Frozen heldout

Fresh seeds `751/757/761` under preregistered `app_clean` + `app_shift`:
- calibrated: **6/6 correct**;
- unconditional macro: **6/6**;
- no-macro: **5/6**;
- R2.38 binary: **5/6**;
- calibrated mean probe cost: **6.57**;
- unconditional macro mean probe cost: **7.40**;
- cost reduction vs unconditional macro: **11.3%**;
- macro routes: **11**, deferrals: **8**;
- zero false accepts;
- all frozen causal/safety/budget/non-bit gates PASS;
- **6/6 independent canonical replays exact**.

Final verifier: **8/8 checks PASS**.

## Nolane World v5

World preregistered six predictions before heldout. The experiment was accepted after prediction registration; deep review ended with audit valid (**54 events**) and World intentionally non-converged. Real blockers—trusted residency, independent attested compute, critical unknowns, validated information gain, remaining value-of-thought and open proof obligations—were retained rather than manufactured away.

## Boundary and next falsifier

R2.40 supports a bounded claim: one development-learned macro can be conditionally reused or bypassed under observable verifier-noise shifts with a causal heldout cost advantage over unconditional macro reuse. It does not establish universal macro calibration or AGI.

The next strong target is **multi-macro applicability competition**: learn several abstractions with overlapping scopes, estimate which macro (or no macro) should control query generation per trajectory, and transfer that routing to a task family where reliability metadata alone is insufficient to expose mismatch.
