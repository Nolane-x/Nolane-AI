# R2.6 Invariant Program Induction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and preregister a zero-new-parameter R2.6 generalization firewall around selected R2.5 ARC program families, measure a frozen R2.5 baseline on a deterministic training-only split, and admit R2.6 candidates only when task-internal transfer evidence improves the preregistered internal-heldout result.

**Architecture:** Keep the R2.5 DSL/runtime as the baseline inference engine. Add isolated split, metamorphic, canonicalization, and firewall modules; R2.6 candidate records carry exact-fit plus generalization evidence. Development and internal-heldout are separated by a filename-only SHA256 rule, and INTERNAL_HELDOUT is opened only for the baseline and a frozen candidate gate.

**Tech Stack:** Python 3.12, existing `cogcoder` ARC runtime, GitHub Actions, pytest/simple executable tests, official ARC-AGI-2 submodule pinned at `f3283f727488ad98fe575ea6a5ac981e4a188e49`.

## Global Constraints

- Effective neural parameters remain exactly 78,779,253 in R2.6 phase A; add 0 neural parameters.
- Never use the consumed R2.5 public 120-task result as a development or tuning signal.
- ARC source revision remains `f3283f727488ad98fe575ea6a5ac981e4a188e49`.
- DEVELOPMENT/INTERNAL_HELDOUT split depends only on SHA256 of task filename: first 8 hex digits modulo 5; buckets 0–3 DEVELOPMENT, bucket 4 INTERNAL_HELDOUT.
- INTERNAL_HELDOUT output is aggregate-only: no solved-task IDs or task-content diagnostics are emitted.
- Fixed inference budget: 2 attempts per test input, 64 programs per task.
- First INTERNAL_HELDOUT run is frozen R2.5 baseline; next INTERNAL_HELDOUT run is allowed only after an R2.6 candidate source lock.
- A protocol change after heldout exposure requires a new R2.6b lock.

---

### Task 1: Deterministic split and preregistration lock

**Files:**
- Create: `cogcoder/r26_split.py`
- Create: `tests/test_r26_split.py`
- Create: `research/R2_6_PRETRAIN_LOCK.json`

**Interfaces:**
- Produces: `partition_name(filename: str) -> str`, returning `development` or `internal_heldout`.
- Produces: `partition_paths(paths: Iterable[Path]) -> tuple[tuple[Path, ...], tuple[Path, ...]]`.

- [ ] **Step 1: Write the failing split test**

```python
from cogcoder.r26_split import partition_name


def test_split_is_filename_only_and_stable():
    assert partition_name('abc123.json') == partition_name('abc123.json')
    assert partition_name('abc123.json') in {'development', 'internal_heldout'}
```

Add a second test that independently computes `int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) % 5` and checks the returned partition for 20 fixed filenames.

- [ ] **Step 2: Run RED**

Run: `PYTHONPATH=. python tests/test_r26_split.py`
Expected: import/module failure because `cogcoder.r26_split` does not exist.

- [ ] **Step 3: Implement minimal split**

```python
def partition_name(filename: str) -> str:
    digest = hashlib.sha256(Path(filename).name.encode('utf-8')).hexdigest()
    return 'internal_heldout' if int(digest[:8], 16) % 5 == 4 else 'development'
```

`partition_paths` sorts by filename and applies only `partition_name(path.name)`.

- [ ] **Step 4: Run GREEN and commit lock**

Run the split test, then commit `research/R2_6_PRETRAIN_LOCK.json` containing revision, split formula, attempts=2, max_programs=64, neural parameters, gate criteria, and explicit prohibition on public-score tuning.

### Task 2: Frozen R2.5 baseline on the R2.6 split

**Files:**
- Create: `scripts/measure_r26_baseline.py`
- Create: `.github/workflows/r26-baseline.yml`
- Create after CI result: `research/R2_6_BASELINE.json`

**Interfaces:**
- Consumes: `cogcoder.r26_split.partition_paths`.
- Consumes frozen R2.5 scorer from `cogcoder.r25_n_region.run` / `arc_candidate_region.program_set` at the current source baseline.
- Produces aggregate-only development and internal-heldout metrics.

- [ ] **Step 1: Add an executable test mode**

The script accepts a directory and produces JSON with only:
`development.{cases,solved,solve_rate,errors,mean_candidate_programs,mean_attempts_emitted}` and equivalent `internal_heldout`, plus `max_attempts`, `max_programs`, `arc_revision`.

- [ ] **Step 2: Ensure aggregate-only output**

No filename, solved-ID list, exception task ID, prediction, or grid content may appear in stdout/artifact.

- [ ] **Step 3: Run GitHub Actions against pinned training submodule**

Workflow checks exactly 1,000 training JSON files and pinned submodule revision, then runs with attempts 2 and max programs 64.

- [ ] **Step 4: Commit immutable baseline result**

Record the Actions run ID, source commit, partition counts, aggregate scores, and computed R2.6 heldout acceptance threshold. Do not inspect heldout task contents.

### Task 3: Metamorphic transform primitives

**Files:**
- Create: `cogcoder/r26_meta.py`
- Create: `tests/test_r26_meta.py`

**Interfaces:**
- Produces: `permute_colors(grid: Grid, mapping: tuple[tuple[int,int], ...]) -> Grid`.
- Produces: `transform_pair(pair, kind: str)` for `flip_h` and square-grid `rot90`.
- Produces: `inverse_kind(kind: str) -> str`.

- [ ] **Step 1: Write RED round-trip tests**

Tests cover color permutation inversion, horizontal reflection twice, and square rot90 four times.

- [ ] **Step 2: Run RED**

Expected module/import failure.

- [ ] **Step 3: Implement using existing `arc_grid.Grid` / geometric transform utilities**

Color mapping must be bijective over mapped colors and leave unmentioned colors unchanged.

- [ ] **Step 4: Run GREEN and existing ARC regression tests**

Commit only after round trips and existing R2.5 tests pass.

### Task 4: Task-level color-role canonicalization

**Files:**
- Create: `cogcoder/r26_canonical.py`
- Create: `tests/test_r26_canonical.py`

**Interfaces:**
- Produces: `color_role_signatures(pairs) -> dict[int, tuple]`.
- Produces: `canonical_color_roles(pairs) -> tuple[tuple[int,int], ...]` mapping raw colors to deterministic role indices.

- [ ] **Step 1: Write RED color-permutation test**

Construct two semantically identical pair sets under a bijective raw-color permutation. After canonicalization, normalized pair rows must be identical.

- [ ] **Step 2: Implement role statistics**

Use only visible demonstrations: background rank, in/out presence bits, frequency rank, component summaries, border/corner incidence, and same-shape changed-cell participation. Tie-break using structural statistics first; raw color ID is last-resort only and is not part of the canonical semantic signature.

- [ ] **Step 3: Run GREEN plus adversarial tie test**

When two colors are structurally indistinguishable, canonicalization must be deterministic and must report ambiguity rather than claiming semantic distinction.

### Task 5: Generalization firewall

**Files:**
- Create: `cogcoder/r26_firewall.py`
- Create: `tests/test_r26_firewall.py`

**Interfaces:**
- Defines `Evidence(loeo_passed: int, loeo_total: int, meta_passed: int, meta_total: int)`.
- Produces `validate_family(infer, pairs, *, meta_kinds=('color','flip_h','rot90')) -> Evidence`.
- `infer` contract: `infer(pairs) -> tuple[Program, ...]` with deterministic ordering.

- [ ] **Step 1: RED LOEO transfer test**

A simple input-to-output identity/transform inducer trained on N-1 demonstrations must predict the omitted example; a memorizer keyed to exact demonstration rows must fail at least one fold.

- [ ] **Step 2: GREEN LOEO implementation**

For `len(pairs) >= 3`, re-infer on each N-1 fold and require at least one emitted program to exactly predict the omitted pair. For fewer than three pairs, set `loeo_total=0`.

- [ ] **Step 3: RED/GREEN metamorphic test**

An equivariant transform family must pass deterministic color and flip transforms; a raw-color-ID-specific family must not receive a full metamorphic score.

- [ ] **Step 4: Commit firewall with no score-threshold tuning**

The firewall reports evidence; gate thresholds remain solely in the preregistered lock.

### Task 6: Evidence-bearing R2.6 candidate wrapper and DEVELOPMENT measurement

**Files:**
- Create: `cogcoder/r26_candidate.py`
- Create: `cogcoder/r26_score.py`
- Create: `tests/test_r26_score.py`
- Create: `scripts/measure_r26_development.py`
- Create: `.github/workflows/r26-development.yml`

**Interfaces:**
- Defines `Candidate(program: Program, evidence: Evidence, legacy: bool)`.
- Produces `program_set(pairs, limit=64) -> tuple[Candidate, ...]`.
- Produces `score(task, max_attempts=2, max_programs=64) -> TaskScore`.

- [ ] **Step 1: RED fixed-budget test**

Verify scorer rejects attempts outside {1,2}, never evaluates more than 64 candidates, and emits at most two distinct predictions per test input.

- [ ] **Step 2: Wrap legacy R2.5 candidates**

Legacy candidates remain available with `legacy=True` and neutral evidence. New R2.6 families are ranked by exact fit, LOEO ratio, metamorphic ratio, cost, signature.

- [ ] **Step 3: Run DEVELOPMENT only**

The workflow selects only DEVELOPMENT paths from the frozen split. It must not load INTERNAL_HELDOUT files into the scorer process.

- [ ] **Step 4: Iterate only on DEVELOPMENT and metamorphic unit tests**

Any new operator/family requires its own RED→GREEN test and must improve DEVELOPMENT generalization diagnostics without changing the split/gate/budget.

### Task 7: Candidate freeze and one-shot INTERNAL_HELDOUT gate

**Files:**
- Create: `research/R2_6_CANDIDATE_LOCK.json`
- Create: `.github/workflows/r26-heldout-gate.yml`
- Create after run: `research/R2_6_GATE_RESULT.json`

**Interfaces:**
- Consumes the exact source commit SHA and hashes of R2.6 runtime files.
- Produces aggregate-only gate result.

- [ ] **Step 1: Freeze source before heldout execution**

Lock source commit, file hashes, attempts=2, max_programs=64, split manifest hash, R2.5 baseline result hash, and gate threshold.

- [ ] **Step 2: Gate workflow validates lock/source equality**

Abort if checked-out source does not match the candidate lock.

- [ ] **Step 3: Run INTERNAL_HELDOUT exactly once for this protocol**

Output aggregate counts only. No task-level diagnostics are uploaded.

- [ ] **Step 4: Accept or reject without post-hoc threshold changes**

If gate passes, record R2.6 phase-A as training-only transfer evidence and begin a separate external-evidence protocol. If it fails, commit the negative result and keep R2.4 accepted.

### Task 8: Verification and milestone delivery

**Files:**
- Create/update: `archive/root-history/historical_r_series/R2_6_DELIVERY.md`
- Create: complete milestone ZIP and checksum outside git; persist recovery copy to Library.

- [ ] **Step 1: Run focused and regression tests**

Run all R2.6 tests plus existing R2.5 ARC tests and accepted R2.4 regression workflows where practical.

- [ ] **Step 2: Verify claim boundary**

No AGI, >100B equivalence, or ARC public-performance claim unless independently measured.

- [ ] **Step 3: Build complete ZIP**

Include source, tests, research locks/results, docs, current accepted one-weight, and negative evidence. Verify archive integrity, entry count, one-weight count, and SHA256.

- [ ] **Step 4: Persist to ChatGPT Library and provide sandbox ZIP**

Do not finish the milestone without both recoverable Library copy and user-downloadable complete ZIP.
