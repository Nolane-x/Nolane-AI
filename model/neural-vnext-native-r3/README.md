# Neural vNext Native R3 — accepted action-attributed hidden-goal successor

Status: **ACCEPTED** under the preregistered parent-relative FIGG-18 court `fresh:80..119`.

R3 extends accepted R2 without mutating it. R3 adds an ordered binding between the selected action and the public transition/progress evidence that followed it. Its residual is hard-gated off whenever the target is visible.

## Accepted authority

- selected candidate: `attributed_broad`
- total physical parameters: **707,990**
- R3-owned parameters: **171,905**
- checkpoint SHA-256: `8c2ba53e81b51d1418cbb7abead6380808dc558cde02af9e63bf8020f92e95da`
- state-dict SHA-256: `6ecf000191d6212953c8f3a77b5f3de697795f9797c75da70ddd838003531c1e`
- durable checkpoint: `accepted/r3.pt` via Git LFS, **2,854,493 bytes**

## Development evidence

Primary `dev:96..127`: R2 **112/128** → R3 **114/128**; implicit-goal **+2**; visible families exact.

Secondary `dev:128..159`: R2 **118/128** → frozen R3 **119/128**; implicit-goal **+1**; visible families exact. This comparison is explicitly post-hoc development evidence, not a promotion court.

## Negative Phase-2 result

Additional training was rejected rather than hidden:

- frozen Phase-1 replay: **119/128**, implicit-goal 24/32
- best Phase-2: **118/128**, implicit-goal 23/32
- broader Phase-2: **114/128**, implicit-goal 19/32

The gate was never relaxed. Canonical evidence is `evidence/PHASE2_NEGATIVE_001.json`.

## Workflow-level reproduction

Multiple workflow executions reproduced the exact Phase-1 checkpoint and state hashes before fresh. This is recorded as workflow-level bitwise reproduction, not a cross-host hardware guarantee.

Fresh evaluation consumed the exact frozen artifact instead of retraining it.

## Untouched fresh court

`PRE_FRESH_LOCK.json` froze candidate identity, source blobs, evidence, artifact authority and gate before `fresh:80..119` opened.

Observed:

- frozen R2: **142/160 = 88.75%**
- R3: **147/160 = 91.875%**
- total delta: **+5**

Families:

- `conditional_regimes`: 39 → **39**
- `regime_switch`: 37 → **37**
- `causal_prerequisites`: 40 → **40**
- `implicit_goal_regimes`: 26 → **31 (+5)**

Thus every solved-count gain occurred in the intended hidden-goal family while every visible family remained exact. Fresh workflow run: `35449613862`; artifact: `10585529581`.

## Durable accepted materialization

The exact accepted artifact was archived after fresh acceptance without retraining:

- path: `model/neural-vnext-native-r3/accepted/r3.pt`
- storage: Git LFS
- LFS object SHA-256: `8c2ba53e81b51d1418cbb7abead6380808dc558cde02af9e63bf8020f92e95da`
- size: **2,854,493 bytes**
- archive commit: `9067ce9224981012a4b8e527348a74d246911a21`

CI now checks out LFS content, verifies hashes and acceptance/negative-result evidence, runs all R3 contracts, and loads the accepted checkpoint. It does not retrain the accepted candidate as an authority check.

## Post-fresh rule

`fresh:80..119` is permanently consumed.

- no post-fresh tuning;
- no mutation under this accepted authority;
- no reuse of the same fresh block for a new promotion attempt;
- future successors require a new frozen candidate and untouched fresh identities.
