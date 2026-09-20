# Neural vNext Native R11 — certified public causal version space

Status: **DEVELOPMENT ONLY; confirmation and fresh UNOPENED**.

R11 starts from accepted R9 and addresses the negative R10 result: exact full-parity transition keys were too sparse for useful deeper planning.

R11 adds **zero learned parameters**.

For each public regime/action, R11 enumerates every FIGG-18 factorized transition rule still consistent with transitions observed publicly in the current episode. A counterfactual prediction is permitted only when **all** remaining rules agree on exactly the same next state. Otherwise R11 falls back to accepted R9.

## Locked courts

- primary dev: `544..575`
- disjoint confirmation: `576..607`
- reserved fresh: `240..279`
- consumed fresh: `0..239`

## Candidate difference

The three candidates differ only in certified planning horizon: 1, 2, or 3. R9's accepted `max_support=3` remains fixed.

Visible-target episodes are never overridden. No private goal is read. Confirmation/fresh cannot be opened during primary development.
