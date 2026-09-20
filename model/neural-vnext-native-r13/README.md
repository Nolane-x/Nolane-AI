# Neural vNext Native R13 — development-rejected selective neural causal residual

Status: **DEV REJECTED; confirmation and fresh never opened**.

R13 started from accepted R11 and attempted to make the learned causal residual from R12 safer. Override thresholds were calibrated only on a disjoint train-only calibration range before development; the calibration rule had to fail closed if it could not establish the preregistered precision requirement.

## Locked development result

On `dev:672..703`:

- accepted R11: **118/128**
- `selective_guarded`: **118/128**
- `selective_broad`: **118/128**
- accepted R11 implicit-goal: **27/32**
- both R13 candidates implicit-goal: **27/32**
- both candidates made **0 overrides vs R11**
- visible-target family solved counts stayed exact.

The same promotion-relevant metrics appeared in both exact-head workflow runs `35489561157` and `35489562880`.

The strict solved-count gate was not relaxed after observing this result.

## Closure

- confirmation `dev:704..735` was never opened;
- `fresh:280..319` was never instantiated and remains untouched;
- no repeated tuning against `dev:672..703`;
- R13 closes without merge.

This negative result is preserved because it distinguishes a safe fail-closed calibration from a successful successor: safety alone was not enough to improve solved count.
