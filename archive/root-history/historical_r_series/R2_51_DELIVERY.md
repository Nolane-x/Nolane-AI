# R2.51 — Interprocedural Call-Flow Query Induction

## Decision

**ACCEPTED_BOUNDED_CAPABILITY.** Capability commit: `22109477052e915d5d72ec1e219a5709ea03364f`.

GitHub Actions run `32020651161`, main job `95359439683`, completed successfully on Ubuntu 24.04 / Python 3.11.15. R2.51 passed 4/4 focused tests; R2.50 plus R2.49-R2.47 passed 26/26; R2.46 passed 5/5; R2.45-R2.44 passed 15/15; R2.43-R2.41 passed 31/31. Separate focused R2.51 jobs passed on Python 3.11 and 3.13. R1.9, R2.0i and R2.2 integrity workflows also succeeded on the same capability commit.

## Capability

R2.51 extends self-induced relational patch localization across direct static helper/caller boundaries. It builds a module-wide, identifier-invariant program graph with scoped symbols, call targets, argument binding, return-to-call value flow and generic transitive `FLOW*`. Changed positive sites and unchanged decoy sites induce minimal relational queries. Learned macros are localized once against an immutable pre-edit graph and then applied transactionally, allowing multiple edits to compose without earlier edits destroying later localization evidence.

The first implementation exposed two real defects and both were fixed before acceptance: candidate AST nodes were initially mapped against a separately reparsed graph, and naive path expansion after materialized `FLOW*` caused search explosion. The accepted implementation builds the graph from the exact candidate AST, treats `FLOW*` as terminal in abstract trace enumeration, deduplicates abstract states, and reuses one localization plan across the Cartesian patch candidate space.

Frozen heldout result: 6/6 exact, zero false accepts, 10 learned macro families, 75 candidates, exact three-macro patch selected in all six episodes, opaque identifiers, and unseen heldout call depths 4-5 after demonstrations at depths 1-2. R2.50 rejects all six as out-of-scope; a global syntax-apply baseline scores 0/6; direct essential patch scores 6/6. Sparse CEGIS starts with four tests, reveals at most two counterexamples, observes at most 6/2,401 tests (0.2499%), and then certifies all 2,401 executable tests.

## Nolane World 0.5.0 audit

World `world4_efb3158d7f354308` was run at W5 depth. Audit is valid with digest `b0f471b079fabf74a9822b3355201153459091effcbbbf32bb9272186a00fe4d`. W5 gate remains **false** with score `0.50`. The unresolved frontier includes architect-provided `FLOW*`, direct same-module calls only, no methods/imports/recursion/higher-order dispatch, no multi-file transaction, repository-scale graph complexity, generated-family breadth, deterministic tests, and bounded edit/query language.

## Coding-AGI engineering-readiness

Internal rubric: **48.0/100**, up from the previous accepted release R2.49 at 39.0/100. This is an engineering-readiness heuristic for general coding intelligence, **not a probability that the system is AGI**.
