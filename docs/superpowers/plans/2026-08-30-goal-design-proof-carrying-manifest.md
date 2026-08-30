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

Observed RED: seven manifest tests failed while 32 existing Goal/Design tests remained green.

- [x] **Step 3: Implement canonical manifest digests**

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

`traceability=None` is a real semantic state and is hashed as such. The implemented manifest additionally binds the selected option and exact snapshot/version vector so authority closure cannot be replayed against different five-plane state.

- [x] **Step 4: Bind evaluation and receipt identities**

`DesignEvaluation.digest` includes the canonical goal, scenario set and option set in addition to computed evaluation rows. `DecisionReceipt.receipt_id` includes `input_manifest_digest`, the exact snapshot/version vector, selected option and evaluation digest.

- [x] **Step 5: Run focused tests GREEN**

Run: `python -m pytest -q tests/test_goal_design_decision_manifest.py`

Observed GREEN as part of the final Goal/Design suite.

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

- [x] **Step 1: Run persistence/runtime tests after Task 1**

Run: `python -m pytest -q tests/test_goal_design_authority_persistence.py tests/test_goal_design_runtime.py tests/test_goal_design_ledger.py`

Observed boundary failure: the new receipt digests were lost during `DecisionAuthorityIndex` restore while the remaining tests passed.

- [x] **Step 2: Re-run focused persistence/runtime tests**

Serialization/deserialization now round-trips every proof-carrying digest with backward-compatible defaults for legacy state. A second RED→GREEN audit test also required typed DECISION ledger events to bind `input_manifest_digest` directly.

### Task 3: Documentation and complete verification

**Files:**
- Modify: `docs/GOAL_DESIGN_COHERENCE_PLANE.md`
- Verify: `.github/workflows/goal-design-coherence-plane.yml`

**Interfaces:**
- Produces: documented proof-carrying authority identity and CI evidence on Python 3.11/3.12.

- [x] **Step 1: Document manifest semantics**

The architecture spec documents that a receipt is content-addressed over complete GoalSpec, scenarios, options, proof/waiver state, uncertainty/mitigation state, traceability and exact five-plane snapshot; IDs alone are not authority evidence.

- [x] **Step 2: Run the full Goal/Design test suite**

Run: `python -m pytest -q tests/test_goal_design*.py`

Exact implementation head `01761ed8d96918d1f23dd5fb099ddd2073aa4964` produced 41/41 passes on both Python 3.11 and 3.12.

- [x] **Step 3: Verify GitHub Actions**

Dedicated Goal Design Coherence Plane run `33306747928` completed with 41/41 passes on Python 3.11 and 41/41 passes on Python 3.12 for the exact implementation head. Final merged-baseline interop verification is tracked by the branch-closing gate below.

- [x] **Step 4: Review branch diff against `main`**

After integrating current `main` (`a38bd47daef1d28e16d9487c3db9355301e6113e`) into the feature branch, `main...feat/goal-design-coherence-plane-gpt56sol` is ahead-only and the diff remains scoped to Goal/Design implementation, tests, documentation and its dedicated workflow. No A/B/C specialist authority file is modified by the D delta.

## Branch-closing merged-baseline gate

- [x] Current `main` was integrated into the feature branch through merge commit `8ac794b00daf5a9b8ef8db63ae69c27c72961aee`, whose first parent is the verified D implementation head and second parent is Refoundation A main.
- [x] The merge tree is exactly the synthetic merge tree GitHub previously computed for PR #239, preserving both A and D authority work without conflict.
- [x] A dedicated `test_goal_design_refoundation_interop.py` contract is used as a cross-refoundation gate: Truth/Knowledge content identity must flow into Goal/Design receipt evidence and must change D authority identity when the upstream truth content digest changes.
- [ ] Final combined A+D head passes all `tests/test_goal_design*.py` on Python 3.11 and 3.12.
- [ ] PR #239 final diff is rechecked against current `main`, remains mergeable, and contains no unrelated specialist-domain delta.
