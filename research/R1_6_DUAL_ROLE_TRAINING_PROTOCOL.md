# R1.6 Dual-Role Causal Binder training protocol

Date: 2026-08-12

## Parent

`Nolane-R1.6-NS2-PSRPlanner.pt`

All parent parameters are frozen. The tested optimizer-scope helper selects only parameters whose names begin with `dual_role_`.

## Data isolation

Procedural `train` split only:

- families: `causal_identification`, `compositional_rule`, `delayed_resource`
- fit indices: 69–78 per family (10 each)
- internal-validation indices: 79–81 per family (3 each)
- seed: 16082

No dev or R1.6 fresh task is used during optimization or hyperparameter selection.

## Objective

The new Dual-Role Causal Binder is trained as a residual on top of frozen PSRPlanner logits. It receives only public structured observation atoms plus action-effect evidence already observed by the recurrent agent. Two learned attention roles are intended to preserve distinct relational evidence (e.g. current-like versus target-like information) without hard-coding field names such as `state` or `goal`.

The candidate is allowed to proceed to closed-loop evaluation only if internal-validation cross-entropy improves without reducing overall teacher-forced action accuracy. Teacher-forced improvement alone is explicitly not considered a capability win.

Output checkpoint: `Nolane-R1.6-NS2-DualRoleCausalBinder.pt`.
