# Neural Public R18 Recursive Core

Status: **independent neural-only recovery candidate — not an accepted successor to R2.3**

This candidate exists because the exact accepted R2.3 one-weight binary and its 11,539-state training cache are no longer present in the Git tree, Releases, Actions artifacts or currently searchable Library backups. It does not weaken the R2.3/vNext preregistered court and does not pretend that missing weights were reconstructed.

## What is neural here

The candidate is a self-contained trainable recurrent policy:

- order-sensitive learned byte encoders for the rendered public observation and public action descriptions;
- recurrent episodic memory updated only from the current public observation, the previously selected public action and public transition feedback;
- a weight-shared recurrent reasoning cell over the current action set;
- trainable action/value/ponder heads;
- end-to-end BPTT over teacher episodes.

No External Core output is an input. There is no inference-time oracle interface and no private FIGG-18 simulator field in the neural forward signature.

## Training boundary

Training uses only FIGG-18 `train` worlds. A public exploration curriculum probes opaque actions and the benchmark oracle may choose **training targets only**. The oracle is evaluator/teacher-side privileged supervision; its state is never serialized into a model input.

Development is fully closed-loop neural-only: the model receives public observations, chooses its own actions, receives only public transition feedback, and carries its own recurrent state. The generic evaluator refuses the `fresh` split.

## Fresh boundary

`PREDEV_LOCK.json` reserves fresh indices **1160–1199** (160 episodes across four families). Those indices remain closed until a checkpoint and all decision thresholds are frozen. This recovery lineage is not authorized to replace R2.3 merely by passing its own fresh court; an accepted successor still requires a valid parent-versus-candidate neural-only comparison.

## Executable path

`scripts/train_and_dev.py` performs:

1. train-index authority checks;
2. deterministic teacher-corpus collection;
3. neural BPTT training;
4. physical parameter audit;
5. checkpoint freeze;
6. reload of the exact frozen bytes;
7. oracle-free closed-loop dev evaluation;
8. evidence emission with `fresh_consumed=false`.
