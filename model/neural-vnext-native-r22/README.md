# Neural vNext Native R22 — conformal singleton goal belief

Status: **PRE-DEVELOPMENT LOCKED; FRESH UNOPENED**.

R22 is a learned Neural Core successor over accepted R11. It addresses the R21 confirmation failure by replacing continuous neural posterior fusion with a fail-closed singleton gate.

The neural ensemble is supervised on hidden-goal labels only on train identities. A disjoint train-only calibration split fits temperature and conformal-style nonconformity thresholds. A second train-only validation split chooses among preregistered alpha values only when empirical singleton precision is at least 90%.

At inference, private goal labels are unavailable. R22 may replace the public posterior only when:

- public support contains 2–3 goals;
- the conformal prediction set is a singleton;
- all three neural heads agree on that singleton;
- accepted R11 has not already reached public progress-complete.

Otherwise behavior is exactly accepted R11.

Locked identities:

- train: `6016..6271`
- conformal fit: `6272..6335`
- train-only guard validation: `6336..6399`
- primary dev: `1248..1279`
- confirmation: `1280..1311`
- fresh: `280..319` — **UNOPENED**

Strict promotion still requires total solved gain, implicit-goal solved gain, and exact visible-target family solved counts.

Claim boundary: the threshold is conformal-style; no IID coverage guarantee is claimed for dependent trajectory rows.
