# R2.64 Learned Contextual Causal Composition — Design

## Status
Approved for inline execution by the user's standing instruction to continue building Nolane-AI autonomously, coordinate through GitHub with the two peer AIs, avoid duplicate work, and prioritize quality/quantity over speed.

## Coordination boundary

Accepted `main` is R2.62. Two peer-AI branches are actively developing R2.63 compositional repository repair, so this milestone deliberately does **not** touch repository multi-edit expansion. R2.64 is orthogonal: it attacks the explicit R2.62 limitation that complementary experiment composition is selected from six host-provided one-step numeric operators and cannot condition on untouched context.

The implementation is additive in a new R2.64 namespace and can be rebased onto accepted R2.63 without modifying R2.63 files.

## Goal

Replace the R2.62 fixed single-operator composition assumption with a bounded learned composition program. The learner must discover a pair of complementary pure-input interventions, synthesize a deterministic expression over the two induced probe outputs plus only the original input positions untouched by **both** interventions, prove that neither probe alone suffices under a matched composition grammar/budget, prove that no R2.62 fixed one-step composition explains the same evidence, synthesize executable probe expressions, and verify the final composed expression on separate contexts.

## Why shared untouched context is allowed

A composition program may use an original field only when neither selected intervention overwrites that positional field. This prevents the composition layer from smuggling the intervened value back in and preserves the causal meaning of the experiment. Field names are canonicalized by position before search, so lexical names do not influence candidate identity or ordering.

## Bounded language

R2.64 does not invent new primitive semantics. It searches a finite expression grammar already trusted by R2.56:

- scalar fields and finite constants
- unary `abs`, `neg`, `not`
- binary numeric/comparison/boolean operators already present in the R2.56 DSL
- conditional `IfElse`

Search is specialized for composition: semantic deduplication, deterministic candidate order, and early conditional generation make useful depth-2 contextual programs reachable without opening the full generic Cartesian depth-2/3 space.

## Core invariants

1. **Positional invariance:** renaming external fields cannot change intervention/program identity.
2. **No intervened-value smuggling:** composition sees only probe outputs and positions free in every selected intervention.
3. **Two-probe necessity:** matched single-probe composition searches must both fail.
4. **R2.62 causal baseline:** every fixed `add/sub/rsub/mul/min/max` composition over the same two probe outputs must fail on the frozen selection evidence.
5. **Probe executability:** each selected intervention output must itself be synthesized from the positions left free by that intervention.
6. **Final exactness:** substituting the learned probe expressions into the learned composition expression must reproduce the oracle on independent validation contexts.
7. **Hard budgets:** composition/probe candidate ledgers fail closed on exhaustion; invalid or non-finite oracle behavior fails closed.
8. **Zero new trainable parameters.**

## Public API

Create `cogcoder/r264_learned_contextual_composition.py` with:

- `ContextualCompositionProgram`
- `ContextualCompositionCandidate`
- `ContextualCompositionStructureReceipt`
- `ContextualCompositionSynthesisReceipt`
- `discover_contextual_composition_structure(...)`
- `synthesize_contextual_composition_program(...)`

The structure receipt records selected intervention IDs/bindings, shared free positions, learned composition expression/digest, fixed-op baseline exact counts, both single-probe ablation outcomes, candidate/oracle accounting, and strict reason strings.

## Authored benchmark

Create a signed-band selector family with six scalar fields:

`band_select(x, lo, hi, left, middle, right)`

- `x < lo` -> `left`
- `lo <= x <= hi` -> `middle`
- `x > hi` -> `right`

Use mixed-sign branch values so `add`, `min`, `max`, subtraction, reverse subtraction and multiplication all fail as universal compositions. The causal pair fixes `right=0` and `left=0`; their union leaves `x, lo, hi, middle` shared. A learned conditional can route between the two probe outputs while both singleton ablations remain insufficient.

Freeze three configurations: canonical names, full rename replay, and argument permutation with role tracking. Include negative cases for insufficient composition budget, missing shared context, non-finite oracle output, and a hidden terminal contradiction.

## External transfer

Use pinned `WarrenWeckesser/ufunclab@f1fbe6769850823a1976ccc28d14cd966130b645`, callable `ufunclab.step`, via callable I/O only in hosted CI.

`step(x, a, flow, fa, fhigh)` provides a clean contextual-composition challenge. With mixed-sign outputs and equality cases, fixing `fhigh=0` and fixing `flow=0` produce two complementary probes. No R2.62 fixed one-step operator is exact over the selection distribution. The shared untouched context contains the positional gate variables; a learned conditional routes the two probe outputs. External challenge and heldout cases are generated separately from composition selection.

The external source is researcher-selected and therefore does not prove blind task discovery.

## Baselines and falsifiers

- R2.62 fixed one-step composition over the selected pair: must fail.
- single-probe learned composition, probe 0 only: must fail under matched grammar/budget.
- single-probe learned composition, probe 1 only: must fail under matched grammar/budget.
- final full learned composition: must pass.
- field rename/permutation: result must remain positionally equivalent.
- invalid/non-finite oracle and budget exhaustion: must abstain, never accept.

## Verification and release boundary

- TDD RED before production module exists.
- focused R2.64 tests locally and hosted on Python 3.11/3.13.
- exact frozen Phase-A recomputation.
- pinned external I/O-only recomputation in hosted CI.
- protected accepted parent lineage.
- source SHA-256 lock before hosted measurement.
- Nolane World 0.8.0 W5 audit; W5 remains false unless all runtime gates genuinely pass.
- complete repository release bundle only after hosted evidence exists.

## Claim boundary

R2.64 may claim only: **bounded learned contextual composition of two complementary pure-input experiments over a finite trusted DSL, with no access to values overwritten by either intervention, matched singleton/fixed-op causal baselines, executable probe synthesis, positional invariance, and one pinned external transfer.**

It must not claim primitive-language invention, 3+ intervention scaling, stateful/effectful experiments, blind external task discovery, broad repository autonomy, unrestricted program synthesis, AGI, or frontier-model equivalence.
