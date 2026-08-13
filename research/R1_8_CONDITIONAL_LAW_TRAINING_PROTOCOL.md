# R1.8 Conditional Neural Law Prior — Train-Internal Protocol

Date: 2026-08-13
Parent: R1.7 Phase-C OperatorExecutor `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`
Benchmark: FIGG-18 v1

## Isolation
Only FIGG-18 `train` tasks may enter collection or optimization. FIGG-18 dev and fresh are forbidden in this stage.

Families: `conditional_regimes`, `regime_switch`, `implicit_goal_regimes`, `causal_prerequisites`.

Fit indices: `0..23` inclusive per family (96 worlds).
Internal-validation indices: `24..31` inclusive per family (32 worlds).
Seed: `180318`.
Exploration prefix: six least-used safe non-submit interventions when possible, followed by exact oracle continuation.
Maximum collected steps: 16.

## Model scope
Candidate architecture adds 1,231,873 `conditional_law_*` parameters, producing 76,619,419 effective parameters. The R1.7 parent, program executor, PSR, old causal-law system, action encoder, and all policy heads remain frozen.

Inputs are public-derived only: structured state sketch, key-name-agnostic public context fingerprint, frozen dynamic action embedding, context-indexed observed effect memory, and evidence metadata `(count, consistency, context similarity)`.

Targets are counterfactual public structured successor effects produced by cloning only the **train** simulator and comparing public before/after observations. Hidden simulator state is never a neural input.

## Optimizer
- AdamW
- learning rate: `3e-4`
- weight decay: `1e-4`
- batch size: `128`
- epochs: `30`
- gradient clipping: `1.0`

The effect world-model loss is MSE over legal non-submit action effects. The confidence output is not accepted as calibrated evidence in this phase; reliability is separately calibrated in Task 4.

## Baseline and acceptance
Baseline is the context-indexed evidence-memory prediction on the exact same state/action/context. Unseen actions predict zero; seen actions reuse their context-compatible observed-effect estimate.

A checkpoint is accepted for Task 4 only if:
1. aggregate validation MSE is strictly below the evidence-memory baseline;
2. every one of the four FIGG-18 families has candidate MSE no greater than its own baseline MSE;
3. effective parameter count remains below 96,000,000;
4. checkpoint report binds the exact Phase-C parent SHA and protocol values above.

A pass proves only held-out train-world transition generalization. It is not a closed-loop capability claim and does not authorize FIGG-18 fresh.
