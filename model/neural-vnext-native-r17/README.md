# Neural vNext Native R17 — development-rejected model-based neural planning

Status: **DEV REJECTED; confirmation and fresh never opened**.

R17 combined R10's multi-step objective with R16's learned public dynamics model.

## Locked dev result

On `dev:928..959`:

- accepted R11: **123/128**, implicit-goal **27/32**
- `mbp_h2_guarded`: **120/128**, implicit **24/32**
- `mbp_h2_broad`: **121/128**, implicit **25/32**
- `mbp_h3_broad`: **121/128**, implicit **25/32**
- visible-target families stayed exact.

Train-only transition calibration: **1097/1116 = 98.30%** at threshold 0.70.

The negative aggregate hides one important positive counterexample: implicit episode **947** changed from accepted-R11 **fail (13 steps)** to R17 **solve (9 steps)**. That successful decision used a one-step selected action. Most harmful changes depended on imagined depth-2 continuations.

## Closure

The strict solved-count gate rejects R17. No threshold or horizon is retuned on this dev block.

- confirmation `960..991`: unopened
- fresh `280..319`: unopened and untouched
- no merge

The next successor must use new identities and may test a safer boundary: use lookahead to evaluate the parent reference, but only execute an alternative whose own selected plan is already a one-step high-confidence improvement.
