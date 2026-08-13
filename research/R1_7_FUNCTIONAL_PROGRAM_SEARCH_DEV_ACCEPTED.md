# R1.7 Functional Program Search — DEV gate ACCEPTED

Date: 2026-08-13

Frozen parent checkpoint: `Nolane-R1.7-NCPM-OperatorExecutor.pt`
SHA-256: `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`
Effective parameters: **75,387,546**
Search trainable parameters: **0**

Protocol: FIGG-17 v1.1 `composition_holdout/dev`, indices `0..59`, six held-out length-3 program templates, max search horizon 4. Search used only public demonstrations, public action descriptions, and the frozen Neural Operator Executor.

## Result

- real task solved: **60/60 = 100%**
- demo-exact program found: **59/60 = 98.33%**
- false-exact: **0/60 = 0%**
- mean action efficiency on solved tasks: **1.0**
- per-template solve rate: **10/10 for all six unseen DEV templates**
- new trainable parameters: **0**

All preregistered dev acceptance conditions passed.

The one world without an exact demonstration fit still solved the real task, showing that exact hidden-template reconstruction is not required; a functionally useful inferred program was sufficient.

Claim boundary: this establishes strong held-out length-3 compositional generalization for FIGG-17 composition tasks. FIGG-17 fresh length-4 remains sealed and has not been used for tuning or selection.
