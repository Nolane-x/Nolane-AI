# Neural vNext Native R39 — binary rescue confidence

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R37 showed that set-selection confidence can produce coverage but poor rescue precision. R38 added the four-way outcome head's direct rescue probability to the gate and collapsed coverage to zero across the entire locked grid.

R39 tests one narrow hypothesis: **rescue confidence needs its own supervised objective**.

The R38 architecture and training protocol are preserved except for one small per-candidate binary rescue head. Each ensemble member predicts whether a candidate solves an episode that the accepted R11 branch would fail. The binary loss uses inverse-frequency positive weighting and is optimized inside the same eight-stratum GroupDRO objective.

At runtime, the selector still requires unanimous candidate preference, selection confidence, a harm ceiling from the four-way outcome head, and a positive margin over keep-R11. The rescue threshold now gates the dedicated binary rescue probability rather than the four-way rescue class probability.

## Locked architecture

- pair width: **774**
- set hidden width: **64**
- ensemble heads: **3**
- explicit keep-R11 null option: yes
- dedicated binary rescue head: yes
- goal-belief parameters: **107,799**
- set-ranker parameters: **313,365**
- successor parameters: **421,164**
- physical learned parameters: **1,298,706**

## Locked training

- listwise loss weight: **1.0**
- harm-mass weight: **0.75**
- binary rescue loss weight: **1.0**
- binary positive weight: inverse frequency from the locked set-training rows
- identity strata: **8**
- GroupDRO eta: **0.15**
- rescue-present listwise multiplier: **3.0**

## Locked selector grid

- selection thresholds: **0.20 / 0.30 / 0.40**
- binary rescue thresholds: **0.50 / 0.60 / 0.70 / 0.80**
- four-way harm ceilings: **0.05 / 0.10 / 0.20**
- precision: **>=75% in every guard block**
- coverage: **>=12 total and >=2 per block**
- selected harm: **0**
- max runtime override: **1 per episode**

## Locked courts

- goal train: train:22784..23295
- temperature fit: train:23296..23423
- set train: train:23424..23807
- guard: train:23808..24063 in four disjoint 64-identity blocks
- primary dev: dev:2336..2367
- confirmation: dev:2368..2399
- reserved fresh: fresh:280..319 — **UNOPENED**

No same-dev retuning is permitted.


## Locked development result

R39 completed its preregistered primary development court without opening confirmation or fresh.

- accepted R11: **118/128**
- R39: **118/128**
- implicit-goal: **25/32 → 25/32**
- visible-target family solved counts: exact
- overrides: **0**
- guard: **disabled**
- confirmation: **UNOPENED**
- fresh: **UNOPENED**

The dedicated binary rescue head restored a small amount of selective signal compared with R38. Under the locked guard grid, the best non-harm settings selected two candidate actions total, including one true rescue and zero harm. However, selection remained concentrated in only two guard blocks and never met the preregistered coverage requirement.

This rejects the hypothesis that adding binary rescue confidence alone is sufficient. The remaining mismatch is now between **candidate proposal** and **rescue confidence**: the set-selection head chooses the proposal first, and the binary head only vetoes that proposal afterward. A successor should change proposal selection itself so that rescue-confidence participates in which candidate is proposed, while preserving the same zero-harm and cross-block promotion gates.

Canonical negative evidence: evidence/DEV_REJECTED_001.json.
