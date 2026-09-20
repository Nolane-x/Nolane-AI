# Neural vNext Native R36 — decision-set rescue ranker

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

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


## Locked development result

R36 trained on **5,148** candidate rows grouped into **1,716 complete decision sets**. Unlike R30-R35, the set-level objective learned a strong safe default: final no-rescue null accuracy was roughly **99.1–99.6%**, while each head selected **79–81 rescue groups** on train.

The guard showed the first major safety improvement in this lineage: the preregistered threshold grid produced **zero selected harm**. However, rescue generalization was highly uneven across identity blocks. The strongest zero-harm setting selected only four actions in total, two true rescues, both concentrated in one guard block; another guard block selected none.

On dev:2144..2175:
- accepted R11: **118/128**, implicit-goal **25/32**
- R36: **118/128**, implicit-goal **25/32**
- visible-target family solved counts: exact
- overrides: **0**
- confirmation: **UNOPENED**
- fresh: **UNOPENED**

Interpretation: the set-valued objective fixed much of the unsafe-action problem, but ordinary ERM still concentrates rescue coverage in a narrow slice of the identity distribution. The next controlled successor should preserve the architecture and selector while making listwise training **distributionally robust across train strata and rescue-present groups**.

Canonical negative evidence: evidence/DEV_REJECTED_001.json.
