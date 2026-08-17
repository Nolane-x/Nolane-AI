# R2.50 Self-Induced Relational Query Grammar — Design

## Status

Approved for implementation by the user on 2026-08-17. The user explicitly asked the agent to continue upgrading autonomously without stopping for intermediate design approval.

## Problem

R2.49 can learn a minimal conjunction of relational context features, but the feature vocabulary itself is still hand-authored in `relational_features_for_site()`. High-level features such as `lineage:reaches_guard`, `guard_body:returns_lineage`, and `lineage:multi_hop` are supplied by the architecture. This means R2.49 learns a rule *inside* a human-designed representation rather than inventing the representation needed to separate a changed site from unchanged decoys.

## Goal

Build a bounded but genuine representation-induction layer that derives discriminative relational queries from low-level program facts. R2.50 must solve held-out executable patch-localization tasks where target and decoy sites are deliberately indistinguishable to the complete R2.49 feature vocabulary.

## Non-goals

R2.50 does not claim general repository repair, interprocedural reasoning, multi-file transactionality, arbitrary edit-language invention, or AGI. It remains a bounded intraprocedural milestone and must preserve Nolane World non-convergence if those frontiers remain unresolved.

## Architecture

### 1. Low-level program fact graph

Create `ProgramFactGraph` from a single Python function AST. The graph exposes only low-level typed structure and binding relations, never task-specific semantic labels. Node kinds include:

- candidate edit site
- expression
- symbol
- function parameter
- assignment
- compare
- branch
- return
- call
- constant

Relations include:

- `AST_PARENT`, `AST_CHILD`
- `LEFT_OPERAND`, `RIGHT_OPERAND`
- `ASSIGNS`, `DEFINED_BY`, `USES`
- `ALIAS_OF`
- `COMPARE_LEFT`, `COMPARE_RIGHT`
- `IF_TEST`, `IF_TRUE_CHILD`, `IF_FALSE_CHILD`
- `RETURN_VALUE`

Raw identifier strings may be used internally to resolve bindings but must never appear in learned query signatures or benchmark evidence.

### 2. Query-trace generator

For each candidate site, enumerate bounded typed paths from the site anchor through the fact graph. A trace is a sequence of `(relation, destination_node_kind)` steps. Paths are bounded by maximum depth and may not revisit the same graph node in one trace.

Alias-chain variation is generalized by a generic trace normalizer: consecutive repeated `ALIAS_OF -> symbol` steps are compressed to an automatically induced repetition token `ALIAS_OF+ -> symbol`. This is not a predeclared semantic feature; it is a grammar-level normalization of repeated edges.

### 3. Relational query induction

Given positive changed sites and negative unchanged sites across demonstrations:

1. generate normalized traces for every site;
2. retain traces present in all positives;
3. remove traces present in any negative;
4. search conjunctions in increasing description length;
5. select the smallest deterministic conjunction that covers all positives and rejects all observed negatives.

The learned result is `InducedRelationalQuery`, containing only normalized trace patterns, support counts, positive/negative counts, and a content-addressed query ID.

### 4. Patch macro composition

Reuse R2.49/R2.47 base `PatchMacro` inference for *what edit to perform*. Replace R2.49's handcrafted feature predicate with the new induced relational query for *where to perform it*. Applying a macro therefore requires both:

- a learned base edit signature;
- an automatically induced query whose path patterns match the candidate site.

### 5. Sparse executable CEGIS

Reuse the existing sparse executable patch solver. R2.50 candidate patches are compiled as Python and selected from a small initial visible test subset. Hidden tests reveal at most one counterexample per loop. Full held-out execution remains certification-only, not search guidance.

## Adversarial held-out design

The benchmark must make R2.49 structurally incapable of separating target and decoy sites:

- target and decoy use the same AST edit pattern;
- both have the same downstream alias/guard/return structure;
- `relational_features_for_site()` returns exactly equal feature sets for both;
- only operand-provenance structure differs.

Positive target operands originate from function parameters through zero or more pure alias assignments. Negative decoy operands originate from locally computed call expressions through aliases. Demonstrations vary alias depth. Held-outs use opaque identifiers, unseen alias depths, nested/deep downstream control-flow shapes, and shuffled source ordering.

R2.49 must fail to learn a separating context predicate or otherwise score 0 exact on the same held-outs. R2.50 must induce a query equivalent to “both operands are parameter-origin lineages” without that phrase or any equivalent high-level feature being hard-coded.

## Acceptance gates

R2.50 is accepted only if all are true on a clean GitHub runner:

1. R2.50 focused tests pass.
2. Frozen held-out is 6/6 exact with 0 false accepts.
3. R2.49 causal baseline is 0/6 or unable to learn a separating predicate on all held-outs.
4. For every held-out target/decoy pair, the complete R2.49 feature sets are equal.
5. Learned query signatures contain no raw identifiers and no task-specific constants.
6. Query structures are induced independently from demonstrations.
7. Sparse feedback uses at most 1% of executable tests before final certification.
8. Ablating query induction causes the baseline to fail.
9. R2.49 through R2.41 parent regression gates remain green.
10. Frozen evidence is recomputed from source in the same clean runner.
11. Nolane World 0.5.0 W5 audit is valid; W5 may remain false and must not be overridden.

## Failure handling

If no discriminative query can be induced, learning fails closed with an explicit error. It must not fall back to raw identifier names, AST positions, source line numbers, hidden test labels, or R2.49 handcrafted semantic features.

If multiple minimal queries tie, select deterministically by canonical serialized query signature.

## Readiness interpretation

Any readiness increase is an internal engineering-readiness heuristic, not a probability of AGI. A meaningful increase requires causal evidence that the representation-induction layer succeeds where R2.49's entire handcrafted feature vocabulary cannot.
