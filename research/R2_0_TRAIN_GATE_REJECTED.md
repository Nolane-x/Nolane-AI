# R2.0a Recursive Imagination Executive — Train Gate REJECTED

Date: 2026-08-13
Checkpoint: `Nolane-R2.0-RIE-RecursiveExecutive.pt`
SHA-256: `2146eed0d5001f7c365019342ef90a585fd192ee724c01dab33ce21f657bf972`
Effective parameters: **78,762,581**

## Locked gate
- split: FIGG-18 `train`
- indices: `480..499` per family
- families: conditional_regimes, regime_switch, implicit_goal_regimes, causal_prerequisites
- beam width: 1
- 80 tasks per mode
- no tuning after gate open

## Aggregate exact solve rate
- random: 0/80 = **0.00%**
- greedy_parent: 1/80 = **1.25%**
- fixed_depth_1: 2/80 = **2.50%**
- fixed_depth_2: 5/80 = **6.25%**
- fixed_depth_8: 0/80 = **0.00%**
- adaptive: 4/80 = **5.00%**

Primary acceptance comparison: adaptive vs fixed_depth_1 = **+2.50 percentage points**, below the preregistered **+10 percentage-point** requirement.

## Family evidence
- conditional_regimes: depth1 0%, depth2 10%, adaptive 10%
- regime_switch: depth1 10%, depth2 10%, adaptive 5%
- implicit_goal_regimes: depth1 0%, depth2 5%, adaptive 5%
- causal_prerequisites: all tested neural modes 0%

## Decision
**REJECTED.** DEV and FRESH remain unopened. The checkpoint is frozen as a negative research result and must not be tuned further.

## Failure analysis for the next candidate
The first training candidate used at most three supervised public states per world, while many training-world oracle trajectories are materially longer. The gate behavior is consistent with insufficient late-trajectory/submit-state coverage: deeper imagination sometimes helps at depth 2, but depth 8 collapses and causal-prerequisite execution never closes the loop.

This is a diagnosis for a new checkpoint, not authorization to tune R2.0a after seeing its gate. The next candidate must use new, previously unopened train indices and a preregistered full-trajectory curriculum.
