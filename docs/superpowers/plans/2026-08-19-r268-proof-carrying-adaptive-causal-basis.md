# R2.68 Proof-Carrying Adaptive Causal Basis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an adaptive, proof-carrying causal-basis solver that discovers a sufficient intervention basis of cardinality 1–4 without treating bounded search failure as proof of necessity.

**Architecture:** Add a new isolated R2.68 module over corrected R2.67.1 primitives. The module separates proposal search from necessity proof, binds collision certificates to exact subset exposure, searches basis cardinality in increasing order, validates learned probe semantics on disjoint evidence, and terminally re-observes selected interventions before acceptance. Existing R2.67.1 production code remains untouched.

**Tech Stack:** Python 3.11/3.13, pytest, existing Nolane `cogcoder` DSL/intervention primitives, GitHub Actions hosted verification.

**Spec:** `docs/superpowers/specs/2026-08-19-r268-proof-carrying-adaptive-causal-basis-design.md`

## Global Constraints

- Parent semantics must be corrected R2.67.1; historical R2.67 authority bugs are not inherited as truth.
- `trainable_parameter_count == 0`.
- No production code before a hosted RED test is observed.
- Search miss or budget exhaustion is never an impossibility certificate.
- Necessity certificates bind to exact subset semantic IDs, exact subset-specific exposed fields, evidence digest, proof kind, and witness digest.
- Each subset recomputes free fields; no monotone collision pruning across different exposure schemas.
- Every reported case counter counts actual attempts, never planned denominators.
- R2.68 must not modify `cogcoder/r267_three_probe_causal_composition.py`.
- Final promotion requires external I/O-only evidence and corrected R2.67.1 accepted ancestry; implementation may remain draft until that parent is accepted.

---

### Task 1: Freeze the R2.68 behavioral contract as hosted RED

**Files:**
- Create: `tests/test_r268_adaptive_causal_basis.py`
- Create: `tests/test_r268_proof_authority.py`
- Create: `.github/workflows/r268-red-green.yml`

**Interfaces:**
- Consumes existing `OperatorInventionNeed` and the intended new API `synthesize_adaptive_causal_basis(...)`.
- Produces executable RED contracts for later tasks.

- [ ] **Step 1: Write a mixed-cardinality RED contract**

Create fixtures with deterministic public contexts and oracles for certified minimal basis sizes 1, 2, 3 and 4. Each test calls `synthesize_adaptive_causal_basis(..., max_basis_size=4)` and asserts `receipt.passed`, `receipt.selected_basis_size`, `receipt.globally_minimal`, `receipt.false_accepts == 0`, and exact terminal counters.

- [ ] **Step 2: Write authority RED contracts**

Tests must assert:

```python
assert verify_necessity_certificate(cert, examples) is True
assert cert.exposed_fields == expected_fields
```

and must include a forged/reused certificate whose subset free-field exposure differs; verification must return `False`.

Add a synthetic monkeypatch case where lower-order search returns a non-budget miss on collision-free evidence; expected receipt is not globally minimal and reason contains `minimality_inconclusive`.

- [ ] **Step 3: Add a hosted RED workflow**

Workflow runs accepted-parent focused tests first, then `tests/test_r268_*.py` on Python 3.11 and 3.13. Before production exists, it must require the R2.68 tests to fail because `cogcoder.r268_adaptive_causal_basis` is absent.

- [ ] **Step 4: Open a draft PR against the active corrected-parent branch and observe RED**

Do not add production implementation until GitHub Actions records the intended import/feature failure.

---

### Task 2: Implement proof certificates and generic semantic helpers

**Files:**
- Create: `cogcoder/r268_adaptive_causal_basis.py`
- Test: `tests/test_r268_proof_authority.py`

**Interfaces:**
- Produces `NecessityCertificate`, `verify_necessity_certificate`, `_canonical_evidence_digest`, `_collision_certificate`, and subset-exposure helpers.

- [ ] **Step 1: Implement immutable `NecessityCertificate`**

Fields:

```python
basis_semantic_profile_ids: tuple[str, ...]
subset_semantic_profile_ids: tuple[str, ...]
subset_cardinality: int
exposed_fields: tuple[str, ...]
evidence_digest: str
proof_kind: str
witness_digest: str
witness_rows: tuple[int, int]
```

- [ ] **Step 2: Implement canonical evidence hashing**

Serialize normalized exposed context values plus normalized target values with sorted JSON and `allow_nan=False`; hash with SHA-256.

- [ ] **Step 3: Implement public collision certificate construction**

For exact subset examples, find two rows with identical complete exposed evidence vector and distinct normalized targets. Return a certificate bound to exact profile IDs/exposed fields/evidence digest; otherwise return `None`.

- [ ] **Step 4: Implement independent certificate verification**

Recompute evidence digest, verify witness indices are in range, verify exact exposed vector collision and target disagreement, and reject any mismatch in subset cardinality or exposed fields.

- [ ] **Step 5: Run proof-authority tests GREEN**

---

### Task 3: Implement variable-arity expression proposal search

**Files:**
- Modify: `cogcoder/r268_adaptive_causal_basis.py`
- Test: `tests/test_r268_adaptive_causal_basis.py`

**Interfaces:**
- Produces `_ExpressionSearchReceipt` and `_synthesize_variable_basis_expression(field_names, required_probe_fields, constants, examples, max_depth, max_candidates)`.

- [ ] **Step 1: Add a failing focused test for required-probe structural use**

A target solvable by raw free fields alone must not be accepted as a `k`-basis if the candidate expression omits one of the required `__pN` fields.

- [ ] **Step 2: Implement deterministic semantic beam search**

Start from fields/constants, expand trusted unary/binary operators, dedupe by output semantic vector plus used-required-probe set, rank by required-probe coverage then cost/depth/digest, and accept only expressions using every required probe.

- [ ] **Step 3: Preserve explicit incompleteness**

Return `variable_basis_budget_exhausted` on candidate cap and `variable_basis_no_expression` otherwise. Neither reason has proof authority.

- [ ] **Step 4: Run focused search tests GREEN**

---

### Task 4: Implement adaptive basis discovery with fair cardinality scheduling

**Files:**
- Modify: `cogcoder/r268_adaptive_causal_basis.py`
- Test: `tests/test_r268_adaptive_causal_basis.py`

**Interfaces:**
- Produces `AdaptiveCausalBasisCandidate`, `AdaptiveCausalBasisStructureReceipt`, `discover_adaptive_causal_basis(...)`.

- [ ] **Step 1: Profile interventions once with exact oracle ledger**

Enumerate legal interventions, run discovery/validation applications, fail globally on oracle/non-finite errors, reject degenerate profiles, and dedupe by semantic behavior.

- [ ] **Step 2: Enumerate basis sizes from 1 through `max_basis_size`**

Within each cardinality, sort bases by semantic profile IDs, not positional intervention IDs. Allocate global search budget using deterministic fair-share scheduling across remaining bases.

- [ ] **Step 3: Recompute subset-specific free fields for every basis/subset**

For a subset, only fields fixed by interventions in that exact subset are hidden. Build composition examples from the subset probe outputs plus the resulting free canonical fields.

- [ ] **Step 4: Build lower-order proof ledger**

For every proper non-empty subset required to support an irreducibility claim, attempt a collision certificate first. If a lower-order sufficient expression exists, reject higher-order minimality. If no collision exists and search does not find a solution, record inconclusive; never certify necessity from search failure.

- [ ] **Step 5: Separate sufficiency from minimality**

A candidate can be structurally sufficient with `globally_minimal=False`. Only set global minimality when every legal lower-cardinality basis has a conclusive status.

- [ ] **Step 6: Run 1/2/3/4 and no-collision-inconclusive tests GREEN**

---

### Task 5: Implement probe learning, terminal re-observation, and exact attempted-case accounting

**Files:**
- Modify: `cogcoder/r268_adaptive_causal_basis.py`
- Test: `tests/test_r268_adaptive_causal_basis.py`
- Create: `tests/test_r268_receipt_accounting.py`

**Interfaces:**
- Produces `AdaptiveCausalBasisReceipt`, `synthesize_adaptive_causal_basis(...)`.

- [ ] **Step 1: Learn one probe expression per selected intervention**

Project only fields not fixed by that intervention. Count validation attempts incrementally; return partial counts on midstream failure.

- [ ] **Step 2: Compose learned probe expressions into the selected basis expression**

Rewrite `__pN` fields to learned probe expressions and externalize from canonical schema.

- [ ] **Step 3: Enforce validation/evidence disjointness**

Terminal contexts and selected-intervention terminal contexts must be semantically disjoint from all learning oracle inputs. Duplicate numeric aliases must canonicalize to the same semantic identity.

- [ ] **Step 4: Terminally re-observe exact selected interventions**

For each terminal context, invoke the terminal oracle on each selected intervention before final base evaluation. Increment counters before each attempted oracle call so errors report actual attempt counts.

- [ ] **Step 5: Add failure-path tests**

Cover second-probe synthesis failure, first terminal-probe oracle error, final terminal oracle error, non-finite output, and probe-expression mismatch. Every pre-final failure reports `final_validation_cases == 0`; no planned denominator is reported.

- [ ] **Step 6: Run all R2.68 receipt/accounting tests GREEN**

---

### Task 6: Add mixed-cardinality authored Phase-A benchmark

**Files:**
- Create: `benchmarks/kfigg/r268_adaptive_causal_basis.py`
- Create: `tests/test_r268_benchmark.py`

**Interfaces:**
- Produces deterministic `run_benchmark() -> dict[str, object]`.

- [ ] **Step 1: Define four structurally distinct authored families**

One each for minimal certified basis sizes 1, 2, 3, and 4. Each family uses separate discovery, validation and terminal rows and provides public collision witnesses for every lower-order claim actually certified.

- [ ] **Step 2: Add permutation/renaming replay**

Run semantic-equivalent tasks with field permutation and intervention-identity changes; require same selected cardinality and equivalent program behavior.

- [ ] **Step 3: Add tight-budget order-invariance replay**

Reorder semantically identical intervention candidates and require identical solve/abstain outcome under the same global budget.

- [ ] **Step 4: Add authority controls**

Include a no-collision forced-search-miss case that must remain minimality-inconclusive and a misspecified/outside-grammar control that must fail closed.

- [ ] **Step 5: Require exact aggregate gates**

`all_gates_pass`, `false_accepts == 0`, `trainable_parameter_count == 0`, mixed selected basis sizes `{1,2,3,4}`, deterministic replay, and exact oracle ledger decomposition.

---

### Task 7: Hosted regression and independent authority verification

**Files:**
- Modify: `.github/workflows/r268-red-green.yml`
- Create: `.github/workflows/r268-canonical-gate.yml`
- Create: `archive/root-history/historical_r_series/R2_68_PRE_HOSTED_LOCK.json` only after source/protocol freeze
- Create: `archive/root-history/historical_r_series/R2_68_PHASE_A_RESULT.json` only from hosted recomputation

**Interfaces:**
- Produces hosted evidence, not new runtime semantics.

- [ ] **Step 1: Run R2.68 tests on Python 3.11 and 3.13**

- [ ] **Step 2: Run corrected R2.67.1 and accepted R2.66 protected regressions**

- [ ] **Step 3: Add independent challenger contracts**

At minimum attack forged certificate reuse, no-collision search miss, tight-budget order dependence, and failure-path receipt accounting.

- [ ] **Step 4: Freeze exact source blobs only after all blockers are GREEN**

Lock parent commit, source/test/benchmark blobs, proof-authority invariants, parameter count, and production-source immutability.

- [ ] **Step 5: Recompute authored evidence from frozen source and compare byte-for-byte**

---

### Task 8: External I/O-only transfer and release authority

**Files:**
- Create: `research/r268_external_transfer.py`
- Create: `tests/test_r268_external_transfer.py`
- Create: `archive/root-history/historical_r_series/R2_68_EXTERNAL_TRANSFER.json`
- Create: `.github/workflows/r268-external-transfer.yml`
- Create: `R2_68_DELIVERY.md`

**Interfaces:**
- Produces independent external evidence required for accepted capability promotion.

- [ ] **Step 1: Freeze a structurally distinct external callable/version before measurement**

Reject candidates isomorphic to authored formulas.

- [ ] **Step 2: Exercise source through callable I/O only**

No source-code or implementation introspection is allowed by the transfer harness.

- [ ] **Step 3: Require challenge/heldout exactness, proof-authority integrity, zero false accepts, and exact end-to-end oracle accounting**

- [ ] **Step 4: Run canonical full lineage, record Nolane World adjudication without forcing W5, and only then mark the bounded capability accepted**

- [ ] **Step 5: Do not claim AGI or automatic readiness increase from the milestone alone**
