# R1.7 Functional Program Search — DEV gate protocol

Date: 2026-08-13
Benchmark: FIGG-17 v1.1

Frozen parent checkpoint: `Nolane-R1.7-NCPM-OperatorExecutor.pt`
SHA-256: `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`
Effective parameters: `75,387,546`
Functional-search trainable parameters: `0`

## Isolation

- split: `dev`
- family: `composition_holdout`
- indices: `0..59` inclusive (60 worlds)
- six DEV program templates, all length 3 and not present in TRAIN program-template set
- maximum search horizon: 4
- no parameter updates, calibration, threshold fitting, or source edits are permitted after this lock and before the result is recorded
- FIGG-17 `fresh` remains unopened

## Inputs

Search may use only public demonstrations, public dynamic action descriptions, and the frozen Neural Operator Executor. Hidden program/template labels are forbidden as inference or ranking inputs. Hidden template identity may be used only after evaluation to aggregate diagnostic per-template scores.

## Metrics

- demo exact rate
- real task solve rate after inferred sequence + public submit
- false-exact rate
- mean action efficiency on solved tasks
- per-template solve rate (six dev templates)

## Acceptance

Proceed beyond the dev composition gate only if all are true:
1. demo-exact rate >= 0.90
2. real task solve rate >= 0.80
3. false-exact rate <= 0.05
4. every one of the six dev templates has solve rate >= 0.70
5. checkpoint SHA and effective parameter count remain unchanged

A pass establishes held-out length-3 compositional generalization for this benchmark family. It does not authorize a fresh claim; FIGG-17 fresh length-4 remains sealed until a separate pre-fresh lock.
