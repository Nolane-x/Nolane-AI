# Neural vNext Native R3 — accepted action-attributed hidden-goal successor

Status: **ACCEPTED** under the preregistered parent-relative FIGG-18 court `fresh:80..119`.

R3 extends accepted R2 without mutating it. The hypothesis is narrow: R2 remembers ordered public transitions, but R3 additionally binds the selected action to the public transition/progress evidence that followed it. The R3 residual is hard-gated off whenever the target is visible.

## Accepted authority

- selected candidate: `attributed_broad`
- total physical parameters: **707,990**
- R3-owned parameters: **171,905**
- checkpoint SHA-256: `8c2ba53e81b51d1418cbb7abead6380808dc558cde02af9e63bf8020f92e95da`
- state-dict SHA-256: `6ecf000191d6212953c8f3a77b5f3de697795f9797c75da70ddd838003531c1e`
- parent: accepted R2 checkpoint `bb18c0b0...`

Canonical metadata is in `ACCEPTED_AUTHORITY.json`. Fresh evidence is in `evidence/FRESH_COURT_001.json`.

## Development evidence

Primary `dev:96..127`:

- frozen R2: **112/128**
- R3: **114/128**
- `implicit_goal_regimes`: 19 → **21**
- all visible-target family solved counts exact

The exact frozen Phase-1 candidate was then observed on the separate development block `dev:128..159`:

- frozen R2: **118/128**
- frozen R3: **119/128**
- `implicit_goal_regimes`: 23 → **24**
- all visible-target family solved counts exact

This second comparison is explicitly post-hoc development evidence, not a preregistered promotion court.

## Negative Phase-2 result

Further training was tested and rejected rather than hidden:

- frozen Phase-1 replay: **119/128**, implicit-goal **24/32**
- best Phase-2 candidate: **118/128**, implicit-goal **23/32**
- broader Phase-2 candidate: **114/128**, implicit-goal **19/32**

The gate was not relaxed. Phase-2 is preserved as a negative result in `evidence/PHASE2_NEGATIVE_001.json`.

## Workflow-level reproduction

Before fresh, multiple workflow executions reproduced the exact Phase-1 checkpoint and state hashes. This supports workflow-level bitwise reproduction. It is **not** promoted into a cross-host hardware guarantee.

Fresh evaluation consumed the exact frozen artifact rather than retraining the candidate.

## Untouched fresh court

`PRE_FRESH_LOCK.json` froze candidate identity, artifact authority, source blobs, evidence and the promotion gate before opening `fresh:80..119`.

Preregistered requirements:

1. R3 must solve strictly more total episodes than frozen R2;
2. R3 must strictly improve `implicit_goal_regimes`;
3. `conditional_regimes`, `regime_switch`, and `causal_prerequisites` solved counts must remain **exactly equal** to R2.

Observed on 160 untouched episodes:

- frozen R2: **142/160 = 88.75%**
- R3: **147/160 = 91.875%**
- total delta: **+5**

Family results:

- `conditional_regimes`: 39 → **39** (exact)
- `regime_switch`: 37 → **37** (exact)
- `causal_prerequisites`: 40 → **40** (exact)
- `implicit_goal_regimes`: 26 → **31** (**+5**)

Every solved-count gain came from the intended hidden-goal family while visible behavior stayed exact. Workflow run: `35449613862`; immutable fresh artifact: `10585529581`.

## Post-fresh rule

`fresh:80..119` is permanently consumed.

- no post-fresh tuning;
- no mutation under this accepted authority;
- no rerun of the same fresh block for a new promotion attempt;
- future successors require a new candidate and untouched fresh identities.

The remaining closure step is durable repository archival of the exact accepted checkpoint without retraining.
