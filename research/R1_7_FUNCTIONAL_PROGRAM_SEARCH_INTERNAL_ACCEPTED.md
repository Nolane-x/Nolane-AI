# R1.7 Functional Program Search — internal gate ACCEPTED

Date: 2026-08-13

Frozen parent checkpoint: `Nolane-R1.7-NCPM-OperatorExecutor.pt`

SHA-256: `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`

Effective candidate parameters: **75,387,546**

Program-search trainable parameters: **0**

Protocol: FIGG-17 v1.1, `composition_holdout/train`, indices `522..585`, 64 worlds, maximum search horizon 4. Search inputs were limited to public demonstration vector pairs, public dynamic action descriptions, and the frozen accepted Neural Operator Executor. Hidden program/template labels were not search inputs or ranking signals.

## Result

- worlds: **64**
- demo-exact: **64/64 = 100%**
- real task solved after inferred sequence + submit: **64/64 = 100%**
- false-exact: **0/64 = 0%**
- mean action efficiency on solved worlds: **1.0**
- new trainable parameters: **0**

All preregistered acceptance conditions passed. This authorizes a separately preregistered FIGG-17 dev composition gate. FIGG-17 fresh remains unopened.

Important claim boundary: this is evidence that a learned single-step operator model can be composed by parameter-free functional search on held-out TRAIN worlds. It is not yet evidence for unseen length-3 dev programs or length-4 fresh programs.
