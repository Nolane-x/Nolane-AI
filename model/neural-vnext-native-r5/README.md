# Neural vNext Native R5 — rejected public-consistency successor

Status: **FRESH REJECTED; candidate closed without promotion**.

R5 started from accepted R4 and added a public-only consistency posterior over all 125 possible hidden goals. It used only public state/progress evidence at inference and was structurally gated off for visible targets.

## Frozen parent

Accepted R4 remains the authority:

- parameters: **877,542**
- checkpoint SHA-256: `167e845e9aa2bfe8a6431478723c777ee8a2f8e77c452192d74cd31d1959a244`
- state SHA-256: `97f114dd202b0e533c01db1adf69efe35b67db02a713d7b40dc619afd3cd2aa9`

## Rejected R5 candidate

Selected candidate: `public_consistency_broad`

- total parameters: **1,013,511**
- R5-owned parameters: **135,969**
- checkpoint SHA-256: `6188ee06c481d9ace7b6a9e5bab9d913574230916f7a54facb7117b54431b576`
- state SHA-256: `ee8c64602d200a57b1b5953f4cbc9b8d7ac42acdfb6c7db6af37deb4a2022731`

On locked development `dev:192..223`:

- frozen R4: **117/128**
- R5: **119/128**
- `implicit_goal_regimes`: **25/32 → 27/32**
- visible-target family solved counts stayed exact.

The exact dev checkpoint/state/manifest/result files reproduced across two workflow executions at the locked source head. This remains workflow-level evidence only.

## Untouched fresh court — REJECTED

The one-shot court opened `fresh:160..199` exactly once.

- frozen R4: **142/160**
- R5: **140/160**
- total delta: **-2**
- `implicit_goal_regimes`: **29 → 27 (-2)**
- every visible-target family solved count remained exact.

Workflow run: `35478051023`.
Immutable artifact: `10594294126`.
Artifact digest: `sha256:63d50d4d1062883b263e702222b8a967467c09ba7726d5d919cd8090033d64e5`.

The preregistered promotion gate therefore failed.

## Negative-result governance

`fresh:160..199` is permanently consumed.

- R5 may not be tuned after seeing this court;
- R5 may not rerun the same fresh block;
- this exact candidate may not be promoted;
- R5 should close without merge;
- any successor must start from the accepted R4 authority with a new candidate identity and a new untouched fresh block.

This failure is intentionally preserved: a dev gain did not generalize to fresh.
