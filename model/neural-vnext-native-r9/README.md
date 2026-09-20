# Neural vNext Native R9 — accepted public counterfactual planner

Status: **ACCEPTED**.

R9 keeps the accepted R4 latent-goal neural policy frozen and adds a deterministic, public-only counterfactual decision layer for hidden-goal episodes.

## What R9 changes

R9 does **not** add a new trained neural checkpoint.

- accepted learned substrate: R4
- physical learned parameters: **877,542**
- R9 learned successor parameters: **0**
- selected deterministic config: `planner_narrow`, `max_support=3`

The planner uses only public state, public progress, public regime/state parity, and transition effects already observed in episode-local public memory. It never reads the private goal.

Visible-target episodes are never overridden.

## Evidence before fresh

Primary `dev:416..447`:

- R4: **115/128**
- R9: **120/128**
- implicit-goal: **23/32 → 28/32 (+5)**
- visible-target families: exact solved counts

Disjoint confirmation `dev:448..479`:

- R4: **114/128**
- R9: **116/128**
- implicit-goal: **21/32 → 23/32 (+2)**
- visible-target families: exact solved counts

## Single-use fresh court

`fresh:200..239` was opened once by workflow `35485340986`.

- R4: **140/160**
- R9: **142/160**
- implicit-goal: **25/40 → 27/40 (+2)**
- conditional: **39 → 39**
- regime-switch: **37 → 37**
- causal-prerequisites: **39 → 39**

The preregistered promotion gate passed.

Fresh artifact: `10596294292`.
Digest: `sha256:bdf8fde882f477ba3bcdef1eef5d06ae0fb6c6842b0c0a93f156db6230fd71c9`.

## Governance

`fresh:200..239` is permanently consumed.

No post-fresh tuning or rerun is permitted. Accepted authority is the exact deterministic R9 source/config plus the accepted R4 checkpoint; there is intentionally no separate R9 tensor checkpoint.

Canonical authority: `ACCEPTED_AUTHORITY.json`.
