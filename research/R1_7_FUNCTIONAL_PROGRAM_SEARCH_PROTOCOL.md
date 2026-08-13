# R1.7 Phase C Functional Program Search gate

Date: 2026-08-13
Parent: accepted `Nolane-R1.7-NCPM-OperatorExecutor.pt`
Parent SHA-256: `bfea6717...` (full hash is bound in the accepted checkpoint/delivery record)
Benchmark: FIGG-17 v1.1

## Purpose

Test whether a frozen neural operator model can be composed into a short latent program from public demonstrations, without using hidden program/template labels as model inputs and without training any new parameter.

## Isolation

- Split: FIGG-17 `train` only.
- Family: `composition_holdout` only.
- World indices: `522..585` inclusive (64 worlds).
- These worlds are disjoint from Operator Executor fit `282..481` and internal validation `482..521`.
- `dev` and `fresh` remain unopened.

## Inputs

Program inference may use only:
- public demonstration vector pairs extracted without literal field-name semantics;
- public dynamic action descriptions;
- the frozen accepted Neural Operator Executor.

The evaluator may inspect task outcome (`solved`) after actions are executed. Hidden `oracle_program`/template IDs are forbidden as search inputs or ranking signals.

## Search

- Search both global orientations of each public demonstration pair.
- Search shortest exact program first.
- Maximum horizon: 4.
- Rollouts are performed through the frozen neural executor.
- If no exact program is found, keep the best partial hypothesis for diagnostics, but it is not counted as an exact inference.

## Execution

Execute the inferred action sequence in the real FIGG task, then issue the public submit action. Functional equivalence is accepted: the inferred sequence does not need to equal the hidden generating template if it solves the real task.

## Metrics

- `demo_exact_rate`: fraction of worlds where neural search finds a program matching all public demonstrations exactly.
- `task_solve_rate`: fraction solved after real execution + submit.
- `false_exact_rate`: fraction where search claims demo-exact but real execution fails.
- `mean_action_efficiency`: reference program actions divided by used pre-submit actions for solved tasks, capped at 1.0 for reporting.

## Acceptance gate

Functional Program Search may proceed to a separate preregistered FIGG-17 dev gate only if all conditions hold:
1. `demo_exact_rate >= 0.95`;
2. `task_solve_rate >= 0.90`;
3. `false_exact_rate <= 0.05`;
4. no new trainable parameters are introduced;
5. the exact accepted Operator Executor checkpoint remains frozen.

A pass is evidence for learned operator composition on train-held-out worlds only. It is not evidence for FIGG-17 dev/fresh generalization until those gates are separately locked and evaluated.
