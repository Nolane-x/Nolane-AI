# Neural vNext Native R2 — accepted transition-trace successor

Status: **ACCEPTED** under the preregistered parent-relative FIGG-18 fresh court `fresh:40..79`.

R2 is the first accepted successor to Neural vNext Native. The accepted parent remains bitwise frozen; R2 adds successor-owned sequence memory and a residual action scorer without retuning parent parameters.

## Accepted authority

- selected candidate: `hidden_trace_broad`
- total physical parameters: **536,085**
- successor-owned parameters: **201,986**
- checkpoint SHA-256: `bb18c0b0f398400aa0d8ab5a7a646c0ed57eec46cfb3415abe2693ab46a30c14`
- state-dict SHA-256: `20a2dcefbe6d5f22184569186716a31053231aa0599b3b52d4650fc30084f2bf`
- frozen development artifact: run `35441662592`, artifact `10583544731`
- durable repository checkpoint: `accepted/successor.pt` via Git LFS, **2,168,688 bytes**

Canonical acceptance metadata is in `ACCEPTED_AUTHORITY.json`. The immutable one-shot fresh result is summarized in `evidence/FRESH_COURT_001.json`, final closure is in `evidence/ACCEPTANCE_CLOSURE.json`, and durable checkpoint archival provenance is in `accepted/ARCHIVE_AUTHORITY.json`.

## Parent boundary

The accepted Neural vNext Native parent remains unchanged:

- physical parameters: **334,099**
- checkpoint SHA-256: `7de154972ed8e06aaf64064d4d1a6d3ee99331955b3ffb0cfdd8813643fb4f4b`
- state-dict SHA-256: `ddd0e7d8744ed18c782febece06f419ec6fd339f62a5159fa1432b5a9d7c4098`

R2 optimizer authority was restricted to successor-owned modules.

## New neural capability

R2 adds an ordered eight-transition public trace. Each token is derived only from public before/after observations and public step feedback. A learned trace encoder and GRUCell produce a recurrent transition state; a shared per-action residual scorer combines that trace state with the frozen parent's action token and recurrent hidden state.

The residual final layer is zero-initialized, so the untrained successor begins parent-equivalent.

## Development selection

On `dev:64..95`:

- frozen parent: **101/128**
- Phase-1 replay: **114/128**
- selected R2 candidate: **116/128 = 90.625%**
- `implicit_goal_regimes`: **22/32**, versus **20/32** for Phase-1 replay
- no solved-count regression versus Phase-1 replay in conditional, causal or regime-switch families

No `fresh:40..79` task was opened during selection.

## Untouched parent-relative fresh court

`PRE_FRESH_LOCK.json` froze the candidate, artifact authority, source blobs, fresh identities and promotion gate before fresh was opened.

Court:

- benchmark: `nolane-figg18-v1`
- split: `fresh`
- indices: `40..79`
- four families
- exactly **160** episodes
- parent and successor evaluated on identical identities

Preregistered promotion required all of:

1. strict total solved gain over the exact frozen parent;
2. strict gain in `implicit_goal_regimes`;
3. zero solved-count regression in every family.

Observed:

- frozen parent: **128/160 = 80.0%**
- R2: **141/160 = 88.125%**
- total delta: **+13**
- `conditional_regimes`: 39 → **40** (`+1`)
- `regime_switch`: 28 → **34** (`+6`)
- `implicit_goal_regimes`: 26 → **27** (`+1`)
- `causal_prerequisites`: 35 → **40** (`+5`)

All preregistered requirements passed. Fresh workflow run: `35445318413`; immutable fresh artifact: `10584793357`.

## Durable accepted materialization

R2 cannot honestly rely on source retraining as its canonical reconstruction path, because cross-host source training produced a disclosed negative result. Therefore the exact accepted checkpoint was archived into the repository after fresh acceptance without retraining or mutation.

- path: `model/neural-vnext-native-r2/accepted/successor.pt`
- storage: Git LFS
- LFS object SHA-256: `bb18c0b0f398400aa0d8ab5a7a646c0ed57eec46cfb3415abe2693ab46a30c14`
- size: **2,168,688 bytes**
- archive commit: `64ba56443245b90a6343b4be38a3b2edae5aaeba`

CI checks out LFS content, verifies the exact file hash/size, verifies acceptance metadata, runs all R2 contracts, and loads the accepted checkpoint. CI no longer retrains the accepted parent or successor as a promotion authority.

## Reproducibility boundary

R2 deliberately does **not** claim cross-host source-training reproducibility.

A same-source/same-image/same-PyTorch/same-seed reproduction attempt diverged before successor training, including a different frozen-parent state hash and dev score. That negative result is retained in `FRESH_GATE_PREREGISTRATION_AMENDMENT_001.json` and `PRE_FRESH_LOCK.json`.

The accepted claim is narrower and auditable: **R2 is a repository-archived immutable frozen-artifact successor, not a cross-host bitwise source-retrainable successor.**

## Post-fresh rule

`fresh:40..79` is permanently consumed for this promotion decision.

- no post-fresh tuning of this candidate;
- no mutation under the same accepted authority;
- no rerun of the same fresh block for a new promotion attempt;
- future successors require a new frozen candidate and a new untouched fresh block.
