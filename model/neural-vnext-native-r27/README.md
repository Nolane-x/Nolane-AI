# Neural vNext Native R27 — distributionally robust action-mass consensus

Status: **PREDEVELOPMENT LOCKED; FRESH UNOPENED**.

R27 keeps the learned action-equivalence representation introduced by R26, but changes the training/calibration procedure to directly address R26's calibration-transfer failure.

## Motivation

R26 achieved **92.59–100%** train-only action precision at several thresholds, yet reduced primary implicit-goal solves by three on new identities. A single calibration block was therefore not a reliable generalization authority.

R27 does not tune against the failed R26 development block. It uses entirely new train/calibration/development identities.

## Learned architecture

The neural architecture remains:

- 3 public hidden-goal heads
- hidden dimension 96
- **107,799 successor parameters**
- **985,341 physical learned parameters** including the frozen accepted R4 substrate
- exact public support hard mask
- per-head goal probability aggregated into causal action mass

## Robust calibration

R27 expands training and uses **four disjoint train-only guard blocks**:

- 8512..8575
- 8576..8639
- 8640..8703
- 8704..8767

A threshold is eligible only if:

- point precision is at least 90% **inside every block**;
- each block contains at least 5 actual R11-changing overrides;
- aggregate coverage is at least 24 overrides;
- all other inference invariants remain satisfied.

Candidate thresholds are fixed before execution: 0.65, 0.75, 0.85, 0.90, 0.95, 0.975.

No development score participates in threshold selection.

## Locked identities

- training: `train:7872..8383`
- temperature fit: `train:8384..8511`
- robust guard blocks: `train:8512..8767`
- primary dev: `dev:1568..1599`
- confirmation: `dev:1600..1631`
- reserved fresh: `fresh:280..319`

Fresh remains **UNOPENED**.

## Promotion

Primary requires a strict total solved gain and a strict `implicit_goal_regimes` gain with exact visible-target family solved counts. Even a primary winner must pass disjoint confirmation unchanged before fresh is opened.
