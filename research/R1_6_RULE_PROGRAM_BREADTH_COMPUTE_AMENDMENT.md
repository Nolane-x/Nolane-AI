# RuleProgramPrior breadth protocol — compute amendment before metrics

Date: 2026-08-12 (Asia/Bangkok)

The originally preregistered 120-fit-world breadth run exceeded the local execution window during parent-state precomputation. The run produced a zero-byte log, no metric line, no optimizer step evidence, and no checkpoint. Therefore it provides no model result and did not expose dev/fresh data.

Before any breadth metric was observed, the train-only breadth test is reduced to a compute-feasible but still substantially wider curriculum than the rejected 10-world rule run:

## Revised fit
- compositional-rule indices **108–137**: 30 worlds
- causal-identification indices **108–117**: 10 worlds
- delayed-resource indices **108–117**: 10 worlds

## Revised internal validation
- compositional-rule indices **138–147**: 10 worlds
- causal-identification indices **118–120**: 3 worlds
- delayed-resource indices **118–120**: 3 worlds

Seed remains `16220`. Same RuleProgramPrior, same 411,650-parameter optimizer scope, same weighted loss (rule 2.0; non-rule 0.5), same parent CurrentBest, same internal acceptance conditions. Compute budget is 30 epochs.

No dev/fresh task has been opened for this breadth test.