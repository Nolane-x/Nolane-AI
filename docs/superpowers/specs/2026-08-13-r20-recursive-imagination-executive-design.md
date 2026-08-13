# R2.0 Recursive Imagination Executive Design

Date: 2026-08-13
Status: approved for implementation by the user

## Objective

Evolve Nolane R1.9 from a strong bounded two-step causal world-model into a compact closed-loop agent that can recursively imagine multi-step futures, allocate more inference compute only when needed, choose actions from those imagined futures, and preserve strict benchmark integrity.

The primary research goal is **more intelligence per parameter**, not parameter scaling.

## Immutable parent

The deployment parent is the accepted R1.9 one-weight artifact:

- artifact: `Nolane-R1.9-78M-STRONGEST-ONE-WEIGHT-FP16.pt`
- SHA-256: `6081a38f65142ae06dc36cba1c9a567a9d0754c08d683d89a8e76f7aade9c52a`
- effective parameters: **78,214,173**
- contents: R1.8 ConditionalLaw neural parent + R1.9 FrontierRollout delta
- measured fresh rollout improvement: **41.2233%** for the one-weight FP16-storage artifact

R2.0 must not modify the accepted R1.9 parent weights during the first milestone. R2.0 is trained as a delta and is accepted only if it improves closed-loop behavior under a locked protocol.

## Parameter budget

R2.0 target effective parameter count: **<79,000,000**.

Therefore all new trainable R2.0 parameters combined must remain below **785,827 parameters**. The implementation should target <=700,000 parameters to preserve a safety margin.

Increasing reasoning depth from 2 to 4, 8, or 16 imagined steps must not duplicate neural parameters. Reasoning depth is an inference-compute dimension.

## Architecture

### 1. Recursive imagination engine

The existing R1.9 `FrontierRolloutHead` is reused as the learned transition primitive. R2.0 introduces an algorithmic recursive planner that repeatedly applies the learned world-model to imagined state sketches.

For a candidate action sequence:

1. begin with the current public state sketch and public context;
2. obtain frozen R1.8/R1.9 one-step and residual transition predictions;
3. update the imagined state sketch with the predicted effect;
4. propagate predicted value and uncertainty;
5. repeat with the **same weights** for the next imagined step;
6. score complete/partial trajectories using predicted progress, uncertainty penalty, and remaining budget.

The supported reasoning depths are `1, 2, 4, 8, 16`. No trainable depth-specific embedding table is required; depth is represented with deterministic sinusoidal/scalar features or recurrent state.

### 2. Bounded beam/counterfactual search

The planner uses bounded beam search over public actions. Default beam width is small (2-4) to prevent exponential explosion. Submit/terminal actions remain legal only when the executive judges sufficient progress/confidence.

No hidden simulator fields, oracle plan, task solution, answer key, or verifier internals may be consumed at inference time.

### 3. Integrated executive delta

A new `RecursiveImaginationExecutive` replaces the need to deploy a second independent R1.8 ActiveExecutive policy.

It consumes only public/neural features:

- current state sketch;
- context fingerprint;
- action embedding;
- frozen ConditionalLaw hidden/effect summaries;
- R1.9 imagined rollout summary for that action;
- predicted uncertainty/value;
- observed progress signal;
- budget fraction;
- previous public feedback;
- recurrent executive state.

It produces:

- action logit for every available public action;
- recurrent executive state;
- stop/continue logit;
- calibrated success/confidence estimate;
- requested imagination depth distribution over `{1,2,4,8,16}`.

The recurrent executive cell is weight-shared across environment steps.

### 4. Adaptive compute

The model learns when additional imagination is useful. Inference begins cheaply and may deepen when uncertainty is high or the top candidate actions are close in score.

Acceptance requires evidence that adaptive-depth inference is not merely wasting compute: it must improve solve rate or reduce errors relative to fixed shallow inference on the same held-out tasks.

## Training protocol

R2.0 training is imitation/supervision only on procedural `train` worlds. Oracle planning may generate training labels, but oracle actions/hidden state are never stored as inference features.

Recommended locked ranges per FIGG-18 family:

- fit: train indices `400..463`;
- internal validation: `464..479`;
- untouched train closed-loop gate: `480..499`.

The exact ranges and seed must be written to a pre-training lock before training begins.

Only R2.0 delta parameters are trainable. R1.9 parent tensor hashes must be identical before and after training.

Checkpoint selection is based only on internal validation loss/closed-loop proxy defined before evaluation.

## Closed-loop evaluation

The primary metric is exact task solve rate, not teacher-forced token/action accuracy.

Every locked evaluation must run at least these ablations on identical task instances:

1. `random` — deterministic seeded random policy;
2. `greedy_parent` — R1.9/R1.8 parent-only shallow policy without recursive imagination;
3. `fixed_depth_2` — R2.0 executive with two-step imagination;
4. `fixed_depth_8` — R2.0 executive with deeper imagination;
5. `adaptive` — R2.0 chooses its own depth;
6. `workspace_only` when a non-neural workspace baseline exists;
7. `full` only when tools/workspace are intentionally enabled.

Neural capability claims must be based on neural-only or explicitly labeled neural+algorithmic search conditions. Habitat/tool performance must never be silently attributed to the neural weight.

## Acceptance gate

R2.0 is accepted only if all of the following hold on the untouched train closed-loop gate:

- effective parameters <79,000,000;
- R1.9 parent weights remain byte/tensor-digest unchanged;
- adaptive or fixed-depth recursive imagination improves aggregate solve rate over the preregistered shallow parent baseline by at least **10 percentage points**, unless the baseline is already >=90%, in which case relative error reduction >=25% is sufficient;
- no preregistered family loses more than 5 percentage points versus the shallow parent baseline;
- deeper/adaptive computation demonstrates a measurable benefit over depth-1/shallow inference on hard tasks;
- no hidden/private fields enter inference features;
- focused R1.9 regression tests remain green;
- checkpoint reload reproduces evaluation metrics within deterministic tolerance.

If the gate fails, the candidate is recorded as rejected and the fresh split remains unopened.

## DEV/FRESH discipline

DEV is opened only after the train gate accepts and the checkpoint is frozen.

Before FRESH, a pre-fresh lock binds:

- checkpoint SHA-256;
- parent SHA-256;
- evaluator source SHA/version;
- exact fresh indices;
- beam width/depth policy;
- inference budget;
- all ablation modes.

FRESH is consumed once. No model, evaluator, depth threshold, beam width, or calibration tuning occurs after FRESH is opened for that checkpoint.

R1.9 fresh indices already consumed are not reused as untouched evidence for R2.0.

## Calibration

R2.0 reports confidence calibration alongside solve rate. At minimum:

- Brier score;
- expected calibration error using a fixed bin scheme;
- high-confidence error rate.

Confidence is not accepted as a useful capability if it becomes sharper while less accurate.

## Frontier benchmark ladder

After R2.0 passes local closed-loop gates, later milestones use the existing `benchmarks/frontier100b/` evidence contract to run public frontier evaluations with exact or executable verifiers:

- ARC-AGI-2-style abstraction/generalization;
- HLE/HLE-Verified-style expert closed answers;
- FrontierMath-style verifier-backed mathematics;
- Terminal-Bench-style executable agent tasks.

A claim that Nolane beats or is competitive with >100B systems requires real reference runs under recorded inference budgets. Local procedural wins alone never authorize that claim.

## Deployment artifact

The user-facing output remains **one strongest weight**.

After acceptance, the R1.9 parent and R2.0 delta are bundled into one standalone FP16-storage checkpoint with:

- architecture metadata;
- exact effective parameter count;
- parent and delta provenance hashes;
- runtime loader;
- locked benchmark summary.

Historical checkpoints may remain in recovery storage, but ordinary distribution exposes one current strongest weight.

## Milestone persistence

Every completed R2.0 milestone must produce:

- source/tests/docs/results;
- current strongest one-weight artifact;
- SHA-256 checksum;
- complete ZIP delivery;
- verified ZIP integrity;
- GitHub `main` publication for all practical source/provenance artifacts;
- ChatGPT Library persistence of the complete delivery and the one-weight artifact.

## Scientific claim boundary

R2.0 aims to establish stronger compact long-horizon closed-loop reasoning. Passing its local gates would not by itself prove AGI or superiority to large frontier models. Those claims require broad external benchmark evidence under controlled budgets.
