# Neural vNext Native R20 — development-rejected active identification

Status: **DEV REJECTED; confirmation and fresh never opened**.

On locked `dev:1120..1151`:

- accepted R11: **122/128**, implicit **29/32**
- probe once (early ≤4): **120/128**, implicit **27/32**
- probe twice (early ≤6): **122/128**, implicit **29/32**
- probe once (early ≤8): **120/128**, implicit **27/32**

Visible-target family solved counts remained exact.

R20 proves that acquiring real transition evidence is not automatically beneficial: blind probes can break solved episodes, while two-probe exploration was only net-neutral.

The strict gate rejects R20.

- confirmation `1152..1183`: unopened
- fresh `280..319`: unopened and untouched
- no retuning on this dev block

The next mechanism must learn **which** public probe is worth taking from train-only paired outcomes rather than probing unconditionally.
