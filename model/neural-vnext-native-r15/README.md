# Neural vNext Native R15 — development-rejected broad-support diagnostic successor

Status: **DEV REJECTED; confirmation and fresh never opened**.

R15 preserved accepted R11 exactly whenever hidden-goal support was ≤3 and attempted to add certified information-gathering actions only while support was broader.

On locked `dev:800..831`:

- accepted R11: **122/128**, implicit-goal **28/32**
- all three R15 candidates: **122/128**, implicit **28/32**
- R15 diagnostic decisions: **0**
- overrides vs R11: **0**
- visible-target families remained exact.

The result reproduced in runs `35490271364` and `35490281532`.

The negative result identifies a timing bottleneck: broad posterior support and certified causal knowledge rarely overlap. R15 waited for a certificate; by the time a certificate existed, accepted R11 was already active.

- confirmation `dev:832..863` was never opened;
- `fresh:280..319` remains untouched;
- R15 closes without merge.
