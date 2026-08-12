# RuleProgramPrior breadth test — internal gate PASSED

Date: 2026-08-12 (Asia/Bangkok)

This is the compute-amended breadth test preregistered before metrics. Parent is accepted EffectProgress CurrentBest; only 411,650 `rule_program_*` parameters were trainable. No dev/fresh task was used in optimization/model selection.

## Breadth

Fit: 30 compositional-rule + 10 causal + 10 resource worlds (50 total). Internal validation: 10 rule + 3 causal + 3 resource worlds. This is 3× the rule breadth of the narrow rejected run. Seed 16220; 30-epoch compute budget.

## Parent validation
- weighted CE: `1.9896488`
- overall accuracy: `61.798%`
- compositional rule: `22.857%`
- causal identification: `73.077%`
- delayed resource: `100.000%`

## Best candidate (epoch 25)
- weighted CE: `1.8774166`
- overall accuracy: `64.045%`
- compositional rule: `28.571%`
- causal identification: `73.077%`
- delayed resource: `100.000%`
- rule-program scale (`tanh(raw)`): `-0.1654192`

All preregistered internal conditions pass: lower loss, higher rule accuracy, non-lower causal/resource, and non-lower overall accuracy.

## Candidate
- checkpoint: `Nolane-R1.6-NS2-RuleProgramPriorBroad.pt`
- SHA-256: `f3108d2e74f955c57578bb42baca5f33890545d07310ef05d239b48333911648`
- effective parameters: `72,260,609`
- fresh opened: false

Teacher-forced improvement is not a capability claim. The next step is the previously preregistered closed-loop gate on dev78–83 and dev84–89 with the accepted EffectProgress CurrentBest as control.