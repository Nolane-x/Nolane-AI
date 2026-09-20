# Neural vNext Native R36 — decision-set rescue ranker

Status: **PREDEVELOPMENT LOCKED; PRIMARY DEV PENDING**.

R36 changes the training unit from an independent candidate row to the **whole decision set**.

Every hidden-goal decision now presents the neural policy with all valid alternatives simultaneously. A permutation-equivariant candidate encoder pools mean/max set context and scores:

- every candidate alternative;
- one explicit learned **keep R11** null option.

Training is listwise:

- if one or more alternatives truly rescue an R11 failure, probability mass is trained toward the rescue set;
- if no rescue exists, the correct selection is keep R11;
- probability mass assigned to true harm actions is explicitly penalized;
- four-way outcome classification is retained as calibration supervision.

This directly matches runtime, where only one action can be chosen from the alternative set.

## Locked architecture

- candidate pair feature width: **774**
- set hidden width: **64**
- pooling: mean + max
- ensemble heads: **3**
- explicit keep-R11 null option: yes
- goal-belief parameters: **107,799**
- set-ranker parameters: **275,730**
- successor parameters: **383,529**
- physical learned parameters: **1,261,071**

## Locked courts

- goal train: train:18944..19455
- temperature fit: train:19456..19583
- decision-set train: train:19584..19967
- guard: train:19968..20223 in four disjoint 64-identity blocks
- primary dev: dev:2144..2175
- confirmation: dev:2176..2207
- reserved fresh: fresh:280..319 — **UNOPENED**

No same-dev retuning is permitted.
