# RuleProgramPrior second continuation — CLOSED-LOOP REJECTED

Date: 2026-08-12 (Asia/Bangkok)

The train-only internal gate passed, but the preregistered first held-out closed-loop slice failed the non-regression condition. Therefore the second slice was short-circuited and CurrentBest was not changed.

## dev90–95 per family

Accepted CurrentBest control:
- solved **9/18**
- causal **2/6**
- resource **6/6**
- rule **1/6**
- mean steps `7.2778`

Continuation candidate (`69a5a6fe399fb9c63725ae08323bb386b1b204c7e4bd86defe4c8b8bd2d439b7`):
- solved **7/18**
- causal **1/6**
- resource **6/6**
- rule **0/6**
- mean steps `7.1111`

The candidate is worse in total solved, causal solved, and rule solved on slice A. The two-slice acceptance rule is therefore impossible to satisfy; dev96–101 is intentionally not opened.

CurrentBest remains `Nolane-R1.6-NS2-RuleProgramPriorBroad.pt`, SHA-256 `f3108d2e74f955c57578bb42baca5f33890545d07310ef05d239b48333911648`.

Fresh remains unopened.