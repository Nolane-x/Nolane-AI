# R2.4 Long-Horizon Execution — Design

## Objective

Extend accepted R2.3 without changing the 78,779,253-parameter neural deployment weight. R2.4 must preserve a multi-stage objective over many environment steps, satisfy dependencies, respond to transient action failure, incorporate public mid-episode requirement changes, and rebuild its remaining plan from current public state.

## Architecture

R2.4 adds zero neural parameters:

1. A public goal graph with dependencies and completion conditions.
2. An execution ledger recording attempted actions and public transition feedback.
3. A replanning loop that recomputes reachable unfinished subgoals after every observation.
4. Bounded retry handling for transient failures and reopening of goals invalidated by public state changes.

The controller may use only public observations, public goal definitions, public action descriptions and observed feedback.

## KFIGG-24

Each synthetic case contains 5–8 goal nodes, dependency depth 3–6, resource constraints and a fixed step budget. Public mid-run events may add a prerequisite, invalidate a support state, or make one action attempt fail transiently.

The comparison baseline receives identical public information but computes one initial plan and keeps following that plan suffix. R2.4 rebuilds the remaining plan after each step.

Metrics: overall solve rate, steps on solved episodes, recovery after public requirement changes, recovery after transient failures, dependency integrity and public-only access violations.

## Admission

- New neural parameters: exactly 0.
- Protocol selection on TRAIN only.
- DEV opens only after source/protocol lock is committed.
- No candidate changes after DEV.
- Final held-out opens after a freeze marker.
- Candidate solve rate >=85%.
- Gain over static-plan baseline >=25 percentage points.
- Requirement-change recovery >=80%.
- Transient-failure recovery >=80%.
- Dependency/public-access integrity failures =0.

## Claim boundary

R2.4 can establish bounded long-horizon goal maintenance and replanning in a synthetic structured environment. It does not establish general real-world task competence, AGI or frontier-model superiority.
