# R1.6 Next-Latent Transition Diagnostic

Date: 2026-08-12 (Asia/Bangkok)

## Why this was measured

Parameter-free multi-step MPC did not improve dev despite using action-conditioned latent branches. To distinguish planner failure from transition-model failure, `next_latent_head` was evaluated directly on held-out dev **teacher trajectories** using the stable `CounterfactualWorld` parent.

For each teacher-selected action:

- prediction: `out.next_latent[action_label]`
- target: actual Stage-2 latent of the next public observation
- naive baseline: keep the current latent unchanged (persistence)

The recurrent public feedback/action state was teacher-forced. Fresh remained unopened.

## Results

| Family | Transitions | Pred MSE | Persistence MSE | Pred cosine | Persistence cosine | True delta norm | Pred delta norm |
|---|---:|---:|---:|---:|---:|---:|---:|
| causal identification | 54 | **0.20095** | **0.00177** | 0.8809 | **0.9988** | 0.815 | **11.284** |
| delayed resource | 51 | **0.23243** | **0.00516** | 0.8634 | **0.9963** | 1.315 | **12.058** |
| compositional rule | 21 | **0.20036** | **0.00202** | 0.8816 | **0.9986** | 0.942 | **11.263** |

## Interpretation

This is a major transition-model failure. The real Stage-2 observation latent changes only slightly between adjacent public states, while the learned transition head predicts a delta roughly an order of magnitude too large in norm. A persistence baseline is dramatically better.

This directly explains why multi-step latent imagination compounds error: the imagined state leaves the local latent manifold after the first predicted transition.

## Next action

Do **not** spend more capacity on planning yet. Replace the unconstrained additive next-latent head with a bounded residual-delta transition:

- zero/near-zero initial residual so persistence is the safe prior;
- explicitly bounded delta magnitude;
- direct supervision on `(next_latent - current_latent)`;
- compare against persistence MSE as a mandatory gate;
- only retry MPC if transition beats persistence on held-out dev.

No fresh tasks were opened.
