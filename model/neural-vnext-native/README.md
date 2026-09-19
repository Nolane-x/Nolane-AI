# Neural vNext Native — accepted reproducible recurrent neural line

Status: **ACCEPTED** under its preregistered untouched FIGG-18 fresh court.

Neural vNext Native exists because the historical accepted R2.3 lineage retained hashes and metrics but not the one-weight checkpoint binary or the 11,539-state expert/DAgger cache. This line restores an end-to-end neural capability path that can be trained, reproduced, frozen, audited and evaluated entirely from repository source.

## Accepted authority

The accepted frozen candidate is:

- selected candidate: `hidden_strong_goal`
- physical parameters: **334,099**
- freeze source head: `24452b366eb6ba57ddcda9cdc670eba514cc1d0c`
- checkpoint SHA-256: `7de154972ed8e06aaf64064d4d1a6d3ee99331955b3ffb0cfdd8813643fb4f4b`
- state-dict SHA-256: `ddd0e7d8744ed18c782febece06f419ec6fd339f62a5159fa1432b5a9d7c4098`

Canonical acceptance metadata is in `ACCEPTED_AUTHORITY.json`. Development reproducibility evidence is in `evidence/DEV_HISTORY_009.json`; untouched fresh evidence is in `evidence/FRESH_COURT_001.json`.

## Public inference boundary

Inference receives only public FIGG-18 observations plus episode-local memory derived from public transitions:

- normalized public state and state parity;
- visible target and modular forward distance only when the benchmark exposes the target;
- progress signal, remaining budget and step;
- public resource/gate values;
- public regime identity;
- previous public feedback;
- per-action public transition memory, including regime/parity-conditioned effects.

Private goal/rule fields are never serialized into inference features.

The policy is action-order equivariant: a shared action encoder/scorer operates over action-memory tokens, multi-head attention summarizes the current action set, and a GRUCell carries recurrent episode state.

For hidden-target worlds, a gated residual specialist is appended to the frozen shared base. Visible-target logits bypass that specialist exactly. This prevents hidden-goal training from regressing visible-target families.

## Training program

`PREDEV_LOCK.json` preregisters the train/dev program. The accepted line uses:

- deterministic model initialization;
- a shared-base stage over all four train families;
- a frozen-base hidden-goal specialist stage;
- 2,048 unique `implicit_goal_regimes` train worlds for specialist training;
- a bounded specialist objective tournament selected only on dev evidence;
- no fresh data in training or development.

The train-only oracle is used solely as supervision. Model inputs remain public-observation-only.

## Reproducibility authority

The candidate is not accepted merely because one run produced a good score. The training runtime is pinned to a cross-run CPU path:

- PyTorch `2.9.0+cpu`;
- deterministic algorithms enabled;
- one intra-op and one inter-op thread;
- MKLDNN disabled;
- `ATEN_CPU_CAPABILITY=default`;
- `MKL_CBWR=COMPATIBLE`;
- deterministic reduction/runtime flags;
- AdamW fused/foreach paths disabled;
- gradient clipping foreach disabled.

Two independent workflow attempts reproduced the exact checkpoint SHA, state-dict SHA and development metrics. The one-shot fresh workflow then reproduced the same checkpoint again from frozen source before creating any fresh task.

## Development result

Frozen dev result: **104/128 = 81.25%**.

- `conditional_regimes`: 30/32
- `regime_switch`: 24/32
- `implicit_goal_regimes`: 24/32
- `causal_prerequisites`: 26/32

Development history, including rejected candidates and determinism blockers, is retained under `evidence/DEV_HISTORY_*.json`.

## Untouched fresh court

`PRE_FRESH_LOCK.json` froze the exact candidate, source blobs, fresh identities and promotion thresholds before the fresh split was opened.

Court:

- benchmark: `nolane-figg18-v1`
- split: `fresh`
- four families
- indices `0..39`
- exactly **160** episodes
- exact Cartesian-product identity check; duplicates and omissions fail closed

Preregistered acceptance floor:

- at least **112/160** solved;
- at least **70%** overall;
- at least **20/40** solved in every family;
- zero integrity violations.

Observed fresh result: **133/160 = 83.125% — ACCEPTED**.

- `conditional_regimes`: 36/40
- `regime_switch`: 31/40
- `implicit_goal_regimes`: 30/40
- `causal_prerequisites`: 36/40

Workflow run: `35430019167`. The immutable fresh artifact and aggregate evidence are referenced by `evidence/FRESH_COURT_001.json`.

## Post-fresh rule

This candidate is closed after fresh opening:

- no post-fresh tuning;
- no candidate mutation under this authority;
- no reuse of fresh indices `0..39` for a new promotion attempt;
- a future successor must be a new frozen candidate with a new untouched fresh block.

## Relationship to historical R2.3

Historical R2.3 remains preserved as accepted historical evidence. Neural vNext Native is the current **source-reproducible accepted neural line**.

Its 133/160 fresh result must not be presented as a direct numerical replacement for the historical R2.3 result because the fresh blocks and training programs differ. The accepted claim is narrower and stronger in a different dimension: the Native line is trainable from repository source, bitwise reproducible under its locked CPU path, and passed its own preregistered untouched fresh court.
