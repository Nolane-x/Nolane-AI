# Nolane R1.9 Frontier-Generalization — Reality Report

Date: 2026-08-13

## Verdict

**ACCEPTED for a bounded new capability: learned two-step counterfactual causal rollout with fresh-split transfer.**

R1.9 extends the frozen R1.8 Conditional Causal State Machine with a small standalone recurrent rollout delta rather than enlarging the whole neural core. The accepted candidate has **78,214,173 effective parameters**, only **1,594,754** more than R1.8 (**+2.08%**).

This report intentionally does **not** claim AGI or superiority to >100B models. The external frontier harness refuses the `hard_for_gt100b` label until at least one measured >100B reference run is recorded under the same locked protocol and budget.

## Frozen parent and candidate

- Parent checkpoint: `checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt`
- Parent SHA-256: `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`
- Parent effective parameters: **76,619,419**
- R1.9 delta checkpoint: `checkpoints/Nolane-R1.9-FGR-FrontierRollout.pt`
- R1.9 delta SHA-256: `1b088c7837b76d37d3d1b288189f4a2ee9b378f069a398867ededef8c2a4d279`
- Delta parameters: **1,594,754**
- Candidate effective parameters: **78,214,173**
- Delta checkpoint bytes: **6,393,558**

The parent tensor digest was identical before and after training: `39fe33d72b9d8c2a2a79b5f814a3603eed4fcf86b8272315dec28648f07f8199`.

## Architecture change

`FrontierRolloutHead` is a behavior-preserving residual module over R1.8 public one-step predictions. It receives public state/context embeddings, an ordered two-action program, and the frozen parent one-step effects. A shared GRU refinement loop predicts only a residual over the additive R1.8 baseline. The residual head is zero-initialized, so before training the candidate is exactly equal to the parent baseline.

The design deliberately spends parameters on relational composition instead of adding generic Transformer depth:

- shared state/context/action projections;
- positional step embeddings;
- relation MLP over current state, context, two ordered actions, and parent effects;
- shared `GRUCell` iterative refinement;
- residual-effect, value, and uncertainty heads.

## FIGG-19 protocol

Source families:

- `conditional_regimes`
- `regime_switch`
- `implicit_goal_regimes`
- `causal_prerequisites`

Training used only `train` worlds:

- fit indices: `32..47` per family;
- internal validation: `48..55` per family;
- seed: `190919`;
- two-step horizon;
- at most two public states per world;
- 15 epochs, AdamW `8e-4`, weight decay `1e-4`, batch 128;
- all R1.8 parameters frozen.

The rollout rows contain public tensors and exact simulator-derived transition targets, but do not store hidden answers, oracle labels, or private task metadata as policy inputs.

## Internal held-out train-world gate

832 rollout rows, 106,496 scalar effect elements:

- additive R1.8 baseline MSE: **0.0040260815**
- R1.9 candidate MSE: **0.0024638282**
- relative improvement: **38.8033%**
- best epoch: **14**

Per-family improvement:

- `causal_prerequisites`: **28.4115%**
- `conditional_regimes`: **39.9618%**
- `implicit_goal_regimes`: **38.0184%**
- `regime_switch`: **47.3780%**

Every preregistered family beat the parent baseline.

## DEV transfer

After the checkpoint was frozen, R1.9 was evaluated on `dev` indices `0..7` per family (832 rows):

- baseline MSE: **0.0039114472**
- candidate MSE: **0.0023653259**
- relative improvement: **39.5281%**

Per-family improvement ranged from **15.7118%** to **49.6421%**. No parameter update followed DEV evaluation.

## FRESH transfer

Before opening fresh, `research/R1_9_PRE_FRESH_LOCK.json` bound the checkpoint SHA, parent SHA, split, indices, horizon, max states, and the rule `no_parameter_or_code_tuning_after_fresh=true`.

The untouched fresh split was then consumed exactly once on indices `0..7` per family (832 rows):

- baseline MSE: **0.0037984334**
- candidate MSE: **0.0022325046**
- relative improvement: **41.2256%**

Per-family improvement:

- `causal_prerequisites`: **20.8728%**
- `conditional_regimes`: **47.2622%**
- `implicit_goal_regimes`: **46.8894%**
- `regime_switch`: **44.8384%**

The R1.9 checkpoint is now frozen. This fresh split is consumed and cannot be described as untouched in future tuning.

## Frontier >100B benchmark contract

`benchmarks/frontier100b/` defines adapters/contracts inspired by public frontier evaluations while keeping claims conservative:

- ARC-AGI-2 style exact grid scoring with at most two submitted predictions;
- HLE/HLE-Verified style closed-answer scoring with only conservative case/whitespace normalization;
- FrontierMath-style verifier-backed mathematical answers;
- Terminal-Bench-style executable terminal tasks in isolated environments.

The harness does not contain leaked benchmark answers. It also refuses a `hard_for_gt100b=true` comparison record unless a named, evaluated model with >100B parameters, finite measured score, explicit budget, and locked protocol SHA is present.

**No >100B model was run during this milestone.** Therefore this milestone makes no empirical claim that Nolane beats a >100B model yet.

## Verification

Focused R1.8 + R1.9 gate after fresh lock:

```text
31 passed, 11 warnings
```

The warnings are PyTorch nested-tensor/norm-first warnings, not assertion failures.

A broad historical `pytest` run reached about 15% before the execution-time ceiling and exposed two inherited legacy failures in `tests/test_effect_progress_critic.py`. Root-cause tracing showed that the recovered R1.7 lineage already contains two `EffectProgressCritic` class definitions in `cogcoder/neural_system2.py`; the later class overrides the constructor/forward signature expected by those older tests. R1.9 did not introduce this duplicate. Because the R1.9 fresh lock had already been consumed, the model/evaluator code was not changed afterward merely to make the historical suite green.

Accordingly, the correct status is:

- focused R1.8/R1.9 research gate: **green (31/31)**;
- complete historical suite: **not claimed clean**;
- known inherited legacy interface failures: **2 observed**;
- fresh integrity: **preserved; no post-fresh model/evaluator tuning**.

## What this proves

Within FIGG-19's bounded conditional-causal worlds, the accepted R1.9 delta can learn a non-additive two-step transition residual and transfer that improvement from held-out train worlds to unseen DEV and then untouched FRESH worlds, while adding only ~1.59M parameters and leaving the 76.62M parent frozen.

## What this does not prove

This is not proof of:

- AGI;
- broad language competence;
- ARC-AGI-2, HLE, FrontierMath, SWE-bench, or Terminal-Bench performance without actually running those suites;
- superiority to any >100B model;
- long-horizon planning beyond the bounded two-step FIGG-19 rollout tested here.

The next valid milestone must use new locked splits and should target longer-horizon composition, uncertainty calibration, and external frontier-suite execution without tuning against the consumed R1.9 fresh set.
