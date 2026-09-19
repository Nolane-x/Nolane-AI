# Neural vNext Native R5 — Public Consistency successor

Status: **DEVELOPMENT ONLY; `fresh:160..199` UNOPENED**.

R5 starts from accepted R4 and targets the remaining hidden-goal failures without mutating the accepted parent. R4 learns a soft latent goal posterior from action-attributed history. R5 adds a separate public-evidence consistency posterior that enumerates all 125 possible 3×5 goals and removes hypotheses inconsistent with the public state/progress signal.

## Frozen parent

Accepted R4 is immutable:

- total parameters: **877,542**;
- checkpoint SHA-256: `167e845e9aa2bfe8a6431478723c777ee8a2f8e77c452192d74cd31d1959a244`;
- state SHA-256: `97f114dd202b0e533c01db1adf69efe35b67db02a713d7b40dc619afd3cd2aa9`.

R5 optimization is restricted to R5-owned modules.

## Mechanism

`PublicGoalConsistencyBelief` uses only the current public state and public `progress_signal`. For each of the 125 candidate goals it computes the forward modular distance implied by FIGG-18 and retains only goals whose public progress matches the observation. Evidence is intersected over the episode.

No private goal is accepted by the R5 inference API. The resulting 125-way posterior, its 15 coordinate marginals, entropy and support fraction are projected into a trainable residual action scorer together with frozen R4/R3/R2/native representations.

The final R5 residual is zero-initialized and multiplied by `1 - target_visible`, so an untrained R5 is exactly R4-equivalent and visible-target behavior is structurally frozen.

## Isolation

- hidden-goal train: `train:2048..2559`;
- selection dev: `dev:192..223`;
- reserved untouched future fresh: `fresh:160..199`;
- consumed fresh blocks `0..159` are forbidden for R5 promotion.

No fresh evaluator exists in the development closure path.

## Development gate

A candidate is eligible only if it strictly improves both total solved and `implicit_goal_regimes` solved over frozen R4 on `dev:192..223`, while exactly preserving solved counts for `conditional_regimes`, `regime_switch`, and `causal_prerequisites`.

Only after an eligible candidate is frozen may a separately bound one-shot fresh court be created.
