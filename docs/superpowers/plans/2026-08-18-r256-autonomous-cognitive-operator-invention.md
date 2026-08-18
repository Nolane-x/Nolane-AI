# R2.56 Autonomous Cognitive Operator Invention — Implementation Plan

## Task 1 — Lock the pure DSL with TDD

Create failing tests for canonical digests, deterministic evaluation, guarded division, runtime type checks, closed opcodes, and bounded deterministic enumeration. Implement `cogcoder/r256_operator_dsl.py` only after RED is observed.

## Task 2 — Lock the invention lifecycle with TDD

Create failing tests for deterministic minimum-cost synthesis, mandatory independent challenges, quarantine, bounded CEGIS refinement, child-registry promotion, content-addressed IDs, collision fail-closed behavior, live rollback, and R2.55 authority non-widening. Implement `cogcoder/r256_operator_invention.py` after RED.

## Task 3 — Build the authored adversarial benchmark

Create a multi-family opaque-field benchmark. Require R2.55 no-invention baseline 0, R2.56 exact success with zero false accepts, at least one CEGIS refinement, verified promotion/live execution, and a post-promotion rollback case.

## Task 4 — Add independently sourced oracle transfer

Pin a public pure function at an immutable external commit. Execute it only to generate I/O examples. Keep synthesis training, promotion challenges, and certification heldouts disjoint. Assert the learner does not parse source structure.

## Task 5 — Protect the lineage

Run R2.56 focused tests and the relevant R2.55→R2.41 test lineage locally. Publish candidate files on an isolated GitHub branch, verify critical blob SHAs, then fast-forward `main` only when the branch corresponds to the verified candidate.

## Task 6 — Run clean hosted verification

GitHub Actions must run focused R2.56 tests, the external oracle transfer, the protected parent lineage, frozen Phase-A recomputation, and Python 3.11/3.13. Publish commit statuses containing the exact run ID and upload the external evidence artifact.

## Task 7 — Run Nolane World adversarial audit

Submit the bounded capability claim, independent hosted evidence, stress worlds, rival hypotheses, and explicit unknowns. Do not credit fake active time. Preserve a failed W5 gate and blockers if convergence is not supported.

## Task 8 — Freeze and release

Freeze delivery, manifest, Phase-A, external transfer, verify result, World result, evolution notes, design, plan, and readiness. A release workflow must verify the frozen boundary, rerun focused tests, create `git archive HEAD`, calculate SHA-256, run `unzip -tq`, and upload the complete artifact. Download and independently verify it, then persist ZIP + checksum + evidence to ChatGPT Library.
