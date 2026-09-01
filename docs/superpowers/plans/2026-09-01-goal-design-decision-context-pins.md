# Goal/Design Decision Context Pins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a proof-carrying decision context compiler that pins exact Goal/Design semantics and provenance without rewriting historical decision authority.

**Architecture:** Create a focused `goal_design_context.py` companion module. It re-derives exact decision input digests, generates typed content-addressed pins, and is exposed through `GoalIntegrityRuntime`, which supplies the current active integrity/decision authority boundary. The generic organization/memory `ContextCompiler` remains unchanged in this wave.

**Tech Stack:** Python 3.11/3.12, frozen dataclasses, enums, deterministic `stable_digest`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-01-goal-design-decision-context-pins-design.md`

## Global Constraints

- Preserve historical v1/v2/v3 `DecisionReceipt` identity exactly.
- Protected semantic pins originate only from active Goal Integrity authority.
- Context compiler is not Family-A truth authority and performs no free-text inference.
- Goal/scenario/option/evaluation/proof/uncertainty state must be re-derived from concrete inputs before pin construction.
- Context policy is configured on the compiler/runtime instance; no per-call override.
- No generic `ContextCapsule` mutation in this wave.
- Production code only follows a hosted behavioral RED.
- Final acceptance requires Goal Design Python 3.11/3.12, Refoundation Python 3.11/3.13, R1.9, R2.0i, race guard, expected-head merge, and actual-main verification.

---

### Task 1: Hosted RED — Runtime Has No Semantic Decision Context Authority

**Files:**
- Create: `tests/test_goal_design_decision_context.py`

**Interfaces:**
- Consumes existing `GoalIntegrityRuntime`, `GoalIntegrityContract`, `GoalIntegrityAttestation`, `GoalSpec`, `DesignScenario`, `DesignOption`, `ProofObligation`, `UncertaintyItem`.
- Produces the required public runtime seam `GoalIntegrityRuntime.compile_decision_context(...)`.

- [ ] **Step 1: Build one valid integrity-backed reversible decision fixture**

Use the same five-plane runtime construction pattern as `tests/test_goal_design_runtime.py`. Install a contract containing terminal goal, hard constraint, anti-goal, and success criterion clauses; create one attestation per Goal/Design plane preserving every required clause; admit a reversible champion against two options, one open non-blocking proof, and one unresolved high-risk uncertainty.

- [ ] **Step 2: Write the behavioral failing test**

```python
def test_integrity_runtime_compiles_exact_semantic_decision_context():
    runtime, admission, goal, scenarios, options, proofs, uncertainties = _admitted_runtime()
    context = runtime.compile_decision_context(
        receipt_id=admission.decision_receipt.receipt_id,
        goal=goal,
        scenarios=scenarios,
        options=options,
        proof_obligations=proofs,
        uncertainties=uncertainties,
    )
    kinds = {pin.kind.value for pin in context.pins}
    assert {"terminal_goal", "hard_constraint", "anti_goal", "champion", "rival", "open_proof", "critical_unknown"} <= kinds
    assert context.decision_receipt_id == admission.decision_receipt.receipt_id
```

- [ ] **Step 3: Push test-only commit and run hosted Goal Design workflow**

Expected RED: `AttributeError: 'GoalIntegrityRuntime' object has no attribute 'compile_decision_context'` after the fixture successfully admits the decision. Collection/import failures do not count.

---

### Task 2: Context Artifact and Exact-Input Compiler

**Files:**
- Create: `nolane/external_core/goal_design_context.py`
- Modify: `tests/test_goal_design_decision_context.py`

**Interfaces:**
- Produces `DecisionContextPinKind`, `DecisionContextTrust`, `DecisionContextPolicy`, `DecisionContextPin`, `DecisionContextContradiction`, `GoalDesignDecisionContext`, `GoalDesignDecisionContextCompiler`.

- [ ] **Step 1: Add immutable content-addressed value types**

Implement canonical text/reference normalization, bounded salience, policy digest, contradiction digest, and derived pin/context IDs. No public API accepts arbitrary `DecisionContextPin` values for compilation.

- [ ] **Step 2: Add exact receipt input re-derivation**

`GoalDesignDecisionContextCompiler.compile(...)` accepts:

```python
def compile(
    self,
    *,
    decision_receipt: DecisionReceipt,
    integrity_contract: GoalIntegrityContract,
    integrity_receipt: GoalIntegrityReceipt,
    goal: GoalSpec,
    scenarios: Sequence[DesignScenario],
    options: Sequence[DesignOption],
    proof_obligations: Sequence[ProofObligation] = (),
    uncertainties: Sequence[UncertaintyItem] = (),
    contradictions: Sequence[DecisionContextContradiction] = (),
) -> GoalDesignDecisionContext:
    ...
```

Verify `DecisionReceipt` authenticity and `GoalIntegrityReceipt` binding first. Recompute goal/scenario/option/evaluation/proof/uncertainty digests using the exact historical projection rules from `goal_design.py`; reject any mismatch before pins are generated.

- [ ] **Step 3: Derive protected integrity pins**

Map all five `GoalIntegrityClauseKind` values one-to-one to protected pin kinds. Use `integrity_receipt.receipt_id` as `authority_ref`, contract digest as `authority_digest`, and clause provenance as `provenance_refs`.

- [ ] **Step 4: Derive champion/rival pins**

The selected option produces exactly one `CHAMPION`; every other exact option produces a `RIVAL`. Their authority is the decision receipt/evaluation digest. Option evidence refs remain attached.

- [ ] **Step 5: Derive proof and uncertainty pins**

Every `ProofStatus.OPEN` proof becomes `OPEN_PROOF`, preserving its `blocking` bit. Every unresolved uncertainty with risk at or above compiler policy threshold becomes `CRITICAL_UNKNOWN` with bounded risk salience.

- [ ] **Step 6: Derive explicit contradiction pins**

Require same-goal contradiction evidence with non-empty evidence/provenance. Emit only `CONTRADICTION` + `EVIDENCE_ASSERTION`; contradiction input cannot manufacture a protected semantic kind.

- [ ] **Step 7: Run focused tests GREEN**

Run `python -m pytest -q tests/test_goal_design_decision_context.py`.

---

### Task 3: Runtime Authority Seam

**Files:**
- Modify: `nolane/external_core/goal_design_integrity_runtime.py`
- Modify: `tests/test_goal_design_decision_context.py`

**Interfaces:**
- Produces `GoalIntegrityRuntime.compile_decision_context(...)` and constructor-owned `decision_context_compiler` / `decision_context_policy` configuration.

- [ ] **Step 1: Configure one compiler per runtime**

Extend public `GoalIntegrityRuntime.__init__` with optional `decision_context_compiler` and `decision_context_policy`. Reject simultaneous incompatible compiler+policy configuration. If no compiler is supplied, instantiate `GoalDesignDecisionContextCompiler(policy=decision_context_policy)` once.

- [ ] **Step 2: Enforce active authority before compilation**

`compile_decision_context(...)` must:

1. get `self.decisions.get(receipt_id)` and require lifecycle `ACTIVE`;
2. get `self.integrity_authority.get(receipt_id)` and require lifecycle `ACTIVE`;
3. require exact decision receipt equality between both records;
4. resolve `current_integrity_contract(goal_id)` and require its digest to equal the integrity receipt contract digest;
5. delegate to the configured compiler.

Raise `CoherenceError` for missing/stale/superseded authority or compiler validation failure.

- [ ] **Step 3: Prove contract supersession invalidates context compilation**

Admit under contract A, supersede to contract B through the existing evolution path used by integrity tests, then prove old receipt context compilation fails before pin generation.

- [ ] **Step 4: Run focused runtime tests GREEN**

Run `python -m pytest -q tests/test_goal_design_decision_context.py tests/test_goal_design_integrity_runtime*.py`.

---

### Task 4: Adversarial Identity and Specification-Gaming Tests

**Files:**
- Modify: `tests/test_goal_design_decision_context.py`

**Interfaces:**
- Validates exact context identity and fail-closed semantics.

- [ ] **Step 1: Option omission/substitution attack**

Compile with one admitted rival removed or mutated. Expected: `CoherenceError` / `ValueError` naming option-set or evaluation mismatch.

- [ ] **Step 2: Proof-state substitution attack**

Change claim/status/evidence of a receipt-bound proof while keeping its ID. Expected: proof-state digest mismatch.

- [ ] **Step 3: Uncertainty-state substitution attack**

Change impact/resolution/mitigation while keeping uncertainty ID. Expected: uncertainty-state digest mismatch.

- [ ] **Step 4: Foreign contradiction attack**

Pass a contradiction with another goal ID. Expected: fail closed.

- [ ] **Step 5: Determinism under reordering**

Compile semantically identical scenario/option/proof/uncertainty/contradiction inputs in different order. Expected: identical context and pin identities.

- [ ] **Step 6: Context policy authority attack**

Configure runtime with a strict threshold and prove there is no per-call parameter capable of weakening it. A caller-created permissive `DecisionContextPolicy` is effective only when it configured the runtime/compiler instance.

- [ ] **Step 7: v2/v3 compatibility**

Prove an empty-assumption decision re-derives base-schema digests exactly. Prove a truth-bound v3 decision uses full goal/option assumption identity and compiles only against the bound truth-capable inputs.

---

### Task 5: Acceptance, Race Integration, and Production Closure

**Files:**
- Modify documentation only if implementation semantics differ from spec/plan.

**Interfaces:**
- Produces merged production authority and hosted evidence.

- [ ] **Step 1: Run full Goal Design acceptance**

Hosted workflow: `python -m pytest -q tests/test_goal_design*.py` on Python 3.11 and 3.12. Both must pass.

- [ ] **Step 2: Run Refoundation Epoch 0**

Require Python 3.11 and 3.13 success across compile, dossier freshness, quarantine audit, Refoundation contracts, Truth Knowledge A, zero-loss evidence, organization/campaign/execution regressions, and frozen Neural R2.3 metadata.

- [ ] **Step 3: Require R1.9 and R2.0i SUCCESS**

Do not repair unrelated frozen historical release locks from D.

- [ ] **Step 4: Race guard latest `main`**

Compare the branch base/head against current `main`. If concurrent specialists advanced main without D overlap, rebuild an exact union onto current main and rerun acceptance. If overlap exists, inspect semantics and preserve the concurrent specialist changes rather than overwriting them.

- [ ] **Step 5: Expected-head protected merge**

Merge only the fully accepted head SHA.

- [ ] **Step 6: Actual-main verification**

On the real merge commit require Goal Design 3.11/3.12 plus R1.9/R2.0i success. Only then label **Decision Context Pins / Context Compiler CLOSED/GREEN**.
