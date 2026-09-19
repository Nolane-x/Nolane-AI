# Neural vNext Native S1 — dual-timescale recurrent successor

Status: **development-only candidate; fresh 40..79 unopened**.

S1 is the first successor to the accepted source-reproducible Neural vNext Native line. It does not modify the accepted parent after its fresh-court closure.

## Parent authority

Frozen parent:

- authority: `Neural-vNext-Native-Recurrent`
- parameters: **334,099**
- checkpoint SHA-256: `7de154972ed8e06aaf64064d4d1a6d3ee99331955b3ffb0cfdd8813643fb4f4b`
- state-dict SHA-256: `ddd0e7d8744ed18c782febece06f419ec6fd339f62a5159fa1432b5a9d7c4098`
- accepted fresh court: 133/160 on parent fresh indices 0..39

Parent parameters are frozen bitwise during S1 training.

## Why S1 exists

The accepted parent already generalizes strongly, but its remaining misses are concentrated in long-horizon hidden-goal inference, regime switching and prerequisite reasoning.

S1 adds a learned recurrent residual rather than rewriting the parent:

- a fast GRU reacts to each public state/evidence update;
- a slow GRU accumulates longer-timescale evidence;
- a learned public-evidence gate controls slow-state updates;
- a shared per-action residual scorer preserves action-order equivariance;
- the final residual layer is zero-initialized, so S1 starts exactly as the accepted parent.

No private task fields are used at inference.

## Clean successor evaluation

S1 does not select on the parent development block.

- train: `train:0..511` for each FIGG-18 family
- new S1 dev: `dev:32..63`
- old parent dev `dev:0..31`: not used for S1 selection
- parent fresh `fresh:0..39`: consumed and forbidden
- reserved S1 fresh: `fresh:40..79` — **UNOPENED**

The full preregistration is in `PREDEV_LOCK.json`.

## Freeze readiness

A development candidate is not eligible to freeze merely for beating the parent by one lucky episode. Before a separate S1 PRE_FRESH lock can exist, the selected candidate must:

- gain at least **+8 solved episodes** over the frozen parent on new dev 32..63;
- regress by at most **1 solved episode** in any family;
- preserve the exact parent state-dict SHA.

Fresh 40..79 remains unavailable until the exact S1 checkpoint is independently reproduced and frozen.
