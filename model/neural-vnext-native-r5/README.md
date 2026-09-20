# Neural vNext Native R5 — frozen public-consistency successor

Status: **FROZEN PRE-FRESH; `fresh:160..199` UNOPENED**.

R5 starts from accepted R4 and adds a public-only consistency posterior over all 125 possible hidden goals. It intersects hypotheses using only public state and public progress evidence, then feeds that posterior into a hidden-target-only neural residual. No private goal is accepted by the R5 inference boundary.

## Frozen parent

Accepted R4 remains immutable:

- parameters: **877,542**
- checkpoint SHA-256: `167e845e9aa2bfe8a6431478723c777ee8a2f8e77c452192d74cd31d1959a244`
- state SHA-256: `97f114dd202b0e533c01db1adf69efe35b67db02a713d7b40dc619afd3cd2aa9`

## Frozen development candidate

Selected candidate: `public_consistency_broad`

- total parameters: **1,013,511**
- R5-owned parameters: **135,969**
- checkpoint SHA-256: `6188ee06c481d9ace7b6a9e5bab9d913574230916f7a54facb7117b54431b576`
- state SHA-256: `ee8c64602d200a57b1b5953f4cbc9b8d7ac42acdfb6c7db6af37deb4a2022731`

On `dev:192..223`:

- frozen R4: **117/128**
- R5: **119/128**
- `implicit_goal_regimes`: **25/32 → 27/32**
- all visible-target family solved counts remain exact.

The guarded candidate regressed to 116/128 and was rejected.

## Reproduction

Two independent GitHub workflow executions at the exact locked source head produced byte-identical:

- `r5.pt`
- `r5.manifest.json`
- `r5.dev.json`

This is recorded as **workflow-level bitwise reproduction**. It is not a universal cross-host/hardware guarantee. Canonical evidence is `evidence/DEV_REPRO_001.json`.

## Fresh isolation

`PRE_FRESH_LOCK.json` now freezes the exact candidate artifact, source blobs, dev evidence and gate.

- consumed fresh blocks: `0..159`
- reserved R5 court: `fresh:160..199`
- court status: **UNOPENED**
- no post-fresh tuning
- no reuse after failure

The next legal step is a separately bound single-use fresh workflow consuming the exact frozen artifact.
