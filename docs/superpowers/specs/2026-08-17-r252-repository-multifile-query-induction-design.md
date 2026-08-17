# R2.52 Repository Multi-File Query Induction — Design

## Goal

Extend R2.51 from same-module interprocedural reasoning to a repository-level static Python capability that can learn identifier-invariant patch-localization queries across file/import boundaries and apply a multi-file patch transaction atomically.

## Scope

R2.52 supports a deliberately bounded Python repository subset:

- multiple `.py` files represented as an in-memory `path -> source` mapping;
- top-level synchronous functions;
- acyclic direct `from module import function [as alias]` imports between repository modules;
- direct calls through imported aliases or same-module function names;
- positional arguments only for cross-function binding;
- the R2.51 patch slots: binary operator, operand wrapper, compare operator, return wrapper;
- executable verification through a designated/inferred unique call-graph root.

R2.52 explicitly does not claim methods, classes, package-relative imports, `import module; module.fn`, recursion, cycles, dynamic dispatch, decorators, closures, higher-order functions, async, side-effectful module initialization, or arbitrary Python repositories.

## Architecture

### 1. Repository snapshot

`RepositorySnapshot` owns a normalized immutable mapping of repository-relative Python paths to source text. Paths must be unique, normalized, and map bijectively to module names (`a/b.py -> a.b`).

### 2. Repository fact graph

`build_repository_fact_graph(snapshot)` parses every module once and constructs one structural graph with:

- module nodes and `MODULE_CONTAINS` edges;
- function and AST nodes;
- scoped symbols keyed by `module::function::symbol`;
- syntax and intraprocedural flow facts inherited from R2.51 semantics;
- `IMPORTS_SYMBOL` edges from caller module bindings to imported function nodes;
- `CALL_TARGET`, `ARG_BIND`, `FLOW`, and materialized `FLOW*` edges across files.

No module path, function name, import alias, or variable name is placed in learnable node attributes. Identifiers are used only by the compiler/resolver, not by query features.

### 3. Learned repository query macros

Each training demonstration is `(before_snapshot, after_snapshot)` and must change exactly one function in exactly one file. The base edit is inferred from that changed function. Candidate sites are gathered across every module. Positive/negative labels are induced from AST differences, and the same bounded trace grammar used by R2.51 learns a minimal conjunction that separates the changed site from structurally similar decoys across the repository.

### 4. Atomic localization and application

All selected macros are localized against the exact immutable pre-edit repository graph. The localization plan records `(path, candidate_index)` targets. Only after every target is validated are edits applied to cloned ASTs. If any target is invalid, the whole transaction fails without returning a partial repository.

This preserves R2.51 causal semantics while extending the transaction boundary from one module to the full repository.

### 5. Candidate execution

The compiler topologically orders the static import DAG. Each module is executed with import statements removed and imported function objects injected from already-compiled dependency namespaces. The repository call graph must have exactly one uncalled top-level root function; that callable becomes the executable candidate entry point.

### 6. Frozen benchmark

Demonstrations use 2–3 files and shallow cross-file depth 1–2. Held-out episodes use 5–6 files and cross-file call depth 4–5 with opaque file/module/function/variable identifiers. The target requires three essential edits in three distinct files. Decoy sites use the same local syntax so a syntax-global baseline changes the wrong sites.

Frozen gates:

- 6/6 exact, zero false accepts;
- 10 learned macro families, each supported by two demonstrations;
- exact three-macro set selected in all episodes;
- three distinct files changed by the accepted candidate;
- R2.51 single-module boundary rejected on every episode;
- global syntax apply baseline 0/6;
- direct target patch 6/6;
- held-out file count 5–6 and call depth 4–5;
- initial 75 candidates;
- at most 2 revealed counterexamples and at most 6 observed tests out of 2,401;
- final exhaustive verification of all 2,401 tests;
- Python 3.11 and 3.13 focused determinism gate.

## Failure handling

Reject ambiguous module names, duplicate functions, unsupported imports, import cycles, missing imports, multiple roots, changed file/function sets in demonstrations, multiple changed functions per demonstration, candidate-count drift, invalid localization indices, and execution exceptions. The solver abstains rather than returning an unverified patch.

## Acceptance boundary

Passing R2.52 establishes a bounded repository-level static multi-file patch-localization capability. It does not establish general repository coding, AGI, unrestricted Python understanding, or autonomous software engineering.
