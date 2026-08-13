# R1.7 generic causal-role binding diagnostic

Date: 2026-08-13
Benchmark: FIGG-17 v1.1
Scope: train-only diagnostic; FIGG dev/fresh unopened.

## Question

Can the agent infer the semantic roles "controllable/current vector" and "target-like vector" from public dynamics alone, without reading field names such as `state` or `goal`?

## Diagnostic algorithm

Model input for the diagnostic used only public numeric structure and one real public intervention:

1. group public numeric list atoms by structural path identity and list positions;
2. compare the same groups before vs. after a real non-submit action;
3. identify the vector group whose values changed as the controllable/current role;
4. among same-shape vector groups that remained invariant, retain target-like candidates.

Literal key names were **not used by the role-induction algorithm**. Ground-truth names were inspected only after prediction to score the diagnostic.

## Data

100 FIGG-17 train worlds not used by earlier Goal-Difference policy candidates:
- `causal_laws`: indices 112..161 sampled across 50 worlds
- `causal_switch`: indices 112..161 sampled across 50 worlds

## Result

- `causal_laws` controllable/current role accuracy: **50/50 = 100%**
- `causal_laws` true target present among invariant same-shape candidates: **50/50 = 100%**
- `causal_switch` controllable/current role accuracy: **50/50 = 100%**
- `causal_switch` true target present among invariant same-shape candidates: **50/50 = 100%**
- overall current-role identification: **100/100**
- overall target-candidate retention: **100/100**
- observed bad examples: **0**

## Interpretation

The main causal policy bottleneck is unlikely to require a larger generic attention head. Public intervention dynamics already provide an extremely strong, field-name-agnostic role signal. R1.7 should explicitly bind this signal into the neural world/policy representation.

Next candidate: **Causal Role-Goal Matcher (CRGM)**.

Planned constraints:
- role extraction remains parameter-free and key-name agnostic;
- ambiguous or missing role evidence yields zero/low role confidence rather than guessing;
- accepted Causal Law representation remains frozen during the first CRGM world-model phase;
- train on a new train-only range starting after index 161;
- internal gate must test **action ranking as well as MSE**, because Goal-Difference demonstrated that low MSE alone can hide poor policy ranking;
- no FIGG dev/fresh use before preregistered authorization.
