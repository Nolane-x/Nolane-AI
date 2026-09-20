# Neural vNext Native R17 — model-based neural planning

Status: **DEVELOPMENT LOCKED; fresh unopened**.

R17 combines the two strongest negative findings so far:

- R10: multi-step search had almost no coverage because exact symbolic transition memory was too sparse.
- R16: a learned public world model reached ~99% train-only calibrated transition precision and changed trajectories, but one-step use did not improve solved count.

R17 therefore trains a fresh, disjoint public dynamics ensemble and uses it for **2–3 step model-based planning**. Accepted R11 remains the exact fallback.

No private goal or oracle action enters world-model training or inference. Counterfactual rollouts never fabricate hidden-goal progress feedback; they advance only public state/parity/step/budget features.

Locked identities:

- train: `4480..4735`
- train-only calibration: `4736..4863`
- primary dev: `928..959`
- confirmation: `960..991`
- reserved fresh: `280..319` — **UNOPENED**
