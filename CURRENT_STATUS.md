# Nolane AI — Current Evidence Status

This file is the short authoritative status index for active research. Historical milestone documents remain evidence records; they are not automatically the current promotion boundary.

## Promotion state

| Track | State | Authority |
|---|---|---|
| `main` / R2.67 | **Historical; strong three-probe necessity claim superseded by active correctness work** | Exact merge `43b43ce4b324b0d74357957af18dd0f60b1cb85e` is retained as history, but post-freeze validation found receipt-unit and lower-order-ablation defects. |
| R2.67.1 / PR #61 | **Pending correctness hotfix; not accepted** | Active branch `r267-1-genuine-causal-necessity-hotfix-gpt56sol`. Promotion requires its own frozen evidence, canonical lineage and release verification. |
| R2.68 / PR #70 | **Research candidate; promotion forbidden** | Isolated branch `r268-cross-task-causal-transfer-gpt56sol`. It must be rebased/refrozen on the exact accepted R2.67.1-or-successor parent before any promotion claim. |

## R2.68 research question

R2.68 tests whether a verified three-probe causal expression can become an identity-free portable prior, then reduce target-side search/evidence cost on a distinct task while still failing closed under negative transfer.

The portable object contains only an abstract expression over `__p0`, `__p1`, `__p2`, its digest and zero-parameter structural metadata. It does not carry source field names, intervention IDs, semantic profile IDs, raw source examples, source outputs or target labels.

Target adaptation is intentionally bounded:

- exact transferred expression;
- abstract probe-role permutations;
- one binary-operator repair;
- active diagnostic selection before each target oracle call;
- independent disjoint terminal verification;
- no unrestricted scratch fallback inside the transfer solver.

A separate matched scratch solver receives the same target evidence contract but no source prior.

## Hosted TDD evidence already established

- Initial portable-prior RED: Actions run `32217699599` failed on Python 3.11/3.13 because the R2.68 module did not exist.
- Portable-prior GREEN: run `32217845457` passed on Python 3.11/3.13.
- Active-adaptation RED: run `32217913671` failed because the target adaptation API did not exist.
- Active-adaptation GREEN: run `32218004962` passed on Python 3.11/3.13.
- Matched-scratch RED: run `32218105396` failed because the scratch baseline API did not exist.
- Matched-scratch GREEN: run `32218226399` passed on Python 3.11/3.13.
- Authored benchmark RED: run `32218264442` failed on Python 3.11/3.13 because the benchmark module did not exist.

The benchmark implementation is not an accepted result merely because code exists. Its final hosted GREEN evidence must be recorded separately before the research gate can be described as passing.

## Parameter boundary

R2.68 adds **0 trainable neural parameters**. Any improvement measured here is hybrid-runtime learning-to-learn evidence, not a neural-parameter increase.

## Claim boundary

No active item in this file establishes AGI, unrestricted program transfer, general software-engineering autonomy, natural-language mastery, open-world learning, or frontier-model equivalence. R2.68 is a bounded causal-transfer experiment and remains non-promotable while its parent correctness boundary is unsettled.
