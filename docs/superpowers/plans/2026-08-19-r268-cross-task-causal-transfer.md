# R2.68 Cross-Task Causal Program Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a zero-parameter cross-task causal transfer engine that exports only a canonical three-probe expression prior, actively binds/adapts it on a distinct target task, rejects negative transfer, and measures advantage against a matched scratch hypothesis space.

**Architecture:** Add one isolated R2.68 module over the existing R2.56 expression DSL and R2.67 receipt type. Source export strips all task identities and retains only an abstract probe-role expression. Target adaptation generates a frozen local repair neighborhood without target labels, chooses diagnostic contexts by candidate disagreement, queries a target oracle only after context selection, prunes the version space, and requires disjoint terminal verification. A separate scratch baseline uses the same active selector and oracle contract over a broader bounded grammar.

**Tech Stack:** Python 3.11/3.13, dataclasses, existing `cogcoder.r256_operator_dsl`, existing R2.67 receipt types, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-19-r268-cross-task-causal-transfer-design.md`

## Global Constraints

- Added trainable neural parameters: exactly `0`.
- Portable serialization must not contain source field names, intervention IDs, semantic profile IDs, raw source examples, or source outputs.
- Candidate generation must not receive target oracle outputs.
- Target diagnostic selection must occur before the corresponding oracle call.
- Selection and terminal contexts must be canonically disjoint.
- Any budget exhaustion, ambiguity, invalid terminal evaluation, or terminal mismatch fails closed.
- No unrestricted scratch fallback is allowed inside the transfer solver.
- R2.68 remains research-only until rebased on the exact accepted R2.67.1-or-successor parent.

---

### Task 1: Portable causal expression export

**Files:**
- Create: `cogcoder/r268_cross_task_causal_transfer.py`
- Create: `tests/test_r268_cross_task_causal_transfer.py`

**Interfaces:**
- Consumes: `cogcoder.r267_three_probe_causal_composition.ThreeProbeCompositionReceipt`, `cogcoder.r256_operator_dsl.Expr`.
- Produces: `PortableCausalProgram`, `export_portable_program(receipt)`.

- [ ] **Step 1: Write the failing export tests**

```python
from dataclasses import replace
from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r268_cross_task_causal_transfer import PortableCausalProgram, export_expression_prior


def test_expression_prior_serialization_is_identity_free():
    source = Binary('add', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))
    portable = export_expression_prior(source)
    data = portable.to_data()
    assert data['probe_roles'] == ['__p0', '__p1', '__p2']
    assert data['expression'] == source.to_data()
    serialized = str(data)
    for forbidden in ('source_a', 'source_b', 'intervention-', 'semantic-profile'):
        assert forbidden not in serialized
    assert portable.trainable_parameter_count == 0


def test_expression_prior_rejects_non_three_probe_expression():
    source = Binary('add', Field('__p0'), Field('__p1'))
    with pytest.raises(ValueError, match='exactly three abstract probe roles'):
        export_expression_prior(source)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `PYTHONPATH=. python -m pytest -q tests/test_r268_cross_task_causal_transfer.py`

Expected: import failure because `cogcoder.r268_cross_task_causal_transfer` does not exist.

- [ ] **Step 3: Implement the minimal portable representation**

Implement:

```python
@dataclass(frozen=True, slots=True)
class PortableCausalProgram:
    expression: Expr
    expression_digest: str
    probe_roles: tuple[str, str, str] = ('__p0', '__p1', '__p2')
    trainable_parameter_count: int = 0

    def to_data(self) -> dict[str, object]: ...


def export_expression_prior(expression: Expr) -> PortableCausalProgram: ...
```

Validate that `_used_fields(expression)` is exactly `{'__p0','__p1','__p2'}` and that no non-abstract fields appear.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `PYTHONPATH=. python -m pytest -q tests/test_r268_cross_task_causal_transfer.py`

Expected: export tests pass.

- [ ] **Step 5: Commit**

Commit message: `feat: add identity-free R2.68 causal prior`

---

### Task 2: Target-label-free repair neighborhood and active binding

**Files:**
- Modify: `cogcoder/r268_cross_task_causal_transfer.py`
- Modify: `tests/test_r268_cross_task_causal_transfer.py`

**Interfaces:**
- Consumes: `PortableCausalProgram`, unlabeled target contexts, `oracle(context) -> object`.
- Produces: `TransferCandidate`, `TransferReceipt`, `generate_transfer_candidates(portable)`, `adapt_portable_program(...)`.

- [ ] **Step 1: Add RED tests for candidate generation and active adaptation**

Use a transferred `add(add(p0,p1),p2)` source prior. Positive target 1 uses a probe-role permutation and the same composition. Positive target 2 uses exactly one operator repair, for example `add(mul(p0,p1),p2)`. Assert that:

```python
candidates = generate_transfer_candidates(portable)
assert candidates == tuple(sorted(candidates, key=lambda row: row.candidate_id))
assert len({row.candidate_id for row in candidates}) == len(candidates)

receipt = adapt_portable_program(
    portable,
    diagnostic_contexts=DIAGNOSTICS,
    terminal_contexts=TERMINALS,
    oracle=target_oracle,
    max_selection_queries=3,
    max_candidates=96,
)
assert receipt.passed is True
assert receipt.false_accepts == 0
assert receipt.selection_queries <= 3
assert receipt.terminal_queries == len(TERMINALS)
assert receipt.trainable_parameter_count == 0
```

Add an oracle wrapper that records calls and assert no oracle call happens before a diagnostic context is selected by the solver trace.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: missing `generate_transfer_candidates` / `adapt_portable_program`.

- [ ] **Step 3: Implement frozen repair generation**

Implement recursive helpers that:

- preserve the exact transferred expression;
- enumerate all six abstract probe-role permutations;
- mutate exactly one `Binary.op` over `('add','sub','mul','div','min','max')`;
- apply probe permutations to repaired expressions;
- canonicalize/deduplicate with `expr_digest`;
- never accept target labels as an argument.

- [ ] **Step 4: Implement active version-space pruning**

For each unqueried diagnostic context, evaluate all live candidates without an oracle and partition candidates by canonicalized predicted output. Select the context minimizing the largest partition, then maximizing partition count, then by canonical context key. Query the oracle only for that chosen context, prune candidates to equivalent predictions, and repeat until one candidate remains or the hard query budget is exhausted.

Require at least one selected diagnostic query before terminal acceptance. If the live version space is non-singleton and no remaining diagnostic separates it, return `reason='ambiguous_transfer_version_space'`.

- [ ] **Step 5: Implement independent terminal verification**

Reject overlapping selection/terminal contexts before any oracle call. Once one candidate remains, query every terminal context and require exact finite agreement. First mismatch returns a failed receipt with `false_accepts=0`; no candidate is accepted before all terminal cases pass.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run: `PYTHONPATH=. python -m pytest -q tests/test_r268_cross_task_causal_transfer.py`

- [ ] **Step 7: Commit**

Commit message: `feat: add active cross-task causal adaptation`

---

### Task 3: Negative transfer and matched scratch baseline

**Files:**
- Modify: `cogcoder/r268_cross_task_causal_transfer.py`
- Modify: `tests/test_r268_cross_task_causal_transfer.py`
- Create: `benchmarks/kfigg/r268_cross_task_causal_transfer.py`

**Interfaces:**
- Produces: `generate_scratch_candidates(max_depth, max_candidates)`, `solve_from_scratch(...)`, `run_benchmark()`.

- [ ] **Step 1: Add RED negative-transfer tests**

Add a target that needs at least two operator changes relative to the source prior and assert a tight transfer neighborhood abstains. Add an ambiguous diagnostic pool where two candidates survive selection but terminal evidence separates them; assert terminal verification selects at most one and never false-accepts.

- [ ] **Step 2: Add RED scratch-baseline tests**

Implement a frozen scratch grammar over `__p0/__p1/__p2`, numeric binary ops `add/sub/mul/min/max`, maximum depth 2, semantic deduplication on public diagnostic contexts, and a hard candidate cap. Assert:

- tight transfer solves the one-repair family within `<=3` oracle selection queries;
- matched tight scratch fails closed or uses strictly more selection queries;
- roomy scratch solves the same target;
- source-prior ablation removes the transfer advantage.

- [ ] **Step 3: Implement scratch candidate generation and solver reuse**

Reuse the same active selector/terminal verifier used by transfer so the comparison differs only in the initial hypothesis space. Scratch generation must not receive oracle outputs.

- [ ] **Step 4: Implement deterministic authored benchmark**

`run_benchmark()` returns JSON-serializable evidence containing per-family receipts and aggregate gates:

```python
{
  'milestone': 'R2.68',
  'capability': 'cross-task-causal-program-transfer',
  'all_gates_pass': bool,
  'positive_transfer_cases': int,
  'positive_transfer_exact': int,
  'negative_transfer_cases': int,
  'negative_transfer_abstained': int,
  'false_accepts': int,
  'trainable_parameter_count': 0,
  'transfer_selection_queries_total': int,
  'tight_scratch_selection_queries_total': int,
  'roomy_scratch_exact': int,
  'identity_invariance': bool,
}
```

- [ ] **Step 5: Run benchmark and tests**

Run:

```bash
PYTHONPATH=. python -m pytest -q tests/test_r268_cross_task_causal_transfer.py
PYTHONPATH=. python - <<'PY'
from benchmarks.kfigg.r268_cross_task_causal_transfer import run_benchmark
result = run_benchmark()
assert result['all_gates_pass'] is True
assert result['false_accepts'] == 0
assert result['trainable_parameter_count'] == 0
print(result)
PY
```

- [ ] **Step 6: Commit**

Commit message: `test: add R2.68 transfer and scratch evidence gate`

---

### Task 4: Hosted RED→GREEN gate and current-status documentation

**Files:**
- Create: `.github/workflows/r268-cross-task-causal-transfer.yml`
- Create: `R2_68_RESEARCH_STATUS.json`
- Create: `CURRENT_STATUS.md`
- Modify: `README.md`

**Interfaces:**
- Workflow runs focused R2.68 tests on Python 3.11 and 3.13 and verifies accepted-parent tests required by the final branch base.

- [ ] **Step 1: Add workflow before production code lands and record hosted RED**

Workflow must install only required dependencies, run `tests/test_r268_cross_task_causal_transfer.py`, and execute `run_benchmark()`. On the test-only commit it must fail because the R2.68 production API is absent.

- [ ] **Step 2: After implementation, require hosted GREEN on both Python versions**

Do not create a capability result file until the exact implementation commit passes.

- [ ] **Step 3: Write `R2_68_RESEARCH_STATUS.json`**

Record branch base SHA, research-only status, zero parameter delta, exact hosted run IDs, benchmark aggregate, and explicit `promotion_allowed: false` while R2.67.1 remains unsettled.

- [ ] **Step 4: Add authoritative `CURRENT_STATUS.md`**

Document that R2.67 is historical with a superseding correctness hotfix, R2.67.1 is pending, and R2.68 is an isolated research candidate with no accepted capability claim.

- [ ] **Step 5: Update README status header only**

Replace the stale top-level current-status wording with a short pointer to `CURRENT_STATUS.md`; preserve historical R2.4/R2.14 evidence rather than rewriting it as current.

- [ ] **Step 6: Commit**

Commit message: `docs: publish evidence-first Nolane AI status`

---

### Task 5: Final verification and draft PR

**Files:** no new production files unless verification exposes a defect.

- [ ] **Step 1: Run focused and parent regression gates in hosted CI**

Require R2.68 focused tests and the active parent focused tests to pass on Python 3.11 and 3.13.

- [ ] **Step 2: Verify diff contains no edits to active R2.67.1 production files**

The R2.68 branch may import parent APIs but must not silently patch #61.

- [ ] **Step 3: Open a draft PR targeting the R2.67.1 branch**

Title: `R2.68 — cross-task causal program transfer`

Body must state: research-only, +0 parameters, no AGI claim, requires exact-parent rebase after R2.67.1 acceptance, and include hosted RED/GREEN evidence.

- [ ] **Step 4: Request independent review before promotion**

Do not merge this PR as a milestone until parent acceptance, refreeze, protected-lineage verification, Nolane World adjudication, external transfer evidence, release bundle, and post-merge exact-main verification are complete.
