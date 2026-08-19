# Nolane AI — Current Evidence Status

This file is the short authoritative status index for active research. Historical milestone documents remain evidence records; they are not automatically the current promotion boundary.

## Promotion state

| Track | State | Authority |
|---|---|---|
| `main` / R2.67 | **Historical; strong three-probe necessity claim superseded by active correctness work** | Exact merge `43b43ce4b324b0d74357957af18dd0f60b1cb85e` is retained as history, but post-freeze validation found receipt-unit and lower-order-ablation defects. |
| R2.67.1 / PR #61 | **Pending correctness hotfix; not accepted** | Active branch `r267-1-genuine-causal-necessity-hotfix-gpt56sol`. Promotion requires its own frozen evidence, canonical lineage and release verification. |
| Canonical R2.68 / PR #73 | **Active architectural research candidate; not accepted** | `r268-proof-carrying-adaptive-causal-basis-gpt56sol` owns the R2.68 milestone namespace. Its proof-carrying adaptive causal-basis work is independent from the transfer research below and remains subject to exact-parent/evidence/release gates. |
| R2.68-T transfer research / PR #70 | **Independent validation/research track; promotion forbidden as R2.68** | `r268-cross-task-causal-transfer-gpt56sol` explicitly yields canonical R2.68 ownership to PR #73. Its evidence may be reused by #73 or a later milestone only after a new version allocation and exact-parent integration. |

## R2.68-T research question

R2.68-T tests whether an identity-free verified three-probe expression prior can make a distinct target solvable under a **smaller bounded hypothesis candidate budget** than the matched scratch search used by this gate while still failing closed under negative transfer.

The current evidence does **not** claim fewer total target oracle calls than a roomy scratch solver. That is a separate experiment.

The portable object contains only an abstract expression over `__p0`, `__p1`, `__p2`, its digest and zero-parameter structural metadata. It may not carry source field names, intervention IDs, semantic profile IDs, raw source examples, source outputs or target labels.

Target adaptation is intentionally bounded:

- exact transferred expression;
- abstract probe-role permutations;
- one binary-operator repair;
- active diagnostic selection before each target oracle call;
- independent disjoint terminal verification;
- no unrestricted scratch fallback inside the transfer solver.

A separate matched scratch solver receives the same target diagnostic/terminal contract and active selector but no source prior.

## Hosted TDD evidence established

- Initial portable-prior RED: Actions run `32217699599` failed on Python 3.11/3.13 because the transfer module did not exist.
- Portable-prior GREEN: run `32217845457` passed on Python 3.11/3.13.
- Active-adaptation RED: run `32217913671` failed because the target adaptation API did not exist.
- Active-adaptation GREEN: run `32218004962` passed on Python 3.11/3.13.
- Matched-scratch RED: run `32218105396` failed because the scratch baseline API did not exist.
- Matched-scratch GREEN: run `32218226399` passed on Python 3.11/3.13.
- Authored benchmark RED: run `32218264442` failed on Python 3.11/3.13 because the benchmark module did not exist.
- Authored benchmark GREEN: run `32218379720` passed the unchanged three-positive/two-negative benchmark on Python 3.11 and 3.13. The assertions require positive transfer `3/3`, negative-transfer abstention `2/2`, tight scratch `0/3`, roomy scratch `3/3`, diagnostic-order invariance, zero false accepts and zero trainable parameters.
- Nolane World W5 hardening RED: run `32218763169` produced **4 failures / 11 passes** on both Python versions. The four failures isolate direct-construction authority bypasses and the missing explicit source-prior ablation; prior transfer/baseline contracts remained green.

The W5 hardening challengers are mandatory before this research track can be described as hardened: direct construction must enforce identity/digest/probe-role/zero-parameter boundaries, and a same-budget structurally shuffled source-prior ablation must remove the transfer advantage.

## Source boundary

Phase A begins at the verified abstract expression-prior boundary; it does not independently rerun the complete source-learning pipeline on every benchmark invocation. Before any future promotion, portable export must be bound to an exact accepted parent receipt/evidence boundary after rebase and refreeze.

## Parameter boundary

R2.68-T adds **0 trainable neural parameters**. Any measured effect is hybrid-runtime learning-to-learn evidence, not a neural-parameter increase.

## Claim boundary

Neither canonical PR #73 nor this transfer-research track establishes AGI. R2.68-T additionally does not establish unrestricted program transfer, arbitrary raw target-schema binding, lower total oracle cost, general software-engineering autonomy, natural-language mastery, open-world learning, or frontier-model equivalence.
