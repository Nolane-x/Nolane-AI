# R1.6 Dual-Role Binder — frozen-parent training scope

Date: 2026-08-12

This step makes Dual-Role Causal Binder training conservative by construction.

## Invariant

The accepted `PSRPlanner` parent must remain frozen during the binder experiment. The optimizer scope is selected by the explicit `dual_role_` parameter prefix only. Parameters belonging to the rejected single-role `causal_evidence_*` binder, policy, world model, trunk, structured encoder, recurrent state, and PSR planner are excluded.

A dedicated regression test was added that fails before the helper exists and passes after implementation. The targeted scope test plus the existing neural-System-2 training/model tests completed successfully before this record was pushed.

The next experiment will use a new train/internal-validation slice and will train only the Dual-Role Binder parameters. Closed-loop capability will be judged on a new held-out dev slice; teacher-forced accuracy alone is not accepted as evidence of interactive intelligence.
