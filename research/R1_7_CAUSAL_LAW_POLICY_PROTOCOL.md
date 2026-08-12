# R1.7 Causal Law policy-calibration protocol

Date: 2026-08-12
Parent candidate: `Nolane-R1.7-NCPM-CausalLaws.pt` (`e6c99e5944b68c2fde7f89e7dec478b54e93f3a3250adfd806e1020b46239dbc`)
Benchmark: FIGG-17 v1.1

The law-world model has already passed its train-internal successor-delta gate. This stage teaches only a small residual policy how to *use* the frozen law representation. It does not update the R1.6 parent or the learned law-world parameters.

## Isolation

- FIGG-17 `train` only.
- fit indices: `32..43` per family.
- internal-validation indices: `44..47` per family.
- families: `causal_laws`, `causal_switch`, `goal_inference`, `composition_holdout`.
- seed: `170217`.
- no FIGG-17 dev/fresh task is instantiated during calibration.

## Teacher behavior

For causal/implicit-goal families the teacher explores least-used non-submit actions for six public transitions, then follows the exact oracle from the resulting state. Composition tasks follow the exact functional oracle program. Hidden simulator information may choose teacher labels only; model inputs remain public observations/actions/feedback.

## Optimizer scope

Exactly:
- `causal_law_policy_head.*`
- `causal_law_policy_scale`

All other parameters, including the 1,118,592 accepted law-world parameters, are frozen.

## Internal gate

The calibrated policy may proceed to FIGG-17 dev only if:
1. internal-validation cross-entropy is lower than the scale-zero parent;
2. overall teacher-action accuracy is no lower;
3. combined `causal_laws` + `causal_switch` accuracy is strictly higher;
4. combined `goal_inference` + `composition_holdout` preservation accuracy is no lower.

Teacher-forced improvement is not a capability claim; it only authorizes a preregistered closed-loop dev gate.
