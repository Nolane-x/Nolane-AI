# R2.43 — Counterexample-Guided Cross-Family Macro Composition

## Decision

**CANDIDATE ONLY — locally verified; external GitHub Actions gate blocked by billing/spending-limit infrastructure.**

R2.43 is intentionally **not** marked ACCEPTED. The last accepted project baseline remains R2.41 at commit `75590cb65b714a68bbaae0707f5406fcbcf58676`. The R2.43 candidate code is on `main` at `1a5786edaff0670baad3aa738d66efe7795b6f62`.

## Capability added

R2.43 adds a bounded synthesis layer that composes **different trusted learned predicate macros** with `AND`, `OR`, `XOR`, or `EQUIV`; ranks applications by posterior partition information; requires positive information synergy over the best parent; semantic-deduplicates programs; preserves R2.41 quarantine boundaries; and uses a counterexample callback as a CEGIS-style falsification filter.

The frozen target family is structurally new: `AND(AND(a,b), OR(c,d))`. The source macro library contains the inner `AND` and `OR` abstractions separately; the combined target is not stored as a macro. Atom identities are renamed per episode.

## Fresh local verification

- Focused tests: **11/11 PASS** (`1.92s`).
- Frozen held-out: **6/6 exact exhaustive 16-row truth-table proofs**.
- False accepts: **0**.
- Neither parent macro alone is exact on the target family.
- Information synergy over the best parent: **0.088392996263 to 0.112732648694 bits**.
- Bounded raw Boolean recombination semantic space: **484** unique candidates.
- Learned composer evaluates **4** candidates in every frozen held-out episode.

The bounded causal claim is search contraction with exact correctness in this protocol. It is **not** a claim that raw search cannot solve the target.

## External CI status

GitHub Actions run `32006471396`, job `95316868377`, did not receive a runner (`runner_id=0`, no steps). GitHub's annotation says the job was not started because recent account payments failed or the spending limit needs to be increased. Therefore the run is recorded as **INFRASTRUCTURE_BILLING_BLOCKER**, not as a code-test failure.

## Nolane World 0.5.0 gate

World session: `world_034289cf75d1`. Fresh gate result: `pass_gate=false`, candidate quality `0.82`, margin `0.12`, estimated material improvement `1.3`. The external-CI-verification attack remains unresolved, and W5 diversity/residency/adversarial thresholds are not yet satisfied. The gate was not gamed or manually overridden.

## Coding-AGI engineering-readiness score

- **Accepted baseline:** **27.9/100**.
- **R2.43 candidate if the independent external gate clears:** **29.2/100**.

This is an internal engineering-readiness rubric for progress toward general coding intelligence, **not a probability that the system is AGI**. The +1.3 candidate delta is justified by genuine compositional reuse, held-out exactness, falsification behavior, quarantine safety, deterministic replay, and bounded search contraction; it is capped because the benchmark is still synthetic/narrow and independent CI is unresolved.

## Acceptance boundary

R2.43 may only become ACCEPTED after an independent clean-environment runner executes the R2.43 focused tests plus R2.41 parent-compatibility gates, the external-CI attack is resolved in Nolane World, and the frozen held-out evidence remains unchanged.
