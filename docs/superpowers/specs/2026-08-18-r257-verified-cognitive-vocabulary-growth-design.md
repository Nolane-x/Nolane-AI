# R2.57 Verified Cognitive Vocabulary Growth — Design

## Status
Approved for inline execution by the user's instruction to continue and finish the proposed R2.57 direction without intermediate approval stops.

## Problem
R2.56 can invent a new pure operator instance, but every invented expression is still searched inside a fixed human-written primitive vocabulary. It does not learn a reusable *language of thought* from solved operators. Re-solving structurally related tasks therefore pays the same low-level search cost repeatedly.

## Goal
Learn parameterized, reusable cognitive abstractions from a corpus of independently verified R2.56 expressions; admit an abstraction only when it has multi-task support and positive description-length compression; then expose the abstraction as a safe first-class synthesis primitive for later tasks. The learned vocabulary must remain pure, deterministic, content-addressed, acyclic, bounded, challengeable, and removable.

## Research grounding
The design follows the library-learning pattern behind DreamCoder (grow a DSL from reusable abstractions), Stitch (compression-driven abstraction discovery), and LILO/LAPS (learned libraries that improve later synthesis/search). R2.57 deliberately implements a small, auditable symbolic version rather than adding another neural component.

## Non-goals
- Arbitrary Python/code generation.
- I/O, tool, filesystem, network, subprocess, clock, random, reflection, import, eval, or exec invention.
- Recursive learned abstractions.
- Claiming open-ended language invention or AGI.
- Letting an abstraction self-promote because it compresses one task.

## Architecture

### 1. Parameterized template representation
Create `cogcoder/r257_vocabulary.py` with:
- `TemplateParam(Expr)` — a non-executable placeholder used only inside learned templates.
- `LearnedAbstraction` — content-addressed ID, ordered parameter names, template, support task IDs, compression accounting, and provenance.
- `AbstractionCall(Expr)` — a pure call node referencing a promoted abstraction plus argument expressions.
- `CognitiveVocabulary` — immutable-ish child vocabulary over a fixed parent R2.56 grammar.

An abstraction call is never executed directly. It is expanded by capture-free substitution into ordinary R2.56 `Expr`, bounded by maximum expansion nodes and maximum nesting depth, then evaluated through R2.56's existing pure evaluator.

### 2. Corpus-guided abstraction discovery
Create `cogcoder/r257_library_learning.py`.

Input is a corpus of `(task_id, verified_expr)` records. The learner:
1. extracts all non-trivial subexpressions;
2. groups structurally compatible subexpressions across distinct tasks;
3. anti-unifies each group into a parameterized template;
4. preserves repeated-variable equality constraints;
5. requires support from at least 3 distinct tasks;
6. computes an MDL-style score:
   `raw_occurrence_cost - (definition_cost + rewritten_call_cost)`;
7. keeps only strictly positive compression;
8. deterministically ranks by compression, support, template cost, then digest.

No task names or user-supplied semantic labels may influence discovery.

### 3. Vocabulary lifecycle and safety
A discovered abstraction starts as `candidate`, moves to `probation`, and is challenged on held-out verified expressions from tasks not used to propose it. Promotion requires:
- exact expansion/evaluation agreement on every challenge;
- positive compression after challenge inclusion;
- no cycle/recursion;
- expansion budget respected;
- pure side-effect class;
- content-addressed digest collision check.

Failure quarantines the abstraction. A post-promotion counterexample removes it from the child vocabulary and rolls back any working-state mutation caused by the failed use.

### 4. Vocabulary-aware synthesis
Create `cogcoder/r257_vocabulary_synthesis.py`.

The enumerator keeps R2.56 primitives but adds promoted abstractions as grammar productions. Calls are generated only from already-enumerated lower-depth arguments and are semantically deduplicated on the current examples. Search accounting counts every evaluated candidate so learned-vocabulary gains can be compared causally against the R2.56 base grammar under identical budgets.

The key claim is not merely that macros are shorter. The same target must be unsolved by R2.56 within a frozen depth/candidate budget and solved when the learned vocabulary is enabled.

## Authored mechanism benchmark
Create `benchmarks/kfigg/r257_verified_vocabulary_growth.py`.

Training corpus contains opaque tasks whose verified solutions repeatedly contain three latent abstractions without naming them:
- ternary clamp pattern `min(max(value, lower), upper)`;
- linear interpolation pattern `start + amount * (end - start)`;
- normalization pattern `(value - lower) / (upper - lower)` with repeated lower-bound binding.

Requirements:
- at least 6 distinct supporting tasks per learned abstraction;
- learned names are digest-based, not `clamp`/`lerp` labels;
- both abstractions have positive compression;
- challenge tasks use renamed fields/constants;
- a held-out composed family requires the learned vocabulary to stay inside a frozen search/depth budget;
- R2.56 base grammar under the same budget must score 0 on those composed heldouts;
- one deliberately bad candidate abstraction must be quarantined;
- one promoted abstraction must be revoked on a live counterexample with state rollback.

## Independent external transfer
Pinned source: `WarrenWeckesser/ufunclab@f1fbe6769850823a1976ccc28d14cd966130b645`.

Hosted CI installs the pinned package and uses `ufunclab.linearstep` only as an oracle to generate scalar I/O. The synthesis learner receives only I/O examples, never source text or AST.

Gate:
- vocabulary is learned before seeing `linearstep` oracle examples;
- R2.56 base synthesis fails under the frozen depth/candidate budget;
- R2.57 vocabulary synthesis passes training/challenge and at least 24 post-promotion heldout oracle cases;
- exact scalar agreement within deterministic floating tolerance;
- external evidence records oracle commit, input sets, learned abstraction digests, base/extended search counts, and no source exposure.

This is evidence for learned-vocabulary transfer to one external pure numeric function, not general repository autonomy.

## Testing and acceptance
- TDD RED→GREEN for template substitution, anti-unification, compression, cycle rejection, promotion/quarantine/revocation, and vocabulary-aware synthesis.
- Frozen authored benchmark.
- External ufunclab transfer in clean GitHub CI.
- R2.56→R2.41 protected lineage.
- Python 3.11 and 3.13 focused matrix.
- Nolane World adversarial audit with W5 allowed to remain false.
- Readiness moves only if external transfer is clean; increase must remain small.
- Final release is generated from final `main` with SHA-256 and `unzip -tq`, then persisted to Library.
