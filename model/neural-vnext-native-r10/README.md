# Neural vNext Native R10 — multi-step public counterfactual planner

Status: **DEVELOPMENT ONLY; confirmation and fresh UNOPENED**.

R10 starts from accepted R9. It keeps R9's accepted hidden-goal support threshold (`max_support=3`) fixed and tests only one new capability: conservative multi-step planning over public transition effects already observed in episode memory.

R10 adds **zero learned parameters**.

## Locked courts

- primary selection: `dev:480..511`
- disjoint confirmation: `dev:512..543`
- reserved fresh: `fresh:240..279`
- consumed fresh: `0..239`

## Mechanism

R9 remains the exact fallback. R10 may override it only when every transition in a 2–4 step candidate path has already been observed at the exact public regime + state-parity key.

The first R10 action may not be worse than R9's first action under the same known public model, and the complete known path must have strictly lower expected hidden-goal distance than the best known continuation beginning with R9's action.

Visible-target episodes are never overridden. No private goal is read.

No confirmation or fresh identity may be instantiated during primary development.
