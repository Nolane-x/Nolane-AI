# Neural vNext Native R18 — safe first-step learned dynamics

Status: **DEVELOPMENT LOCKED; fresh unopened**.

R18 is a new successor after R17's mixed result. R17 proved learned dynamics can rescue an R11 failure, but decisions that relied on imagined depth-2 trajectories broke several parent-solved episodes.

R18 therefore imposes a hard boundary:

- an alternative action is scored only by its **one-step** high-confidence neural transition;
- R11's reference is allowed one extra imagined continuation, which makes R11 harder to replace;
- no alternative is ever selected because of an imagined second step;
- visible-target episodes return accepted R11 exactly.

New identities:

- train `4864..5119`
- train-only calibration `5120..5247`
- primary dev `992..1023`
- confirmation `1024..1055`
- fresh `280..319` — **UNOPENED**
