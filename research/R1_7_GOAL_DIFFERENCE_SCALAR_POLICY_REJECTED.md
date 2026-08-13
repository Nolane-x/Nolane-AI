# R1.7 Goal-Difference one-scalar policy bridge — REJECTED

Date: 2026-08-13
Parent: `Nolane-R1.7-NCPM-GoalDifference.pt` (`84c00198b9cc0d65e68789b445c3635dba8403e105b4fc9d05029e047ef3a11a`)
Benchmark: FIGG-17 v1.1 train-only calibration

The preregistered calibration used fit indices 80..91 and internal validation 92..95 across all four FIGG-17 families. Only `goal_difference_policy_scale` was trainable.

## Result

- accepted for dev: **false**
- base validation CE: `5.498825550079346`
- lowest observed validation CE: `5.498763084411621`
- base overall action accuracy: `0.20967741935483872`
- action accuracy at the lowest-CE scale: unchanged `0.20967741935483872`
- base causal_laws accuracy: `0.27906976744186046`
- base causal_switch accuracy: `0.3125`
- both remained unchanged throughout calibration
- scalar `tanh(scale)` approached approximately `0.98` but changed no validation argmax decisions
- no policy checkpoint was created
- FIGG-17 dev/fresh remained unopened by this experiment

Interpretation: the accepted Goal-Difference world model contains useful counterfactual progress information, but a single globally bounded additive scalar is not expressive/strong enough to convert that information into action selection. The world-model checkpoint remains accepted; only this policy bridge is rejected.
