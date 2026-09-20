# Neural vNext Native R8 — development-rejected public belief correction

Status: **DEV REJECTED; fresh never opened**.

R8 added zero trainable parameters and corrected frozen R4 goal probabilities from public state/progress constraints when hidden-goal support became narrow.

On locked `dev:352..383` frozen R4 solved **119/128** with implicit-goal **24/32**. Every R8 configuration also solved **119/128** with implicit-goal **24/32** and the same total 1,620 steps.

Correction did activate on hidden-goal steps (189–365 steps depending on configuration), but did not change aggregate action behavior enough to improve solved count.

The strict promotion gate was not relaxed.

- confirmation `dev:384..415` was never opened;
- `fresh:200..239` remains untouched;
- R8 closes without merge;
- no repeated selection against `dev:352..383`.

Canonical evidence: `evidence/DEV_REJECTED_001.json`.
