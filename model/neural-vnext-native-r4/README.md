# Neural vNext Native R4 — fresh-accepted latent goal belief successor

Status: **FRESH ACCEPTED; durable repository archive pending**.

R4 extends accepted R3 with an explicit learned latent belief over the hidden goal. The accepted candidate is `latent_goal_guarded`; R3 remains fully frozen.

## Accepted fresh result

On untouched `fresh:120..159`:

- frozen R3: **146/160 = 91.25%**
- R4: **148/160 = 92.5%**
- total delta: **+2**
- `implicit_goal_regimes`: **29 → 31 (+2)**
- `conditional_regimes`: **40 → 40**
- `regime_switch`: **38 → 38**
- `causal_prerequisites`: **39 → 39**

Every visible-target family remained exact, and every solved-count gain occurred in the intended hidden-goal family. The one-shot preregistered gate passed.

Fresh workflow: `35451949227`. Fresh artifact: `10587106977`.

## Frozen candidate

- selected candidate: `latent_goal_guarded`
- total parameters: **877,542**
- R4-owned parameters: **169,552**
- checkpoint SHA-256: `167e845e9aa2bfe8a6431478723c777ee8a2f8e77c452192d74cd31d1959a244`
- state SHA-256: `97f114dd202b0e533c01db1adf69efe35b67db02a713d7b40dc619afd3cd2aa9`

Development on `dev:160..191`: frozen R3 **114/128** → R4 **117/128**. All +3 solves were in `implicit_goal_regimes` (22 → 25), with visible families exact.

## Reproducibility boundary

Two independent workflows at the same locked source head selected the same candidate and reproduced the exact same dev solved counts, but checkpoint/state hashes differed. This negative result is frozen in `evidence/DEV_REPRO_NEGATIVE_001.json`.

Therefore R4 does **not** claim bitwise source-training reproducibility. Canonical authority was fixed before fresh as the **first completed successful dev run at the locked source head**: run `35451337745`, artifact `10586044507`.

## Architecture

R4 learns a 3 × 5 latent goal posterior from public action-attributed transition/progress history. Private hidden-goal coordinates are permitted only as train-only auxiliary labels. Inference, dev and fresh consume public observations and public episode-local memories only.

The R4 residual is hard-gated by `1-target_visible`; visible-target behavior is structurally frozen R3 behavior.

## Post-fresh rule

`fresh:120..159` is permanently consumed. No post-fresh training, tuning, candidate mutation or reuse of this block for promotion is allowed.

The remaining closure step is durable archival of the exact accepted checkpoint into the repository without retraining.
