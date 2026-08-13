# R1.7 phase-only Latent Program Ranker — REJECTED

Date: 2026-08-13
Benchmark: FIGG-17 v1.1 train-only composition_holdout
Parent: accepted Goal-Difference world representation

Before training, the composition teacher collector was corrected to replay the initial exact oracle plan once in order. The invalid pre-fix cache was deleted. Correct cache integrity was:
- 64 worlds
- 192 decision rows = exactly 3/world
- 64 submit rows
- 24 rows/template for all 8 train templates
- fit templates 0..5; held-out validation templates 6,7

## Held-out-template baseline

Frozen full parent logits on templates 6/7:
- operation accuracy: **0.50** (32 operation rows)
- submit accuracy: **1.00** (16 submit rows)
- template 6 operation: **0.50**
- template 7 operation: **0.50**

## Candidate

Shared phase-conditioned ranker (53,761 params), trained only on templates 0..5 for 60 epochs.

No epoch satisfied the preregistered gate. Late training behavior:
- candidate operation accuracy: **0.00**
- candidate submit accuracy: **1.00**
- template 6 operation: **0.00**
- template 7 operation: **0.00**

The zero-initialized candidate before training had operation 0.15625 / submit 0.1875 on this slice. No candidate checkpoint was created. FIGG dev/fresh remained unopened.

## Interpretation

A program-step sinusoid plus frozen Goal-Difference relational features is not sufficient to compose unseen two-operation templates. The ranker learns training-template sequence priors rather than the functional transformation implied by demonstrations. Phase C must re-evaluate representation quality under the corrected teacher before adding recurrence or more capacity.
