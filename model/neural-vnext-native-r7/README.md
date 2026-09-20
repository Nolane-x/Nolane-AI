# Neural vNext Native R7 — development-rejected threshold consistency successor

Status: **DEV REJECTED; fresh never opened**.

R7 tested whether a public-consistency residual should act only after the hidden-goal hypothesis support becomes sufficiently narrow.

## Frozen parent

Accepted R4 remained immutable.

## Locked primary development court

On `dev:288..319`:

- frozen R4: **119/128**, implicit-goal **26/32**, 1,629 steps
- `threshold_exact`: **119/128**, implicit **26/32**, 1,597 steps
- `threshold_narrow`: **119/128**, implicit **26/32**, 1,644 steps
- `threshold_moderate`: **119/128**, implicit **26/32**, 1,633 steps

All visible-target family solved counts remained exact.

`threshold_exact` was more efficient, but the preregistered promotion rule required a **strict solved-count gain** in both total and implicit-goal episodes. The gate was not relaxed after seeing the result.

## Closure

No R7 candidate was eligible.

- confirmation `dev:320..351` was never opened;
- `fresh:200..239` was never instantiated and remains untouched;
- R7 closes without merge;
- no repeated tuning against `dev:288..319`.

Canonical result: `evidence/DEV_REJECTED_001.json`.
