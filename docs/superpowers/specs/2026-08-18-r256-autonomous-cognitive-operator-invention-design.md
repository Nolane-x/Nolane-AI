# R2.56 Autonomous Cognitive Operator Invention — Design

## Goal

R2.55 can acquire and distill procedures, but those procedures remain bounded by host-registered primitive operators. R2.56 adds bounded invention of a **new pure cognitive primitive** when a verified state transformation is missing.

## Selected architecture

R2.56 uses a deterministic typed expression DSL rather than unrestricted executable-code generation. This creates behavior that did not exist as an operator ID while preserving a static safety boundary.

The DSL supports field reads, scalar constants, selected numeric/string/boolean transforms, guarded arithmetic, comparisons, min/max, and conditionals. It exposes no filesystem, network, process, reflection, dynamic import, random, or clock operation.

## Invention lifecycle

1. A host declares an `OperatorInventionNeed` with input fields, one output field, search depth, constants, and candidate budget.
2. The synthesizer enumerates expressions deterministically by structural cost and deduplicates observed semantic vectors.
3. A training fit creates only a candidate.
4. A non-empty independent challenge suite is mandatory.
5. Failed challenges quarantine the candidate; bounded CEGIS may add the first counterexample and search again.
6. A passing candidate is compiled into content-addressed `invented.<digest>` behavior and promoted only into a child registry.
7. Live execution is transactional over `ExternalWorkingState`; supported evaluation failures restore the pre-execution state and roll the invention back.
8. Invented operators are always `side_effect_class='pure'` and cannot widen the R2.55 host-issued authority envelope.

## Verification strategy

The authored benchmark contains opaque-field transformation families where the R2.55 no-invention registry cannot provide the required output. It must prove exact synthesis, challenge gating, CEGIS refinement, promotion, live execution, and rollback.

The independent transfer uses pinned `mahmoud/boltons` `clamp` only as an input/output oracle. The learner receives sampled I/O, not parsed implementation structure. Training, challenge, and post-promotion heldout inputs are disjoint.

## Acceptance boundary

Acceptance requires focused tests, protected R2.55→R2.41 lineage, Python 3.11/3.13, external heldout transfer, valid Nolane World audit, and a GitHub-generated full repository release bundle.

R2.56 does **not** claim arbitrary program synthesis, effectful operator invention, universal/open-ended representation invention, broad autonomous repository repair, or AGI. Nolane World non-convergence must be preserved if its W5 gate remains false.
