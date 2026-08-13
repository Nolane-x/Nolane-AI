# Nolane R1.7 Phase C Complete Delivery

This delivery closes the R1.7 Neural Causal Program Machine Phase C milestone.

Current best system:
- neural checkpoint: `checkpoints/Nolane-R1.7-NCPM-OperatorExecutor.pt`
- checkpoint SHA-256: `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`
- effective parameters: `75,387,546`
- inference mode: `functional_program_search`
- search-added trainable parameters: `0`

Key evidence:
- Neural Operator Executor held-out transitions: 99.5% exact vector / 99.5% element.
- held-out TRAIN length-2 Functional Search: 64/64 solved.
- DEV unseen length-3 Functional Search: 60/60 solved; frozen parent policy 5/60.
- locked FRESH unseen length-4 Functional Search: 60/60 solved; frozen parent policy 0/60.
- post-fresh R1.7 tests: 81/81 pass.
- lineage/protocol regressions: 28/28 pass.

Fresh Phase-C composition set is consumed and must not be reused as an untouched benchmark after future tuning.

See `R1_7_PHASE_C_REALITY_REPORT.md`, `R1_7_PHASE_C_FINAL_MANIFEST.json`, and `R1_7_CURRENT_BEST.json`.
