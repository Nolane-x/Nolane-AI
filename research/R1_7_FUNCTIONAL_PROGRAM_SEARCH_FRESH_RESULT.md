# R1.7 Functional Program Search — locked FRESH result

Date: 2026-08-13
Pre-fresh lock: `R1_7_PHASE_C_PRE_FRESH_LOCK_V2.json`
Frozen checkpoint SHA-256: `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`
Effective parameters: **75,387,546**
Search trainable parameters: **0**

Evaluation: FIGG-17 v1.1 `composition_holdout/fresh`, indices `0..59`, six unseen length-4 program templates, max horizon 4.

## Locked result

- real task solved: **60/60 = 100%**
- demo-exact: **60/60 = 100%**
- false-exact: **0/60 = 0%**
- mean action efficiency: **1.0**
- each of six unseen fresh templates: **10/10**

Every preregistered fresh acceptance condition passed.

This fresh set is now consumed. No R1.7 Phase C model/source/search tuning is permitted based on these results. Any future progress must use new benchmark worlds/splits.

Claim boundary: this is strong evidence for learned-operator composition within FIGG-17: single-step operators learned on train data were composed by parameter-free search from train length-2 to dev length-3 and fresh length-4 programs. It is not an AGI claim and does not establish unrestricted program synthesis outside this benchmark family.
