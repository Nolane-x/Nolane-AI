# Neural vNext Native R21 — supervised public hidden-goal belief

Status: **PRIMARY DEV LOCKED; FRESH UNOPENED**.

R21 tests a dedicated neural hidden-goal belief model over accepted R11.

R19 showed that simply reusing R4's latent goal probabilities did not improve solved count. R21 changes the learning target: three neural heads are explicitly supervised to identify the private hidden goal, but **only on train identities**. Inference never reads the private goal.

The input at inference is entirely public:

- exact public consistency support mask over 125 possible goals;
- current public state;
- public progress signal;
- public budget/step;
- previous public feedback.

The exact public consistency mask remains a hard support boundary. The network may only reweight goals already consistent with public evidence; it cannot introduce a ruled-out goal.

## Locked identities

- train: `5632..5887`
- train-only temperature calibration: `5888..6015`
- primary dev: `1184..1215`
- confirmation: `1216..1247`
- reserved fresh: `280..319` — **UNOPENED**

Preregistered posterior blends:

- `goalblend25`: beta 0.25
- `goalblend50`: beta 0.50
- `goalblend100`: beta 1.00

All are restricted to public support <=3; outside that region accepted R11 remains exact.

Strict promotion requires total solved gain, implicit-goal solved gain, and exact visible-target family solved counts.
