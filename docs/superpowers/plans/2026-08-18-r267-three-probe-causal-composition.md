# R2.67 Three-Probe Causal Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend accepted R2.66 from exactly two complementary pure-input interventions to one rigorously verified three-probe causal composition that strictly falsifies every singleton and pair ablation.

**Architecture:** Build a new R2.67 module on top of the accepted R2.66 semantic-normalization and bounded expression-synthesis primitives without modifying R2.66 production behavior. R2.67 profiles authorized interventions, schedules semantic triplets fairly, synthesizes a full three-probe expression, rejects any triplet solvable by a proper probe subset, synthesizes executable probe expressions, substitutes them, and grants authority only after fresh three-probe terminal re-observation plus final terminal verification.

**Tech Stack:** Python 3.11/3.13, existing `cogcoder` R2.56 expression DSL, R2.58 positional intervention schema, R2.59 semantic normalization, R2.66 bounded contextual expression synthesis, pytest, GitHub Actions, pinned NumPy 2.4.6.

**Spec:** `docs/superpowers/specs/2026-08-18-r267-three-probe-causal-composition-design.md`

## Global Constraints

- Exact parent: accepted R2.66 merge commit `e2eef08f15e7c0a5e79f58579282db90c157cb4a`.
- Added trainable parameters: exactly `0`.
- Pure deterministic mapping inputs and pure-input interventions only.
- Composition DSL remains the existing finite trusted R2.56/R2.66 DSL.
- Accepted full composition must use exactly all three probe symbols `__p0`, `__p1`, `__p2`.
- Every singleton and pair probe subset must fail under matched declared ablation grammar/budgets.
- Composition may reference only original positions untouched by all three selected interventions.
- Invalid/non-finite oracle behavior fails closed.
- Terminal evidence must be semantically disjoint from every oracle input used during learning.
- Every selected terminal intervention is validated before its oracle call.
- Terminal probe case units equal `3 * len(terminal_contexts)`.
- No source/evidence freeze until production source is final.
- Any frozen-blob change after lock requires complete remeasurement.

---

### Task 1: Establish hosted RED and public contract

**Files:**
- Create: `tests/test_r267_three_probe_causal_composition.py`
- Create: `.github/workflows/r267-three-probe-causal-composition.yml`

**Interfaces:**
- Consumes: accepted R2.66 only.
- Produces expected public API:
  - `ThreeProbeCompositionReceipt`
  - `discover_three_probe_structure(...)`
  - `synthesize_three_probe_causal_program(...)`

- [ ] **Step 1: Write the failing module/import contract**

```python
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program

FIELDS = ('a', 'b', 'c', 'd', 'e', 'f')


def tri_bilinear(row):
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def test_three_probe_module_starts_red_until_implemented():
    assert callable(synthesize_three_probe_causal_program)
```

- [ ] **Step 2: Add the hosted RED workflow**

```yaml
name: R2.67 Three-Probe Causal Composition
on:
  push:
    branches: [r267-three-probe-causal-composition-gpt56sol]
    paths:
      - 'cogcoder/r267_*.py'
      - 'tests/test_r267_*.py'
      - '.github/workflows/r267-three-probe-causal-composition.yml'
  pull_request:
    branches: [main]
jobs:
  focused:
    strategy:
      matrix:
        python-version: ['3.11', '3.13']
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: python -m pip install pytest
      - run: PYTHONPATH=. python -m pytest -q tests/test_r266_*.py
      - run: PYTHONPATH=. python -m pytest -q tests/test_r267_*.py
```

- [ ] **Step 3: Run hosted test and record RED**

Run: `PYTHONPATH=. python -m pytest -q tests/test_r267_three_probe_causal_composition.py`

Expected: collection failure with `ModuleNotFoundError: cogcoder.r267_three_probe_causal_composition`.

- [ ] **Step 4: Commit the RED contract only**

```bash
git add tests/test_r267_three_probe_causal_composition.py .github/workflows/r267-three-probe-causal-composition.yml
git commit -m 'test: define R2.67 three-probe causal RED contract'
```

### Task 2: Implement semantic intervention profiling and fair triplet discovery

**Files:**
- Create: `cogcoder/r267_three_probe_causal_composition.py`
- Extend: `tests/test_r267_three_probe_causal_composition.py`

**Interfaces:**
- Consumes:
  - `InterventionSpec`, `PositionalSchema`, `enumerate_interventions` from R2.58
  - `semantic_vector_key` from R2.59
  - `synthesize_contextual_expression`, `_equivalent`, `_used_fields`, `ContextualInterventionProfile` from R2.66
- Produces:

```python
@dataclass(frozen=True, slots=True)
class ThreeProbeCandidate:
    interventions: tuple[InterventionSpec, InterventionSpec, InterventionSpec]
    profiles: tuple[ContextualInterventionProfile, ContextualInterventionProfile, ContextualInterventionProfile]
    shared_positions: tuple[int, ...]
    expression: Expr
    used_fields: tuple[str, ...]
    composition_candidates_considered: int
    singleton_candidates_considered: tuple[int, int, int]
    pair_candidates_considered: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class ThreeProbeStructureReceipt:
    passed: bool
    selected: ThreeProbeCandidate | None
    legal_interventions: int
    triplets_considered: int
    composition_candidates_considered: int
    singleton_candidates_considered: int
    pair_candidates_considered: int
    oracle_calls: int
    false_accepts: int
    reason: str
    trainable_parameter_count: int = 0
```

- [ ] **Step 1: Add RED for exact three-probe use**

```python
def test_authored_family_discovers_expression_using_all_three_probes():
    receipt = _discover_authored()
    assert receipt.passed is True
    assert receipt.selected is not None
    assert {'__p0', '__p1', '__p2'} <= set(receipt.selected.used_fields)
```

- [ ] **Step 2: Add RED for semantic positional-order invariance**

```python
def test_triplet_semantics_are_invariant_to_field_permutation_under_roomy_budget():
    left = _discover_authored(FIELDS)
    right = _discover_authored(('f', 'a', 'd', 'c', 'b', 'e'))
    assert _selected_semantic_profiles(left) == _selected_semantic_profiles(right)
```

- [ ] **Step 3: Implement fail-closed profile collection**

Use original R2.66 oracle-validation semantics: query discovery/validation originals first, then each authorized intervention; return immediately with `reason='oracle_error:<type>:<message>'` on any invalid/non-finite intervention observation instead of skipping the failed intervention.

- [ ] **Step 4: Implement semantic profile identity**

```python
def _profile_semantic_id(profile: ContextualInterventionProfile) -> str:
    raw = semantic_vector_key(profile.outputs)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()
```

- [ ] **Step 5: Implement fair triplet scheduling**

Canonical triplet identity is the sorted tuple of three semantic profile IDs. Sort triplets by that identity before synthesis. Allocate a deterministic fair per-triplet slice:

```python
remaining_triplets = total_triplets - triplet_index
remaining_budget = max_total - total_composition_candidates
triplet_budget = min(per_triplet_cap, max(1, remaining_budget // remaining_triplets))
```

This guarantees position/hash order cannot let early triplets monopolize the global budget.

- [ ] **Step 6: Run focused discovery tests**

Run: `PYTHONPATH=. python -m pytest -q tests/test_r267_three_probe_causal_composition.py -k 'discover or invariant or three_probe'`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add cogcoder/r267_three_probe_causal_composition.py tests/test_r267_three_probe_causal_composition.py
git commit -m 'feat: add R2.67 semantic three-probe discovery'
```

### Task 3: Enforce strict singleton and pair ablation falsification

**Files:**
- Modify: `cogcoder/r267_three_probe_causal_composition.py`
- Modify: `tests/test_r267_three_probe_causal_composition.py`

**Interfaces:**
- Consumes selected triplet and full composition evidence.
- Produces `singleton_ablation_passed: tuple[bool, bool, bool]` and `pair_ablation_passed: tuple[bool, bool, bool]` in the accepted candidate/receipt evidence.

- [ ] **Step 1: Add RED that a pair-solvable task is rejected**

```python
def test_pair_sufficient_task_cannot_be_promoted_as_three_probe_capability():
    receipt = _discover_pair_sufficient_control()
    assert receipt.passed is False
    assert receipt.false_accepts == 0
```

- [ ] **Step 2: Add RED that every proper probe subset is searched**

```python
def test_selected_triplet_records_three_singleton_and_three_pair_ablations():
    receipt = _discover_authored()
    selected = receipt.selected
    assert selected is not None
    assert len(selected.singleton_candidates_considered) == 3
    assert len(selected.pair_candidates_considered) == 3
```

- [ ] **Step 3: Implement matched ablation helpers**

For singleton `i`, expose `('__p0',)` plus the same shared original fields; remap selected probe `i` to local `__p0`.

For pair `(i, j)`, expose `('__p0', '__p1')` plus the same shared original fields; remap those two selected probe vectors to the local pair names.

Use the same `composition_constants`, `composition_max_depth`, and explicit ablation candidate cap for all six searches.

- [ ] **Step 4: Reject any lower-order success**

Only candidates with:

```python
singleton_ablation_passed == (False, False, False)
pair_ablation_passed == (False, False, False)
```

may be structurally accepted.

- [ ] **Step 5: Run ablation tests**

Run: `PYTHONPATH=. python -m pytest -q tests/test_r267_three_probe_causal_composition.py -k ablation`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add cogcoder/r267_three_probe_causal_composition.py tests/test_r267_three_probe_causal_composition.py
git commit -m 'feat: require strict R2.67 lower-order falsification'
```

### Task 4: Synthesize executable probes and independent terminal authority

**Files:**
- Modify: `cogcoder/r267_three_probe_causal_composition.py`
- Modify: `tests/test_r267_three_probe_causal_composition.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True, slots=True)
class ThreeProbeCompositionReceipt:
    passed: bool
    structure: ThreeProbeStructureReceipt
    expression: Expr | None
    probe_expressions: tuple[Expr, ...]
    probe_candidates_considered: tuple[int, ...]
    probe_validation_cases: int
    probe_validation_exact: int
    final_validation_cases: int
    final_validation_exact: int
    reason: str
    trainable_parameter_count: int = 0
    oracle_calls_total: int = 0
    terminal_probe_validation_cases: int = 0
    terminal_probe_validation_exact: int = 0
```

- [ ] **Step 1: Add RED for terminal selected-probe re-observation**

Inject `NaN` only on previously unseen terminal applications of the selected interventions. Assert the oracle is actually called on those inputs and receipt fails.

- [ ] **Step 2: Add RED for validator-before-oracle ordering**

Have `context_validator` reject selected terminal interventions and count oracle calls. Assert rejected contexts produce zero oracle calls.

- [ ] **Step 3: Add RED for semantic terminal disjointness**

Use an integer learning context and float-equivalent terminal alias. Assert `ValueError` before terminal authority.

- [ ] **Step 4: Add tracked oracle**

```python
oracle_calls_total = 0
queried_keys: set[str] = set()

def tracked_oracle(context):
    nonlocal oracle_calls_total
    key = _context_key(schema, context)
    queried_keys.add(key)
    oracle_calls_total += 1
    return _finite_json_value(oracle(dict(context)))
```

- [ ] **Step 5: Synthesize three executable probes**

For each selected intervention, project discovery/validation inputs to positions not overwritten by that intervention and synthesize its output with the existing R2.56 operator synthesis path. Require exact validation success for all three.

- [ ] **Step 6: Substitute all three probes**

Map `__p0`, `__p1`, `__p2` to the three synthesized probe expressions and recursively rewrite the composition expression.

- [ ] **Step 7: Terminally verify all three probes then final expression**

For every terminal context, perform three fresh selected-intervention observations and one original-context observation. On success:

```python
terminal_probe_validation_cases == 3 * len(terminal)
terminal_probe_validation_exact == terminal_probe_validation_cases
final_validation_cases == len(terminal)
final_validation_exact == len(terminal)
```

- [ ] **Step 8: Run terminal-authority tests**

Run: `PYTHONPATH=. python -m pytest -q tests/test_r267_three_probe_causal_composition.py -k 'terminal or validator or oracle'`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add cogcoder/r267_three_probe_causal_composition.py tests/test_r267_three_probe_causal_composition.py
git commit -m 'feat: add R2.67 executable probes and terminal authority'
```

### Task 5: Freeze authored tri-bilinear benchmark

**Files:**
- Create: `benchmarks/kfigg/r267_three_probe_causal_composition.py`
- Create: `tests/test_r267_three_probe_causal_benchmark.py`

**Interfaces:**
- Produces `run_benchmark() -> dict[str, object]` with stable JSON-compatible evidence.

- [ ] **Step 1: Define deterministic authored rows**

Use independent signed tuples such as:

```python
CONFIGS = (
    (2.0, -3.0, 5.0, 7.0, -11.0, 13.0),
    (-4.0, 9.0, 6.0, -5.0, 3.0, 8.0),
    (7.0, 2.0, -9.0, 4.0, 5.0, -6.0),
    (-8.0, -3.0, 11.0, 2.0, -5.0, 7.0),
    (3.0, 10.0, -4.0, -7.0, 9.0, 2.0),
    (12.0, -2.0, 5.0, -9.0, -3.0, 4.0),
    (-6.0, 5.0, 8.0, 3.0, 7.0, -4.0),
    (9.0, -8.0, -2.0, 11.0, 4.0, 6.0),
)
```

Split deterministically into discovery, validation, and terminal rows without reuse.

- [ ] **Step 2: Assert the authored capability gates**

Required result keys include:

```python
'all_gates_pass': True
'full_uses_all_three_probes': True
'all_singleton_ablations_fail': True
'all_pair_ablations_fail': True
'probe_validation_exact': probe_validation_cases * 3
'terminal_probe_validation_exact': terminal_probe_validation_cases
'final_validation_exact': final_validation_cases
'false_accepts': 0
'rename_invariant': True
'positional_semantic_invariant': True
'trainable_parameter_count': 0
```

- [ ] **Step 3: Add deterministic replay test**

Call `run_benchmark()` twice and assert the returned dictionaries are exactly equal.

- [ ] **Step 4: Run benchmark tests**

Run: `PYTHONPATH=. python -m pytest -q tests/test_r267_three_probe_causal_benchmark.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add benchmarks/kfigg/r267_three_probe_causal_composition.py tests/test_r267_three_probe_causal_benchmark.py
git commit -m 'test: add R2.67 authored three-probe benchmark'
```

### Task 6: Add pinned NumPy-dot external transfer

**Files:**
- Create: `research/r267_external_dot_transfer.py`
- Create: `tests/test_r267_external_dot_transfer.py`
- Create: `.github/workflows/r267-external-dot-transfer.yml`

**Interfaces:**
- Produces `run_external_transfer(dot_callable, *, source_id: str, source_version: str) -> dict[str, object]`.

- [ ] **Step 1: Write the external adapter before executing held-out evidence**

```python
def oracle_from_dot(dot_callable):
    def oracle(row):
        left = [row['a'], row['c'], row['e']]
        right = [row['b'], row['d'], row['f']]
        return float(dot_callable(left, right))
    return oracle
```

- [ ] **Step 2: Add external evidence assertions**

```python
assert result['source_id'] == 'numpy.dot'
assert result['source_version'] == '2.4.6'
assert result['source_exposure'] == 'io_only'
assert result['passed'] is True
assert result['all_singleton_ablations_fail'] is True
assert result['all_pair_ablations_fail'] is True
assert result['challenge_exact'] == result['challenge_cases']
assert result['heldout_exact'] == result['heldout_cases']
assert result['false_accepts'] == 0
assert result['trainable_parameter_count'] == 0
```

- [ ] **Step 3: Add GitHub Action with exact dependency pin**

Install `numpy==2.4.6`, run accepted R2.66 first, then R2.67 external tests, recompute fresh external evidence, and upload the JSON receipt.

- [ ] **Step 4: Run external transfer**

Run: `PYTHONPATH=. python -m pytest -q tests/test_r267_external_dot_transfer.py`

Expected: PASS with NumPy 2.4.6 installed.

- [ ] **Step 5: Commit**

```bash
git add research/r267_external_dot_transfer.py tests/test_r267_external_dot_transfer.py .github/workflows/r267-external-dot-transfer.yml
git commit -m 'research: add R2.67 pinned NumPy-dot transfer'
```

### Task 7: Add independent falsifiers and accounting hardening

**Files:**
- Create: `tests/test_r267_three_probe_independent_blockers.py`
- Modify only if RED proves a real defect: `cogcoder/r267_three_probe_causal_composition.py`

**Interfaces:**
- No new capability surface. This task attacks authority and accounting.

- [ ] **Step 1: Add six independent blockers**

Cover:

```text
numeric-semantic terminal alias
learning-profile input reused as terminal intervention
non-finite intervention-only oracle result
pair-ablation false promotion
triplet hard-budget positional ordering
terminal validator rejection before oracle
```

- [ ] **Step 2: Run blockers before any hardening mutation**

Run: `PYTHONPATH=. python -m pytest -q tests/test_r267_three_probe_independent_blockers.py`

Expected: either all PASS, or one/more reproducible REDs identifying exact defects.

- [ ] **Step 3: Fix only demonstrated root causes**

Do not widen the DSL or budget to make tests pass. Preserve the same accepted capability boundary.

- [ ] **Step 4: Run full focused regression**

```bash
PYTHONPATH=. python -m pytest -q tests/test_r267_*.py
PYTHONPATH=. python -m pytest -q tests/test_r266_*.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_r267_three_probe_independent_blockers.py cogcoder/r267_three_probe_causal_composition.py
git commit -m 'test: harden R2.67 independent authority blockers'
```

### Task 8: Freeze evidence, run protected lineage, and build COMPLETE release

**Files:**
- Create: `archive/root-history/historical_r_series/R2_67_PHASE_A_RESULT.json`
- Create: `archive/root-history/historical_r_series/R2_67_EXTERNAL_TRANSFER.json`
- Create: `archive/root-history/historical_r_series/R2_67_PRE_HOSTED_LOCK.json`
- Create: `.github/workflows/r267-canonical-gate.yml`
- Create: `.github/workflows/r267-freeze-evidence.yml`
- Create: `.github/workflows/r267-release-bundle.yml`

**Interfaces:**
- Produces exact frozen release evidence and `Nolane-AI-R2.67-COMPLETE.zip` plus SHA-256.

- [ ] **Step 1: Recompute authored and external evidence from final source**

Write canonical JSON with `json.dumps(..., indent=2, sort_keys=True) + '\n'` and never hand-edit result fields.

- [ ] **Step 2: Freeze exact blobs**

Lock all R2.67 production, tests, benchmark, research adapter, spec, and release workflows using `git hash-object` receipts. Record exact accepted R2.66 parent `e2eef08f15e7c0a5e79f58579282db90c157cb4a`.

- [ ] **Step 3: Run canonical cross-Python gate**

Require Python 3.11 and 3.13 R2.67 focused tests plus exact frozen-source verification.

- [ ] **Step 4: Run protected lineage**

Run R2.67, R2.66, R2.65, then all protected R2.64→R2.41 suites exactly as the accepted R2.66 canonical/release workflows do.

- [ ] **Step 5: Create the complete repository ZIP**

```bash
mkdir -p release
git archive --format=zip -o release/Nolane-AI-R2.67-COMPLETE.zip HEAD
sha256sum release/Nolane-AI-R2.67-COMPLETE.zip > release/Nolane-AI-R2.67-COMPLETE.zip.sha256
unzip -tq release/Nolane-AI-R2.67-COMPLETE.zip
```

- [ ] **Step 6: Verify required ZIP contents**

At minimum assert the archive contains the three R2.67 evidence JSON files, production module, benchmark, external adapter, all R2.67 tests, spec, plan, and release workflows.

- [ ] **Step 7: Upload artifact and publish success status**

Use `actions/upload-artifact@v4`; publish `r267/release-bundle` status only on success.

- [ ] **Step 8: Independently download and verify the produced artifact**

Verify the outer artifact archive, inner COMPLETE ZIP integrity, and SHA-256 before promotion.

- [ ] **Step 9: Persist the final COMPLETE ZIP to ChatGPT Library**

Upload the verified inner `Nolane-AI-R2.67-COMPLETE.zip` and its SHA file to the Library.

- [ ] **Step 10: Promote only the exact verified head**

Mark the R2.67 PR ready and merge with an expected-head SHA guard only after canonical full gate and complete release bundle are both freshly green.
