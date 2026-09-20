# Neural vNext Native R38 — dual-evidence decision-set rescue ranker

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R36/R37 established two useful facts: whole-set ranking can avoid selected harm, but relative set-selection confidence alone is not a calibrated rescue probability. R37 could cover all guard blocks at a low set threshold with zero harm, yet only 2/19 selected actions were true rescues.

R38 preserves the complete R37 model and training protocol. The only conceptual change is the **runtime rescue gate**.

An override now requires all of the following:

1. unanimous ensemble preference for the same candidate over the keep-R11 null option;
2. minimum per-head set-selection probability above a preregistered threshold;
3. minimum per-head direct **rescue probability** from the four-way outcome head above a separate preregistered threshold;
4. maximum per-head direct harm probability below the preregistered ceiling;
5. positive mean selection margin over the null option.

This tests whether R37's main failure was selector calibration rather than representation or training capacity.

## Locked architecture

- pair feature width: **774**
- set hidden width: **64**
- pooling: mean + max
- explicit keep-R11 null option: yes
- goal-belief parameters: **107,799**
- set-ranker parameters: **275,730**
- successor parameters: **383,529**
- physical learned parameters: **1,261,071**

## Locked training

Identical to R37:

- 8 contiguous identity strata
- round-robin stratum traversal
- GroupDRO eta: **0.15**
- rescue-present listwise multiplier: **3.0**
- harm-mass weight: **0.75**

## Locked dual-evidence grid

- selection thresholds: **0.20 / 0.30 / 0.40**
- direct rescue thresholds: **0.55 / 0.65 / 0.75 / 0.85**
- harm ceilings: **0.05 / 0.10 / 0.20**
- minimum rescue precision: **75% in every guard block**
- minimum selections: **12 total, 2 per block**
- selected harm: **0**
- maximum runtime override: **1 per episode**

## Locked courts

- goal train: train:21504..22015
- temperature fit: train:22016..22143
- decision-set train: train:22144..22527
- guard: train:22528..22783 in four disjoint 64-identity blocks
- primary dev: dev:2272..2303
- confirmation: dev:2304..2335
- reserved fresh: fresh:280..319 — **UNOPENED**

No same-dev retuning is permitted.


## Locked development result

R38 completed its preregistered primary development court without opening confirmation or fresh.

- accepted R11: **120/128**
- R38: **120/128**
- implicit-goal: **28/32 → 28/32**
- visible-target family solved counts: exact
- overrides: **0**
- guard: **disabled**
- confirmation: **UNOPENED**
- fresh: **UNOPENED**

The direct-rescue gate removed the false-positive behavior seen in R37, but collapsed selective coverage completely. Across the entire locked grid of selection thresholds (0.20/0.30/0.40), direct rescue thresholds (0.55/0.65/0.75/0.85), and harm ceilings (0.05/0.10/0.20), the selector chose **zero actions in every guard block**.

This falsifies the hypothesis that the existing four-way outcome probability can simply be used as a calibrated selective-rescue probability. The next successor should not lower the threshold after observing this court. Instead it should train a dedicated rescue-confidence signal, calibrated on disjoint train-only identities, while retaining the safe set-ranker and harm controls.

Canonical negative evidence: evidence/DEV_REJECTED_001.json.
