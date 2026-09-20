# Neural vNext Native R6 — calibrated public-consistency successor

Status: **DEVELOPMENT ONLY; `fresh:200..239` UNOPENED**.

R6 starts again from accepted R4. R5 demonstrated that a public 125-goal consistency posterior can improve development yet reverse sign on an untouched fresh court. R6 therefore changes the mechanism rather than retuning R5: public-consistency evidence may influence actions only when it is both informative and sufficiently aligned with frozen R4's public-derived latent goal belief.

## Frozen parent

Accepted R4 is immutable:

- parameters: **877,542**
- checkpoint SHA-256: `167e845e9aa2bfe8a6431478723c777ee8a2f8e77c452192d74cd31d1959a244`
- state SHA-256: `97f114dd202b0e533c01db1adf69efe35b67db02a713d7b40dc619afd3cd2aa9`

## R6 mechanism

R6 constructs the same public-only 125-goal consistency posterior, then computes:

- normalized posterior entropy;
- posterior support fraction;
- marginal agreement with frozen R4 goal probabilities;
- a deterministic calibration gate from evidence confidence × agreement.

Uniform/weak evidence drives the gate to zero, so R6 falls back exactly to R4. The successor residual is also hard-gated by `1-target_visible`, preserving visible-target behavior structurally.

No private goal enters inference or posterior construction.

## Isolation

- hidden-goal train: `train:2560..3071`
- selection dev: `dev:224..255`
- reserved fresh: `fresh:200..239`
- consumed fresh blocks: `0..199`

Fresh remains forbidden during development.

## Development gate

A candidate is development-eligible only if it strictly improves both total solved and `implicit_goal_regimes` versus frozen R4 on the locked development block, while exactly preserving solved counts in all visible-target families.

A separately frozen candidate and PRE_FRESH_LOCK are required before any fresh court may open.
