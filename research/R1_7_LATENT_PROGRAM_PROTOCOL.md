# R1.7 Latent Program Ranker template-holdout protocol

Date: 2026-08-13
Parent world representation: accepted Goal-Difference checkpoint `84c00198b9cc0d65e68789b445c3635dba8403e105b4fc9d05029e047ef3a11a`
Benchmark: FIGG-17 v1.1

## Purpose

Test whether the frozen 384D Goal-Difference relational representation contains enough compositional structure to induce the next operation of an unseen program template when augmented by a horizon-general sinusoidal program-phase encoding.

This is intentionally smaller than a recurrent program machine. A recurrent state is not justified unless this shared phase-conditioned ranker fails template transfer.

## Isolation and template holdout

- FIGG-17 `train` only.
- family: `composition_holdout` only.
- world indices: `218..281` inclusive (64 worlds).
- template id is the benchmark's train template selector `index % 8`.
- fit templates: ids `0,1,2,3,4,5` only — 48 worlds.
- internal-validation templates: ids `6,7` only — 16 worlds, **never shown during optimization**.
- seed: `170817`.
- no FIGG dev/fresh task may be instantiated during training or selection.

## Teacher and rows

Each world follows the exact functional oracle trajectory. For every teacher decision state cache:
- frozen full parent `base_logits`;
- frozen Goal-Difference `policy_features` (384D per dynamic action);
- program phase = zero-based decision-step ordinal represented by deterministic sinusoidal encoding;
- teacher action label;
- whether the teacher label is `submit`;
- train program template id.

Hidden target program may select the teacher label only. Neural inputs are public observation/action representations.

## Architecture / optimizer

Shared action-wise ranker:
`[policy_features 384D ; phase 32D] -> Linear(416,128) -> GELU -> LayerNorm(128) -> Linear(128,1)`.

- final output zero-initialized;
- parameters: 53,761;
- effective live architecture: 75,027,978 (<96M);
- trainable scope exactly `latent_program_ranker.*`;
- AdamW, lr `0.001`, weight decay `0.0001`;
- 60 epochs;
- gradient norm clip 1.0.

## Objective

Cross-entropy on the exact teacher action across the dynamic action set. Checkpoint selection is based only on the held-out-template gate below, never training loss.

## Baseline and metrics

Baseline on the exact same cached rows: frozen **full parent base logits** argmax.

Report separately:
- operation-state accuracy (teacher label is non-submit);
- submit-state accuracy;
- operation accuracy for held-out template id 6;
- operation accuracy for held-out template id 7.

## Internal acceptance gate

The ranker may proceed to a new train-only policy-integration phase only if all are true on templates 6 and 7:
1. candidate operation accuracy is **strictly higher** than parent operation accuracy;
2. candidate submit accuracy is no lower than parent submit accuracy;
3. template-6 operation accuracy is no lower than its parent baseline;
4. template-7 operation accuracy is no lower than its parent baseline;
5. no parameter outside `latent_program_ranker.*` receives gradient;
6. FIGG dev/fresh remain unopened.

Passing is evidence for held-out-template operation induction, not closed-loop capability. A new train-only integration slice and preregistered FIGG dev gate are still mandatory.
