# Neural vNext Native R4 — Latent Goal Belief successor

Status: **DEVELOPMENT ONLY; `fresh:120..159` UNOPENED**.

R4 starts from the accepted R3 authority and targets the remaining weakness in `implicit_goal_regimes`. R3 learned which public action caused which transition/progress evidence; R4 adds an explicit learned latent belief over the hidden goal while preserving the accepted parent exactly.

## Frozen parent

Accepted R3 is immutable:

- 707,990 physical parameters;
- checkpoint SHA-256 `8c2ba53e81b51d1418cbb7abead6380808dc558cde02af9e63bf8020f92e95da`;
- state SHA-256 `6ecf000191d6212953c8f3a77b5f3de697795f9797c75da70ddd838003531c1e`.

R4 optimizer authority is restricted to R4-owned modules.

## New mechanism

R4 consumes only the same public action-attributed trace already available to R3. A new recurrent belief encoder produces a latent hidden-goal state, a 3 × 5 posterior head predicts goal-coordinate distributions, and a projected posterior conditions a hidden-target-only residual action scorer.

The goal labels used by the auxiliary loss are a **train-only supervision channel**. Private goals are forbidden from inference, rollout, development and fresh evaluation. The final residual layer is zero-initialized, so an untrained R4 is exactly R3-equivalent.

Visible-target safety is structural: the R4 residual is multiplied by `1 - target_visible`. Therefore the candidate must remain exactly equal to frozen R3 on visible-target families.

## Data isolation

- hidden-goal train: `train:1536..2047`;
- selection dev: `dev:160..191`;
- reserved untouched future fresh: `fresh:120..159`;
- consumed fresh blocks `0..39`, `40..79`, `80..119` are forbidden for R4 promotion.

No fresh task is permitted during development.

## Promotion rule

Development eligibility requires strict improvement over frozen R3 in both total solved and `implicit_goal_regimes`, with exact solved counts on all visible-target families. A separately frozen candidate must later pass the preregistered one-shot parent-relative `fresh:120..159` gate before any acceptance claim.
