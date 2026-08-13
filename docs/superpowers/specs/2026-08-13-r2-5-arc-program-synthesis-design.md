# R2.5 ARC Program Synthesis — Design

## Objective

Measure and improve Nolane's transferable abstract reasoning with the official ARC-AGI-2 corpus while keeping the accepted 78,779,253-parameter neural weight unchanged. R2.5 adds a bounded generic grid program-synthesis layer with zero neural parameters.

## Dataset provenance

Pin `arcprize/ARC-AGI-2` at commit `f3283f727488ad98fe575ea6a5ac981e4a188e49`.

Development uses only `data/training`. The official public scoring set is used only after source, operator vocabulary, search budgets, ranking and the two-output policy are frozen on GitHub.

## Architecture

1. Analyze grid dimensions, color frequencies, background candidates, connected components, bounding boxes, symmetries and repeated structure.
2. Use generic typed transformations: identity, color replacement, rotations, flips, transpose, crop, object selection, component-wise transforms, repeat/scale, overlay and concatenation.
3. Search hierarchically from low-complexity transforms to bounded compositions.
4. Keep only programs that reproduce every demonstration output exactly.
5. Rank by description length, operator count, literal count and structural invariants.
6. Return at most two unique grids for each test input.

No task identifier is used as a solver feature. Operators must be generic and reusable across tasks.

## Protocol

- TDD for operators, parser, synthesis and scoring.
- Training-only GitHub Actions runs all 1,000 official training tasks.
- All development feedback stays inside `data/training`.
- Before official public scoring, commit the pinned ARC revision, source Git blob identities, operator vocabulary, max program depth, candidate budget, per-task compute budget and two-output policy.
- Run the official public set only after that freeze and preserve the resulting score without changing the frozen R2.5 candidate.

## Claims

No minimum public score is preregistered. The external result is evidence even if low. Broad-reasoning readiness changes only from the external result, not from training performance. ARC-AGI-2 performance alone does not establish AGI or frontier-model superiority.
