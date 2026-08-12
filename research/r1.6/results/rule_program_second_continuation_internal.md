# RuleProgramPrior second continuation — internal gate PASSED

Date: 2026-08-12 (Asia/Bangkok)

Compute-amended train-only protocol; no dev/fresh data was used in optimization/model selection. Parent is accepted CurrentBest `f3108d2e...`; no new parameters were added and only existing 411,650 `rule_program_*` parameters were trainable.

## Parent internal validation
- weighted CE: `1.7430320`
- overall: `50.649%`
- rule: `14.286%`
- causal: `33.333%`
- resource: `100.000%`

## Best continuation (epoch 30)
- weighted CE: `1.4119395`
- overall: `58.442%`
- rule: `25.000%`
- causal: `47.619%`
- resource: `100.000%`
- rule-program scale (`tanh(raw)`): `-0.1897625`

All internal conditions pass.

Candidate:
- `checkpoints/Nolane-R1.6-NS2-RuleProgramContinuation.pt`
- SHA-256 `69a5a6fe399fb9c63725ae08323bb386b1b204c7e4bd86defe4c8b8bd2d439b7`
- effective parameters `72,260,609`
- fresh opened: false

Next: frozen closed-loop gate on preregistered dev90–95 and dev96–101.