# R2.51 Interprocedural Call-Flow Query Induction — Design

## Objective

Extend R2.50's self-induced relational query grammar beyond a single function. A patch site may live in a helper while executable evidence is visible only at a caller. The learner must discover a context query through direct static call/argument/return value flow, localize edits across multiple top-level functions, and preserve sparse executable CEGIS.

## Scope

R2.51 supports modules containing at least two synchronous top-level Python functions with one static call-graph root. Calls are direct `Name(...)` calls among functions in the same module. This milestone does not claim methods, imports, recursion, dynamic dispatch, higher-order calls, multiple files, or noisy tests.

## Representation

Build a module-wide identifier-invariant fact graph from the exact parsed AST used for candidate labeling/localization. Facts include syntax ownership, scoped symbols, assignment flow, operand/use facts, compare facts, return value flow, static call targets, argument binding, and generic `FLOW` edges. Materialize `FLOW*` as a bounded-audit transitive closure primitive so a learned query can transfer from demonstration call depths 1–2 to held-out depths 3–5.

R2.51 reuses R2.50's deterministic minimal relational-query induction over changed positive sites and unchanged negative sites. It does not receive helper names, caller names, or target identifiers.

## Search and transaction semantics

All learned macros are localized once on the immutable pre-edit module graph. Candidate patch combinations reuse that localization plan and apply edits transactionally on a fresh AST. This prevents earlier edits from destroying evidence needed by later edits and avoids re-running graph localization for every Cartesian patch candidate.

`FLOW*` is terminal during abstract trace expansion: because it already summarizes arbitrary concrete flow depth, expanding past it duplicates hypotheses and causes path explosion. Trace states are deduplicated by `(node, abstract trace)`.

## Evaluation

Training contains 10 competing edit families with two demonstrations each at call depths 1 and 2. Frozen held-outs use six opaque-renamed modules at unseen call depths 3–5, multiple helpers, a target helper, a decoy helper, bridge functions, and a caller-only observable test surface.

The required patch contains three edits: target helper `Sub→Add`, target operands wrapped in `abs`, and caller guard `Lt→LtE`. The boundary branch has an explicit output offset so the compare edit is causally observable.

Required gates:
- 6/6 exact, zero false accepts.
- Exact three-macro set selected in all held-outs.
- R2.50 single-function baseline rejects all six modules.
- Global syntax-apply baseline fails all six.
- Opaque identifiers and unseen call depths.
- Start from four tests, reveal at most sparse counterexamples, then certify all 2,401 tests.
- R2.50→R2.41 parent compatibility remains green.

## Known boundary

`FLOW*` and the low-level relation vocabulary are still architect-provided. The call model is static, same-module, synchronous, non-recursive, and single-file. These are explicit adversarial targets for the next milestone.
