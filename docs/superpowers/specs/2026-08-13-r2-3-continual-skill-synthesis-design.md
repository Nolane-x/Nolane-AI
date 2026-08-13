# R2.3 Continual Skill Synthesis — Design

## Objective
Extend accepted R2.2 without changing the 78,779,253-parameter neural deployment weight. R2.3 must acquire reusable bounded skills from public demonstrations during runtime, persist them outside neural weights, transfer them to unseen inputs and later episodes, revise them when a newer version is demonstrated, and retain unrelated previously learned skills.

R2.3 is accepted only on locked TRAIN -> DEV -> FRESH evaluation. Synthetic success may increase only the continual-learning/adaptation evidence in the AGI-readiness rubric; it must not be described as AGI or broad frontier-model superiority.

## Architecture
R2.3 adds three zero-trainable-parameter components around R2.2:

1. A deterministic bounded skill synthesizer over the existing restricted arithmetic instruction set.
2. A persistent versioned skill registry with provenance, demonstrations, validation status, competence counters and rollback.
3. A continual runtime that learns, revises, composes and reuses skills across episodes while preserving the accepted R2.2 behavior when the subsystem is disabled.

All artifacts are deterministic, bounded and serializable. Hidden benchmark answers or hidden generator descriptions never enter public runtime state.

## KFIGG-23 Continual Transfer Benchmark
Each case is a curriculum containing multiple opaque skills. Public data includes skill identifiers, version identifiers and demonstration input/output pairs. Hidden evaluator metadata contains expected answers only.

The curriculum tests few-shot induction, retention after intervening learning, version revision, and ordered composition of already learned skills. The baseline receives identical demonstrations and persistent storage permission but performs replay only rather than synthesizing a reusable transformation.

## Locked Admission Protocol
- Neural parameters added: exactly 0.
- TRAIN-only protocol selection.
- DEV opens only after source hashes and protocol are committed.
- No source or protocol tuning after DEV.
- FRESH opens once after a pre-FRESH lock.
- Acceptance: candidate >= baseline +20 percentage points, candidate >=85%, retention >=90%, revision >=90%, composition >=80%, integrity failures =0.
- With continual skills disabled, normal environment behavior remains identical to R2.2/R2.0i.

## Failure Handling
Ambiguous or budget-exhausted synthesis returns unresolved. A version collision with inconsistent provenance is rejected. A failed revision preserves the previous validated current version. Failures in one skill cannot mutate unrelated skills.

## Claim Boundary
R2.3 can establish bounded continual skill acquisition and transfer in a synthetic restricted domain. It does not establish unrestricted lifelong learning, autonomous self-improvement, broad coding or mathematics competence, AGI, or superiority over large language models.
