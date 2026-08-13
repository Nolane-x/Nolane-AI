# R2.4 Long-Horizon Execution Implementation Plan

> **For agentic workers:** use a task-by-task TDD workflow.

**Goal:** Add a zero-neural-parameter public-state goal graph and replanning controller that maintains long tasks under dependency changes and transient failures.

**Architecture:** Build a deterministic synthetic project environment, a goal graph/replanning controller, a matched static-plan baseline, then lock TRAIN/DEV/final held-out admission. Existing R2.3 behavior and the single 78,779,253-parameter deployment weight remain unchanged.

## Global constraints
- New neural parameters: 0.
- Public observation/goal/action data only.
- Fixed step/retry budgets.
- TRAIN-only protocol selection; no candidate changes after DEV.
- Current one-weight remains unchanged.

### Task 1 — Public project environment
Create `cogcoder/longhorizon_world.py` and `tests/test_r24_world.py`. Test deterministic generation, dependency enforcement, public incident visibility, transient-failure semantics and absence of private fields from the controller interface before implementation.

### Task 2 — Goal graph and replanning controller
Create `cogcoder/goal_stack.py` and `tests/test_r24_goal_stack.py`. Test dependency ordering, replanning after public requirement change, bounded retry behavior, reopening invalidated support goals and deterministic action choice before implementation.

### Task 3 — Baseline and KFIGG-24 evaluator
Create `cogcoder/kfigg24.py`, `scripts/evaluate_r24_longhorizon.py` and `tests/test_r24_kfigg24.py`. Give static-plan baseline and replanning candidate identical initial information and action budgets. Measure solve, interruption recovery, transient-failure recovery, dependency integrity and steps.

### Task 4 — Locked admission/release
Select protocol on TRAIN only. Commit source/protocol lock, run DEV from GitHub source, freeze unchanged candidate, run final held-out once, and accept only if candidate >=85%, gain >=25 pp, requirement-change recovery >=80%, transient-failure recovery >=80%, integrity violations 0. Publish verifier/CI/current-best/reality report, build a COMPLETE ZIP with exactly one weight, verify archive/SHA and persist to Library.
