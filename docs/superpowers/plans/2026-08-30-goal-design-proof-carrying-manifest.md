# Goal/Design Proof-Carrying Decision Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind every admitted Goal/Design decision identity to the complete semantic input state that justified it, while preserving deterministic content addressing and backward-safe authority persistence.

**Architecture:** Extend the canonical digest boundary in `nolane/external_core/goal_design.py` rather than adding a second manifest store. Domain dataclasses remain immutable; their complete canonical state is hashed into named manifest digests, the evaluation digest binds GoalSpec + scenario set + complete option set + computed evaluation, and the receipt ID binds those manifest digests plus the exact five-plane snapshot. Existing runtime/ledger layers consume the enriched immutable `DecisionReceipt` without becoming owners of decision semantics.

**Tech Stack:** Python 3.11/3.12, frozen dataclasses, canonical JSON/SHA-256 through `stable_digest`, pytest, GitHub Actions.

**Spec:** `docs/GOAL_DESIGN_COHERENCE_PLANE.md`

## Global Constraints

- Requirements, Planning, Architecture, Integration and Context remain separate specialist authorities.
- Exact five-plane snapshot binding remains fail-closed.
- Decision receipt identity must be deterministic for identical semantic inputs.
- Semantic changes to goal, scenarios, options, proof state, uncertainty state or traceability must change the appropriate manifest digest and decision receipt identity.
- No new runtime dependency is introduced.
- Existing Goal/Design tests must remain green on Python 3.11 and 3.12.

---

### Task 1: Canonical decision input manifest

**Files:**
- Modify: `nolane/external_core/goal_design.py`
- Test: `tests/test_goal_design_decision_manifest.py`

**Interfaces:**
- Consumes: `stable_digest(value) -> str`, `GoalSpec`, `DesignScenario`, `DesignOption`, `ProofObligation`, `UncertaintyItem`, `TraceabilityState`.
- Produces: enriched `DecisionReceipt` fields `goal_digest`, `scenario_set_digest`, `option_set_digest`, `proof_state_digest`, `uncertainty_state_digest`, `traceability_digest`, `input_manifest_digest`.

- [x] **Step 1: Write the failing tests**

The committed tests require semantic receipt identity changes for goal assumptions, option dependencies, proof status/waiver state and uncertainty resolution state, while identical complete inputs remain deterministic.

- [x] **Step 2: Run tests to verify RED**

Run: `python -m pytest -q tests/test_goal_design*.py`

Expected baseline: existing tests pass while the seven new manifest tests fail because the digest fields/semantic bindings do not yet exist.

- [ ] **Step 3: Implement canonical manifest digests**

Use the existing canonicalizer, hashing complete immutable domain objects rather than only IDs:

```python
goal_digest = stable_digest({"goal": goal})
scenario_set_digest = stable_digest({"scenarios": tuple(scenarios)})
option_set_digest = stable_digest({"options": tuple(options)})
proof_state_digest = stable_digest({"proof_obligations": tuple(proof_obligations)})
uncertainty_state_digest = stable_digest({"uncertainties": tuple(uncertainties)})
traceability_digest = stable_digest({"traceability": traceability})
input_manifest_digest = stable_digest({
    "goal_digest": goal_digest,
    "scenario_set_digest": scenario_set_digest,
    "option_set_digest": option_set_digest,
    "proof_state_digest": proof_state_digest,
    "uncertainty_state_digest": uncertainty_state_digest,
    "traceability_digest": traceability_digest,
})
```

`traceability=None` is a real semantic state and is hashed as such.

- [ ] **Step 4: Bind evaluation and receipt identities**

`DesignEvaluation.digest` must include the canonical goal, scenario set and option set in addition to computed evaluation rows. `DecisionReceipt.receipt_id` must include `input_manifest_digest`, the exact snapshot/version vector, selected option and evaluation digest.

- [ ] **Step 5: Run focused tests GREEN**

Run: `python -m pytest -q tests/test_goal_design_decision_manifest.py`

Expected: all manifest tests pass.

### Task 2: Persistence and causal ledger compatibility

**Files:**
- Modify if required: `nolane/external_core/goal_design_runtime.py`
- Modify if required: `nolane/external_core/goal_design_ledger.py`
- Test: `tests/test_goal_design_authority_persistence.py`
- Test: `tests/test_goal_design_runtime.py`
- Test: `tests/test_goal_design_ledger.py`

**Interfaces:**
- Consumes: enriched immutable `DecisionReceipt`.
- Produces: restart-safe authority index and deterministic ledger events with no loss of new receipt fields.

- [ ] **Step 1: Run persistence/runtime tests after Task 1**

Run: `python -m pytest -q tests/test_goal_design_authority_persistence.py tests/test_goal_design_runtime.py tests/test_goal_design_ledger.py`

Expected: PASS. If serialization constructs `DecisionReceipt` explicitly, update it to round-trip every enriched field and keep schema validation fail-closed.

- [ ] **Step 2: Re-run focused persistence/runtime tests**

Run the same command and require zero failures.

### Task 3: Documentation and complete verification

**Files:**
- Modify: `docs/GOAL_DESIGN_COHERENCE_PLANE.md`
- Verify: `.github/workflows/goal-design-coherence-plane.yml`

**Interfaces:**
- Produces: documented proof-carrying authority identity and CI evidence on Python 3.11/3.12.

- [ ] **Step 1: Document manifest semantics**

Document that a receipt is content-addressed over complete GoalSpec, scenarios, options, proof/waiver state, uncertainty/mitigation state, traceability and exact five-plane snapshot; IDs alone are not authority evidence.

- [ ] **Step 2: Run the full Goal/Design test suite**

Run: `python -m pytest -q tests/test_goal_design*.py`

Expected: all tests pass locally/CI-equivalent.

- [ ] **Step 3: Verify GitHub Actions**

Require the dedicated Goal Design Coherence Plane workflow to complete successfully for both Python 3.11 and 3.12 on the final implementation commit.

- [ ] **Step 4: Review branch diff against `main`**

Confirm no unrelated A/B/C or other specialist-domain files are modified, no accidental authority collapse is introduced, and the PR remains mergeable.
