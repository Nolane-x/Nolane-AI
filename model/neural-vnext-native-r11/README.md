# Neural vNext Native R11 — accepted certified public causal version space

Status: **ACCEPTED**.

R11 keeps accepted R9 as the fallback authority and adds a deterministic public causal version-space planner for hidden-goal episodes.

## Mechanism

For each public regime/action, R11 enumerates the FIGG-18 factorized transition rules still consistent with public transitions observed in the current episode. A counterfactual prediction is usable only when **all surviving rules agree on the same next state**. Otherwise it falls back to accepted R9.

- selected config: `causal_horizon1`
- horizon: **1**
- R9 goal-support threshold: **3**
- learned successor parameters: **0**
- physical learned parameters remain **877,542** from accepted R4.

No private goal is read. Visible-target episodes are never overridden.

## Promotion evidence

Primary `dev:544..575`:

- accepted R9: **119/128**
- R11: **120/128**
- implicit-goal gain: **+1**
- visible-target families exact

Disjoint confirmation `dev:576..607`:

- accepted R9: **120/128**
- R11: **121/128**
- implicit-goal gain: **+1**
- visible-target families exact

Promotion-relevant solved counts reproduced across exact-source executions. Primary and confirmation trajectory step counts were **not bitwise reproducible**; those step counts were not used for promotion.

## Single-use fresh court

`fresh:240..279` was opened once.

- accepted R9: **146/160**
- R11: **149/160**
- implicit-goal: **29/40 → 32/40 (+3)**
- conditional-regimes: **39 → 39**
- regime-switch: **38 → 38**
- causal-prerequisites: **40 → 40**

Fresh workflow: `35487147712`.

Fresh artifact: `10598086827`.
Digest: `sha256:06597a315dd7ef23024d47d48cc68905087c079dfc802b7546d41535e0de809c`.
`r11.fresh.json` SHA-256: `017df285c026ad9bd71bee1586172e5db93ff8f7020b0674325303cd880f4112`.

## Governance

`fresh:240..279` is permanently consumed. No post-fresh tuning, replay, or same-block reuse is allowed.

R11 intentionally has no separate tensor checkpoint. Accepted authority is exact R11 deterministic source/config layered on accepted R9 and the accepted R4 learned checkpoint.
