# Neural vNext Native R8 — public belief correction

Status: **DEVELOPMENT ONLY; fresh:200..239 UNOPENED**.

R8 starts from accepted R4 after R5 failed fresh and R6/R7 failed locked development gates.

Instead of training another residual, R8 corrects the **goal belief fed into the already accepted frozen R4 neural goal-action scorer** when public evidence has sufficiently narrowed the hidden-goal hypothesis set.

## Key property

R8 adds **zero trainable parameters**.

When evidence is broad or the target is visible, R8 returns exact frozen R4 action logits. When public state/progress constraints narrow support below a preregistered threshold, R8 replaces or blends R4 goal probabilities with the public posterior marginals, then uses the frozen R4 goal projection and action scorer.

No private goal is read.

## Isolation

- selection dev: `dev:352..383`
- reserved fresh: `fresh:200..239`
- consumed fresh: `0..199`
- training: none

Strict solved-count improvement is required. A separate disjoint confirmation block must be preregistered before any fresh opening.
