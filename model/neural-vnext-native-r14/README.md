# Neural vNext Native R14 — belief-tree certified causal successor

Status: **DEVELOPMENT ONLY; confirmation and fresh UNOPENED**.

R14 starts from accepted R11 and adds no learned parameters.

R11 already learns nothing new at inference: it builds a public causal version space and uses a counterfactual only when all surviving rules agree. Its accepted configuration plans one step ahead. R14 keeps that exact fallback but changes the planning state.

## New mechanism

R14 models **future public feedback** inside the planner.

After a hypothetical certified action, the next public `progress_signal` reveals a distance shell. R14 partitions the current hidden-goal posterior into the goal hypotheses that would produce each possible shell, then plans separately inside each observation branch.

This is a small exact belief-state tree over at most three surviving public goal hypotheses.

Candidates:

- `belief_tree_h2_guarded`
- `belief_tree_h3_guarded`
- `belief_tree_h2_pareto`

No private goal is read. Visible-target episodes are exact accepted R11/R9/R4 behavior.

## Locked identities

- primary dev: `dev:736..767`
- confirmation: `dev:768..799`
- reserved fresh: `fresh:280..319`
- consumed fresh: `0..279`

R12 and R13 reserved `fresh:280..319` but never opened it; it remains untouched.

Promotion requires strict total and implicit-goal solved-count gain with exact visible-target family solved counts. Primary success alone cannot authorize fresh.
