# Neural vNext Native R40 — rescue-aligned proposal

Status: **PREDEVELOPMENT LOCKED; PRIMARY DEV PENDING**.

R39 restored a small safe rescue signal, but candidate identity was still chosen by the set-selection head before binary rescue confidence was consulted. The best locked non-harm setting selected only two guard actions, one true rescue, concentrated in two blocks.

R40 changes **candidate proposal only**. Training, architecture, parameter count, thresholds, harm controls and promotion gates are unchanged from R39.

For every candidate and ensemble head:

`joint proposal = selection probability × binary rescue probability`

The candidate with the highest mean joint proposal is considered only when all three heads independently rank that same candidate first by joint proposal. It must still pass the locked selection threshold, binary rescue threshold, four-way harm ceiling, and positive selection margin over the keep-R11 null option.

## Locked architecture

- pair width: **774**
- set hidden width: **64**
- ensemble heads: **3**
- keep-R11 null option: yes
- binary rescue head: yes
- successor parameters: **421,164**
- physical learned parameters: **1,298,706**

## Locked selector grid

Unchanged from R39:

- selection: **0.20 / 0.30 / 0.40**
- binary rescue: **0.50 / 0.60 / 0.70 / 0.80**
- four-way harm ceiling: **0.05 / 0.10 / 0.20**
- precision: **>=75% in every guard block**
- coverage: **>=12 total and >=2 per block**
- selected harm: **0**
- max override: **1 per episode**

## Locked courts

- goal train: train:24064..24575
- temperature fit: train:24576..24703
- set train: train:24704..25087
- guard: train:25088..25343
- primary dev: dev:2400..2431
- confirmation: dev:2432..2463
- fresh: fresh:280..319 — **UNOPENED**

No same-dev retuning is permitted.
