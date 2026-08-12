# Nolane R1.6 Live Research Ledger

Updated: 2026-08-12 (Asia/Bangkok)

This file is the crash-resistant research ledger for the R1.6 Neural System-2 line. It records negative results as well as positive ones. Binary checkpoints are not uploaded through the current GitHub text connector; their byte sizes and SHA-256 hashes are recorded in `R1_6_LIVE_MANIFEST.json`, while full binary weights remain in milestone ZIP/Library backups.

## Current research objective

Move capabilities that R1.5 delegated to an external symbolic System-2 workspace into the neural model itself: dynamic semantic action scoring, world-model prediction, causal evidence binding, recurrent planning, rule induction, system identification and termination/horizon control. Parameter count is allowed to grow modestly rather than being artificially frozen at 50M.

## Current best verified parent

`Nolane-R1.6-NS2-CounterfactualWorld.pt` is the strongest stable parent in the current dev protocol: 4/18 closed-loop dev tasks (1/6 causal identification, 1/6 compositional rule, 2/6 delayed resource) on the recorded evaluation. This is weak in absolute terms and is not described as AGI-level performance. Fresh remains unopened for R1.6.

## Architecture evolution retained

- Stage-2 recurrent ~50M trunk remains the neural representation core.
- Dynamic semantic action scoring replaces fixed action slots.
- Neural micro world-model predicts action-conditioned consequences.
- Raw public-observation channel preserves details the code-trained trunk can discard.
- Structured observation encoder represents typed JSON/public-state atoms.
- Dynamic causal action memory stores action-effect evidence without binding to slot IDs.
- Structured numeric-delta sketch adds generic causal credit assignment from public state transitions.
- Counterfactual world-model curriculum supervises all legal actions at each train state, not only the teacher-selected action.
- Relational context/action scoring is retained because it improved dev behavior over the earlier bilinear-only policy.

## Important retained evidence

- `StructuredStage`: first observed recurrent causal gain over its no-recursion ablation, but only 1/9 dev.
- `CounterfactualWorld`: best stable dev parent at 4/18. Counterfactual failure calibration reached about 89.7% train accuracy with progress MAE about 0.181 in the recorded run.
- `StructuredDelta`: 32,768-parameter causal delta encoder improved trajectory imitation signal to about 56.7%, but did not beat 4/18 dev by itself.
- `CausalMemoryPath`: training action accuracy reached about 66.7% after opening the memory-to-consequence pathway, but dev remained 4/18; treated as overfit rather than a capability win.
- Dev diagnostic found that many causal failures probe opaque actuators correctly but then fail to plan corrections; many rule failures perform one correct operation and terminate too early; resource failures violate prerequisites.
- Failure-head diagnostic showed high failure probability even for some correct terminal actions, so it currently behaves partly like an action-type prior and must not be used as a hard safety shield.

## Rejected / negative branches

The following were tested and rejected because they did not exceed the verified parent on closed-loop dev: recurrent adapter expansion, residual cognitive highway, strategy-MoE, AtomCross, Action-Conditioned Atom Policy, raw-byte cross policy, metadata-invariant perception retrain, hierarchy-only perception retrain, epistemic exploration weighting, risk-barrier policy reweighting, and several broader causal BPTT runs that either timed out before producing an artifact or failed to transfer.

Negative branches are intentionally retained in local milestone artifacts/results so future work does not repeat them.

## Current experiment: factorized termination readiness

A new termination model separates two concepts that the old failure head conflated:

1. `P(action is terminal | action)`
2. `P(state/history is not ready to terminate | cognitive state)`

The curriculum provides terminal-action targets from counterfactual `done` outcomes and readiness targets from teacher trajectories. The new tests pass and the checkpoint `Nolane-R1.6-NS2-TerminationGuard.pt` has been written locally. The next required step is to train/evaluate the termination heads from cached thought/action representations and compare closed-loop dev against the 4/18 parent before calling it an improvement.

## Research protocol

- Train and dev are procedural and disjoint.
- R1.6 fresh remains unopened until a candidate is preregistered/locked.
- A module is retained only when ablation or closed-loop evaluation shows causal gain.
- Timeouts before checkpoint creation are recorded as incomplete, not successes.
- Parameter growth is allowed, but capacity is spent only when a measured bottleneck justifies it.
- Every completed research step must be pushed to `Nolane-x/Nolane-AI` immediately; milestone completion additionally requires a complete ZIP and a Library copy.
