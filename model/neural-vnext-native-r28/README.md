# Neural vNext Native R28 — development-rejected counterfactual rescue value

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R28 was the first Native successor in this line to supervise intervention using paired terminal counterfactual outcomes rather than teacher-action agreement.

## Learned authority

- goal successor parameters: **107,799**
- rescue successor parameters: **52,035**
- total successor parameters: **159,834**
- total physical learned parameters: **1,037,376**
- checkpoint SHA-256: `0f584de4de765bfc1d78b464ed03802c48cc192d4693cb684b4cdd1caf3841da`
- state SHA-256: `813d14dff51475c7b11ad27c23c86ae65d737f3637b77ed3c31435f5b42842e9`

## Counterfactual evidence

The train-only paired branch collector produced **209** intervention rows:

- **19 true rescue rows**: candidate branch solves while R11 branch fails;
- **19 true harm rows**: R11 branch solves while candidate branch fails;
- remaining rows are terminally neutral.

This is an important positive scientific result despite candidate rejection: there are real single-action interventions capable of changing terminal success in both directions.

## Rescue guard — failed closed

The pre-action rescue representation could not identify those rows robustly.

At threshold 0.5 the four-block guard predicted 13 interventions but only:

- **1 true rescue**
- **2 harms**
- rescue precision **7.69%**

Higher thresholds collapsed coverage without producing a valid rescue gate. The guard therefore disabled all neural overrides before primary dev.

## Primary development

On `dev:1632..1663`:

- accepted R11: **116/128**
- R28: **116/128**
- implicit-goal: **24/32 → 24/32**
- neural overrides: **0**
- visible-target family solved counts: exact

R28 is rejected at development.

## Interpretation

The failed variable is now more specific: terminal rescue exists, but **state/action/action-mass features before intervention are insufficient to distinguish rescue from harm**.

The next successor should encode certified public counterfactual consequence geometry — predicted R11 next state versus predicted candidate next state, public expected-distance changes, causal rule certainty, and neural posterior geometry — before estimating terminal rescue value.

## Governance

- confirmation `1664..1695`: **UNOPENED**
- fresh `280..319`: **UNOPENED**
- no post-dev threshold retuning
- closes without merge

Workflow: `35499509678`.

Artifact: `10600639805`.

Artifact digest: `sha256:7402c2dddde1e03ed1584e4ea025e2f34f18f91962c24ada2c3e43f4687fb52b`.

Canonical negative evidence: `evidence/DEV_REJECTED_001.json`.
