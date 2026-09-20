# Neural vNext Native R29 — certified counterfactual rescue geometry

Status: **PREDEVELOPMENT LOCKED; FRESH UNOPENED**.

R29 follows the strongest evidence from R28: single-action interventions can genuinely rescue or harm terminal episodes, but pre-action state/action features did not distinguish those outcomes.

## Learned mechanism

R29 has two learned subsystems.

1. A three-head public hidden-goal/action-mass ensemble proposes an alternative action.
2. A three-head rescue-geometry classifier predicts **neutral / rescue / harm**.

Unlike R28, the rescue classifier additionally sees public consequence geometry that is available before intervention and certified by R11's causal version space:

- certified next state under R11;
- certified next state under the candidate;
- causal-rule counts for both;
- expected distance from current, R11-next and candidate-next states under the public neural posterior;
- candidate-vs-R11 distance advantage;
- candidate-vs-R11 action-mass margin;
- rule-count advantage.

If either next state is not certified, the neural path falls back to accepted R11.

## Parameter authority

- goal-belief successor: **107,799**
- certified rescue-geometry successor: **59,721**
- total successor parameters: **167,520**
- physical learned parameters including accepted R4: **1,045,062**
- rescue feature dimension: **238**

## Counterfactual labels

Only train identities are branched.

- **neutral**: no terminal fail/solve flip;
- **rescue**: candidate branch solves while R11 branch fails;
- **harm**: R11 branch solves while candidate branch fails.

After the single differing first action, both branches use accepted R11. The rescue/harm labels require no private goal.

## Locked identities

- goal training: `train:9984..10495`
- temperature fit: `train:10496..10623`
- rescue-geometry training: `train:10624..11007`
- guard blocks: `11008..11071`, `11072..11135`, `11136..11199`, `11200..11263`
- primary dev: `dev:1696..1727`
- confirmation: `dev:1728..1759`
- reserved fresh: `fresh:280..319`

## Locked intervention gate

Candidate generation requires all three goal heads to agree on an alternative causal action with minimum action mass >= **0.55**, support size 2..8, and both R11/candidate next states certified.

Guard selection searches only the preregistered train-only grid:

- rescue threshold: 0.4 / 0.5 / 0.6 / 0.7 / 0.8 / 0.9
- harm ceiling: 0.05 / 0.10 / 0.20

A pair is eligible only if:

- rescue precision >= **75% in every guard block**;
- at least 2 predicted interventions per block;
- at least 12 predicted interventions overall;
- **zero true harm rows** among predicted interventions.

At inference all rescue heads must exceed the selected rescue threshold and every harm probability must remain below the selected harm ceiling. At most one neural override is allowed per episode. Visible-target families never enter this path.

## Promotion

Primary promotion requires a strict total solved gain and a strict `implicit_goal_regimes` solved gain with exact visible-target family solved counts. A primary winner must pass disjoint confirmation with the exact frozen checkpoint/config before fresh may be opened.
