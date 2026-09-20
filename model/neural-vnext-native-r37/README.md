# Neural vNext Native R37 — distributionally robust decision-set ranker

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R36 produced the strongest safety signal yet in the rescue lineage: across the preregistered guard threshold grid it selected **zero harm**, but rescue coverage concentrated in only one identity block.

R37 preserves the complete R36 inference architecture and selector. It changes **training distribution handling only**.

## R37 training change

Complete decision groups are partitioned into **8 contiguous identity strata** over the locked set-training range.

Each epoch:

- traverses the eight strata round-robin;
- computes the same R36 outcome/listwise/harm losses;
- multiplies listwise loss by **3.0** on rescue-present decision groups;
- computes mean loss per represented stratum;
- updates non-parametric GroupDRO weights with **eta = 0.15**;
- optimizes the DRO-weighted stratum loss.

The inference model receives no stratum ID and no new feature. Parameter count and runtime behavior remain identical to R36.

## Locked architecture

- pair feature width: **774**
- set hidden width: **64**
- pooling: mean + max
- explicit keep-R11 null option: yes
- goal-belief parameters: **107,799**
- set-ranker parameters: **275,730**
- successor parameters: **383,529**
- physical learned parameters: **1,261,071**

## Locked courts

- goal train: train:20224..20735
- temperature fit: train:20736..20863
- set train: train:20864..21247
- guard: train:21248..21503 in four disjoint 64-identity blocks
- primary dev: dev:2208..2239
- confirmation: dev:2240..2271
- reserved fresh: fresh:280..319 — **UNOPENED**

The R36 selector and guard remain unchanged: unanimous ensemble preference over null, direct harm ceiling, at least 75% rescue precision in every guard block, minimum coverage, zero selected harm, and at most one override per episode.


## Locked development result

R37 completed its preregistered primary development court without opening confirmation or fresh.

- accepted R11: **120/128**
- R37: **120/128**
- implicit-goal: **28/32 → 28/32**
- visible-target family solved counts: exact
- overrides: **0**
- guard: **disabled**
- confirmation: **UNOPENED**
- fresh: **UNOPENED**

The distributionally robust training change did not solve calibration. At selection threshold 0.35 the guard could obtain broad coverage with zero selected harm, but only **2/19** selected actions were true rescues; two guard blocks had zero rescue precision. Higher thresholds sharply collapsed coverage.

The critical follow-up is therefore not another loss-weight increase. R36/R37 expose a selector mismatch: the gate thresholds set-selection confidence but does not require the already-trained four-way outcome head to assign high direct rescue probability. The next controlled successor should preserve R37 training and architecture and add a preregistered **dual-evidence gate** requiring both set preference and direct rescue probability, while retaining the harm ceiling and unanimous ensemble preference.

Canonical negative evidence: evidence/DEV_REJECTED_001.json.
