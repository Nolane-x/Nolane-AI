# R2.0c Public-Memory Executive — Train Gate REJECTED

Date: 2026-08-13
Checkpoint SHA-256: `31d98d6b170366ebf58c9ba7dc0b337a7768bc2ea8036af598df4968b802816a`
Effective parameters: **78,768,917**

## Gate result (800..819 per family)
- adaptive: **15/80 = 18.75%**
- fixed_depth_1: **14/80 = 17.50%**
- fixed_depth_2: **15/80 = 18.75%**
- fixed_depth_8: **1/80 = 1.25%**
- greedy_parent: **1/80 = 1.25%**
- random: **1/80 = 1.25%**

Adaptive improvement over the locked shallow baseline was only **+1.25 percentage points**, below the required +10 points. Causal-prerequisites remained 0/20 for every neural mode.

## Important positive result
Although rejected for the R2.0 acceptance gate, public per-action memory raised adaptive exact solve rate from 5% (R2.0a/b) to 18.75% with only 6,336 additional executive parameters. Conditional/regime/implicit families reached 15–30% solve rates depending on depth.

## Root-cause evidence for the next candidate
1. In causal-prerequisite public observations, prerequisite state is carried by numeric resources such as charge/gate values.
2. `public_context_fingerprint` hashes short categorical strings only; measured causal-prerequisite context fingerprints were exactly zero through prerequisite transitions.
3. R2.0c maintained a real `ConditionalEvidenceMemory`, but its recursive planner still invoked the frozen conditional-law parent with zero evidence/evidence-metadata tensors. Therefore observed action effects did not feed back into the world-model used for imagination.

## Decision
**REJECTED.** DEV/FRESH remain unopened. The next checkpoint must use new indices and condition imagination on public evidence effects instead of merely exposing memory metadata to the action scorer.
