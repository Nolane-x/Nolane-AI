# Neural vNext Native R18 — development-rejected safe first-step dynamics

Status: **DEV REJECTED; confirmation and fresh never opened**.

On locked `dev:992..1023`:

- accepted R11: **118/128**, implicit **28/32**
- `safe90_guarded`: **118/128**, implicit **28/32**, 0 overrides
- `safe90_broad`: **117/128**, implicit **27/32**, 1 override
- `safe85_broad`: **117/128**, implicit **27/32**, 1 override

Train-only exact-transition calibration was **1054/1067 = 98.78%** at threshold 0.80.

The safety boundary prevented compounded rollout harm, but the remaining neural-dynamics override was still harmful and the guarded candidate became behaviorally identical to R11. The strict solved-count gate rejects R18.

- confirmation `1024..1055`: unopened
- fresh `280..319`: unopened and untouched
- no merge / no retune on this dev block
