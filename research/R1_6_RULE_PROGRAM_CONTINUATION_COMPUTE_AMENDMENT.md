# RuleProgramPrior second continuation — compute amendment before metrics

The preregistered 60-fit-world run exceeded the local execution window during frozen-parent precomputation. It produced a zero-byte log, no metric and no checkpoint. Before observing any model metric, the train-only continuation is reduced to:

Fit:
- rule 148–177 (30 worlds)
- causal 133–142 (10 worlds)
- resource 133–142 (10 worlds)

Internal validation:
- rule 208–215 (8 worlds)
- causal 146–148 (3 worlds)
- resource 146–148 (3 worlds)

Seed 16270, same parent, same 411,650-parameter optimizer scope, same weighted loss, same acceptance conditions, same future closed-loop slices dev90–95 and dev96–101. No dev/fresh data has been opened for this continuation.