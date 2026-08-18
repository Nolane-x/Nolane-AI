# R2.64.1 Frontier Fairness Hotfix

R2.64.1 is a correctness hardening release for accepted R2.64. It does not introduce a new intelligence primitive and therefore receives **+0.0** readiness movement; the internal engineering heuristic remains **49.4/100**, not an AGI probability.

## Defect

Independent hosted falsification showed that R2.64 can retain a broader authorized expansion frontier after diagnostic evidence has narrowed the live version space. Because trusted-macro generation is globally capped and content ordered, a previously contradicted parent can consume the sole generation slot before a currently live parent is expanded. In the reproduced case the target is expressible: the accepted R2.64 solver succeeds when the generation cap is raised, but abstains at cap 1.

## Fix

The accepted R2.64 solver is preserved byte-for-byte in `cogcoder/r264_unified_adaptive_repository_search_base.py`. The public API routes through an isolated fairness scheduler that uses two deterministic tiers: currently live evidence-consistent authorized parents first, then the remaining authorized frontier only with unused budget. Every generated child is still filtered against the complete public evidence ledger. Candidate generation still receives neither the oracle nor target outputs.

The fallback tier is intentional. A parent contradicted by current evidence can still mutate into a child that repairs all evidence, so deleting contradicted ancestors would trade one false-abstention bug for another completeness bug.

## Hosted evidence

TDD RED was reproduced post-merge on workflow `32132315543`: two controls passed and the tight-budget fairness invariant failed. A separate pre-merge validation run `32131666124` independently reproduced the same defect.

The frozen six-episode causal benchmark then establishes the before/after boundary: accepted R2.64 abstains 6/6 at generation budget 1; R2.64.1 repairs 6/6 exactly at the same budget; the roomy-budget control remains exact 6/6; and the repairable-contradicted-ancestor fallback remains exact 6/6. Generated/admitted counts remain one per tight/fallback episode, target-output leakage is false, false terminal accepts are zero, verification failures are zero, and added trainable parameters are zero.

Canonical hosted run `32133355598` verifies the frozen source lock, recomputes R2.64.1 Phase-A byte-exact, recomputes accepted R2.64 authored evidence and pinned NumPy 2.4.6 `numpy.square` transfer exactly, passes **13/13** R2.64/R2.64.1 tests plus **234/234** protected R2.63→R2.41 parent tests (**247/247 relevant tests total**), and passes the hotfix contract on Python 3.11 and 3.13.

## Nolane World audit

Nolane World 0.8.0 audit `world_3180299bb313` remains deliberately non-converged at W5. The audit records six adversarial families, five evidence receipts, three experiments, four verification rounds, and two fresh-context verifications. It also keeps material unknowns explicit, including the requirement that R2.65 rebase onto the post-hotfix parent before its own source lock/promotion. No W5 pass is claimed or forced.

## Claim boundary

R2.64.1 proves a bounded scheduling correctness repair inside the existing trusted `PatchMacro` repository-repair system. It does **not** prove new patch-language invention, arbitrary code generation, stateful/effectful experimentation, broad real-repository autonomy, unrestricted program synthesis, or AGI.
