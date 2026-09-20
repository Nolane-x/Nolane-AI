# Neural vNext Native R7 — thresholded public-consistency successor

Status: **DEVELOPMENT ONLY; `fresh:200..239` UNOPENED**.

R7 starts from accepted R4 after R5 failed fresh and R6 failed its primary development gate. It changes the intervention rule again: a public-consistency residual is forbidden while the public hidden-goal hypothesis set is broad.

## Frozen parent

Accepted R4:
- parameters: **877,542**
- checkpoint SHA-256: `167e845e9aa2bfe8a6431478723c777ee8a2f8e77c452192d74cd31d1959a244`
- state SHA-256: `97f114dd202b0e533c01db1adf69efe35b67db02a713d7b40dc619afd3cd2aa9`

## Mechanism

R7 enumerates the same 125 possible hidden goals using public state/progress evidence. Each candidate preregisters a maximum public posterior support size.

If current support is larger than that threshold, `evidence_gate = 0` exactly and action logits equal frozen R4. When evidence becomes sharp enough, a confidence-weighted successor residual may act.

The residual is separately multiplied by `1-target_visible`, so visible-target behavior remains structurally identical to R4.

## Isolation

- train: `train:3072..3583`
- primary dev: `dev:288..319`
- reserved fresh: `fresh:200..239`
- consumed fresh: `0..199`

No fresh tasks are permitted during development.

## Development gate

Strict total + implicit-goal gain over frozen R4, with exact solved counts on all visible-target families. Passing primary development alone will not authorize fresh; a disjoint confirmation block will be preregistered before any court can open.
