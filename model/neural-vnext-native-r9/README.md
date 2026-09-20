# Neural vNext Native R9 — public counterfactual planner

Status: **DEVELOPMENT ONLY; fresh:200..239 UNOPENED**.

R9 keeps accepted R4 as the neural fallback and adds no trainable parameters.

For hidden-goal episodes only, it uses public state/progress constraints plus already-observed transition effects. FIGG-18 action effects are conditioned by public regime and public state parity; PublicActionMemory already records transitions at exactly that key. When the goal posterior is narrow and a previously observed local action is provably expected to reduce forward distance, R9 may override R4. Otherwise it returns R4's action.

A separate proof guard submits immediately when public `progress_signal == 1`.

Visible-target episodes are never overridden.

Selection dev: `416..447`. Reserved fresh: `200..239`. No training. Fresh remains unopened.
