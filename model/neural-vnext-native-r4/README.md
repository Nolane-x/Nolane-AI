# Neural vNext Native R4 — Public Goal-Consistency Belief

Status: **development successor; fresh:120..159 unopened**.

R4 tests a narrower hypothesis than simply scaling R3: the remaining hidden-goal failures may require an explicit belief over latent goals, not a longer generic recurrent trace.

## Frozen parent

R4 starts from the exact accepted R3 authority:

- checkpoint SHA-256: `8c2ba53e81b51d1418cbb7abead6380808dc558cde02af9e63bf8020f92e95da`
- state-dict SHA-256: `6ecf000191d6212953c8f3a77b5f3de697795f9797c75da70ddd838003531c1e`
- 707,990 physical parameters
- all parent parameters frozen

## Public goal-consistency belief

For hidden-goal FIGG-18 episodes, the public observation exposes:

- current three-coordinate state;
- scalar `progress_signal`;
- public transition feedback.

The benchmark progress signal is the normalized sum of forward distances from the current public state to the hidden goal. R4 therefore maintains all 125 possible 5×5×5 goals and removes candidates inconsistent with each public `state + progress_signal` observation.

No private goal/rule field is read. The belief representation contains:

- exact 125-way consistency posterior;
- 15 coordinate marginals;
- normalized candidate count;
- posterior confidence.

A small neural encoder converts this public belief into a residual action signal on top of frozen R3. The residual is multiplied by `1-target_visible`, so visible-target behavior is structurally exact to R3.

## Development contract

- train: `train:2048..2559`, `implicit_goal_regimes` only
- select: `dev:160..191`
- reserved untouched fresh: `fresh:120..159`
- previously consumed fresh blocks `0..119` are forbidden for R4 promotion

Eligibility requires strict total and implicit-goal gains over frozen R3 and exact solved counts in all visible-target families.

No fresh task may be instantiated before a separately frozen candidate receives PRE_FRESH_LOCK authority.
