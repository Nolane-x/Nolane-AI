# R2.9 Verifier-Guided Patch Search Design

Date: 2026-08-15
Status: approved by standing autonomous research instruction

## Goal

Add a language-agnostic, parameter-free patch-search runtime that can choose and refine candidate source edits using execution feedback, repository-risk evidence, and uncertainty rather than one-shot generation.

## Why this milestone

R2.8 can choose what investigation/edit action to take but does not search over concrete patch candidates. The current 79.4M stack also has no general source-code token decoder. R2.9 therefore isolates the next missing capability: inference-time patch search over externally proposed or symbolic candidate edits. It must not be represented as arbitrary code generation.

## Research basis

The design combines three current findings: iterative/global patch search can outperform local trial-and-error; execution-level runtime evidence is more informative than binary pass/fail; and entropy-guided test-time scaling can allocate search budget efficiently. Nolane adapts these ideas to a compact-model setting by moving search, memory, and verification outside the neural core.

## Architecture

### 1. Patch candidate representation

`PatchCandidate` is immutable and contains:
- stable candidate id;
- one or more `TextEdit` operations (`path`, byte-independent line span, replacement text);
- parent candidate id for refinement lineage;
- provenance label;
- optional targeted hypothesis ids.

Edits are applied in-memory to a `RepositorySnapshot`. Candidate application must reject overlapping edits, invalid spans, missing files, and duplicate canonical patch fingerprints.

### 2. Execution evidence

`VerificationResult` records:
- targeted tests passed/failed;
- full regression tests passed/failed when available;
- verifier scalar in [0,1];
- changed file count and line count;
- structured observations/tags supplied by the execution adapter;
- terminal success flag.

R2.9 does not execute arbitrary host commands itself. It consumes a callback implementing `PatchEvaluator` so benchmark/runtime sandboxes retain authority over execution.

### 3. Search memory

`PatchSearchMemory` stores fingerprints and results of all explored candidates. Repeated candidates are never re-evaluated. Failed candidates remain informative: their verification evidence is attached to descendants and used to discourage equivalent/redundant branches.

### 4. Candidate utility

Candidate priority combines:
- verifier score;
- targeted-test progress;
- full-test status;
- coverage of currently likely hypotheses;
- novelty versus explored fingerprints;
- patch-size penalty;
- R2.8 graph-derived blast-radius penalty;
- lineage regression penalty.

A terminal candidate is accepted only when evaluator reports `success=True`; a high heuristic score alone cannot finish the task.

### 5. Budgeted best-first search

`VerifierGuidedPatchSearch` performs deterministic best-first search with:
- hard evaluation budget;
- deterministic tie-breaking;
- candidate deduplication;
- optional `refine(candidate, result)` callback that may emit child candidates using execution evidence;
- early stop on verified success;
- an explicit search trace.

The engine is proposal-source agnostic. R2.9 tests it with a small symbolic proposer. R2.10 may plug in a neural edit decoder without changing search semantics.

## Phase-A locked evidence

Internal benchmark uses hidden-fix micro repositories and decoy patches. The locked gate must include at least four tasks where:
1. a plausible small patch fails targeted verification and a refinement succeeds;
2. two patches both fix the target but the lower-blast-radius patch must rank first;
3. duplicate-equivalent patches are emitted under different ids and evaluated only once;
4. a high heuristic/verifier candidate that fails a required regression test cannot be accepted.

Required Phase-A metrics before implementation tuning:
- verified solve rate: 4/4;
- no false terminal acceptance: 0;
- duplicate evaluator calls: 0;
- deterministic trace under candidate-id renaming: 4/4;
- evaluation budget: <= 8 per task;
- neural parameters added: 0;
- external coding claim allowed: false.

## Claim boundary

Passing Phase A establishes only that the implemented search engine can select/refine candidate text patches under a locked synthetic executable protocol. It does not establish arbitrary patch generation, fresh-repository SWE-bench performance, AGI, or frontier-model parity.

## Next milestone if accepted

R2.10: neural/source-aware edit proposal. Train or attach a compact edit proposer that emits patch candidates conditioned on issue text, localized code context, R2.8 hypotheses, and R2.9 execution history; keep R2.9 verifier-guided search unchanged as the safety/evidence layer.
