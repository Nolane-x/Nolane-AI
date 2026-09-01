# Goal/Design Stress-World Reversibility Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace decorative non-trivial scenario gates with quantified stress-world, tail-risk, recovery/containment, and reversibility-frontier authority while preserving historical v1/v2/v3 decision receipt identity.

**Architecture:** Add a focused `goal_design_stress.py` companion authority that deterministically evaluates evidence-bearing stress worlds and recovery profiles and emits a content-addressed `StressAdmissionToken`. The public `GoalDesignCoherencePlane` verifies that token before allowing costly/irreversible admission; `GoalDesignRuntime` mints tokens from explicit stress inputs and binds accepted decisions to a companion `DecisionStressReceipt` without changing decision receipt identity.

**Tech Stack:** Python 3.11/3.12, dataclasses, enums, deterministic `stable_digest`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-01-goal-design-stress-world-reversibility-design.md`

## Global Constraints

- Preserve historical v1/v2/v3 decision receipt identities and verifiers.
- Keep D as admission/control-plane authority; do not duplicate Family-A truth or Evaluation-family ownership.
- Reversible decisions without stress tokens must follow the historical exact path.
- Costly/irreversible decisions require exact-input stress authority.
- Every required stress world and recovery/containment profile carries evidence refs.
- Token verification re-derives all input/evidence/policy/frontier identities; stale or rebound tokens fail closed.
- Existing frozen release boundaries outside D are not modified.
- All production behavior requires RED first and hosted Goal Design acceptance on Python 3.11/3.12 before merge.

---

### Task 1: RED — Prove Decorative Scenario Tags Are Insufficient

**Files:**
- Create: `tests/test_goal_design_stress_world_authority.py`

**Interfaces:**
- Consumes existing `GoalDesignCoherencePlane`, `DesignScenario`, `DesignOption`, `DecisionClass`.
- Produces executable requirements for `StressWorldEvidence`, `RecoveryProfile`, `StressPolicy`, `GoalDesignStressAuthority`, and `StressAdmissionToken`.

- [ ] **Step 1: Add a direct-plane RED test**

```python
def test_costly_decision_cannot_cross_gate_with_decorative_adversarial_tag_only():
    with pytest.raises(CoherenceError, match="stress"):
        plane.admit_decision(
            goal=goal,
            scenarios=(base, DesignScenario("break", tags=("adversarial",))),
            options=(costly_with_rollback, reversible_alternative),
            selected_option_id=costly_with_rollback.option_id,
            snapshot=snapshot,
            current_vector=vector,
        )
```

Expected production change: the public plane requires a verified stress token for non-trivial decisions.

- [ ] **Step 2: Add an irreversible coverage RED test**

```python
def test_irreversible_token_requires_challenge_and_tail_failure_worlds():
    token = stress.authorize(
        goal=goal,
        scenarios=scenarios,
        options=options,
        selected_option_id="irreversible",
        worlds=(adversarial_world,),
        recovery_profiles=(containment_profile,),
    )
    assert token.authorized is False
    assert any("tail" in blocker.lower() or "failure" in blocker.lower() for blocker in token.blockers)
```

Expected production change: irreversible coverage requires both challenge and tail/failure classes.

- [ ] **Step 3: Push test-only commit and verify hosted RED**

Run through Goal Design Coherence Plane. Expected failure is missing stress authority / non-trivial decision accepted without quantified token; collection errors caused by typos do not count as RED.

### Task 2: Quantified Stress Authority Core

**Files:**
- Create: `nolane/external_core/goal_design_stress.py`
- Test: `tests/test_goal_design_stress_world_authority.py`

**Interfaces:**
- Produces:
  - `StressWorldKind`
  - `StressWorldEvidence`
  - `RecoveryProfile`
  - `StressPolicy`
  - `StressAdmissionToken`
  - `DecisionStressReceipt`
  - `GoalDesignStressAuthority.authorize()`
  - `GoalDesignStressAuthority.verify_token()`
  - `GoalDesignStressAuthority.bind_decision()`

- [ ] **Step 1: Implement canonical evidence objects**

`StressWorldEvidence` validates known kind, bounded plausibility/severity, non-empty evidence refs, canonical refs and content digest. `RecoveryProfile` validates bounded recovery metrics, non-empty evidence, exact option identity and content digest.

- [ ] **Step 2: Implement policy digest and world exposure**

```python
exposure = world.plausibility * world.severity * (1.0 - selected_utility)
```

Costly defaults: max exposure `0.60`, recovery score `>=0.12`, residual harm `<=0.50`.
Irreversible defaults: max exposure `0.45`, recovery/containment score `>=0.08`, residual harm `<=0.35`.

- [ ] **Step 3: Enforce evidence coverage**

Costly requires `ADVERSARIAL` or `COUNTERFACTUAL`. Irreversible requires challenge plus independent `TAIL` or `FAILURE`. World scenario refs must exist in the supplied scenario set.

- [ ] **Step 4: Enforce rollback/containment semantics**

Costly profile `rollback_ref` must equal selected option `rollback_ref`. Irreversible selected option must have a non-empty `containment_ref` in its profile.

- [ ] **Step 5: Run focused tests GREEN**

Run: `python -m pytest -q tests/test_goal_design_stress_world_authority.py`
Expected: all Task-2 stress evidence/risk tests pass.

### Task 3: Reversibility Frontier

**Files:**
- Modify: `nolane/external_core/goal_design_stress.py`
- Modify: `tests/test_goal_design_stress_world_authority.py`

**Interfaces:**
- Consumes existing Goal/Design robust evaluation.
- Produces `frontier_option_ids` and domination blockers in `StressAdmissionToken`.

- [ ] **Step 1: Add RED for dominated non-trivial selection**

```python
def test_selected_option_blocked_when_alternative_is_more_robust_and_more_reversible():
    token = stress.authorize(...)
    assert token.authorized is False
    assert "reversibility frontier" in " ".join(token.blockers).lower()
```

- [ ] **Step 2: Compute per-option reversibility score**

Use detailed `RecoveryProfile.recovery_score` where present, otherwise existing class optionality (`REVERSIBLE=1`, `COSTLY_REVERSIBLE=.5`, `IRREVERSIBLE=0`).

- [ ] **Step 3: Compute two-axis Pareto frontier**

An option dominates another when it is weakly better in both robust score and reversibility score and strictly better in at least one. Selected non-trivial option outside the frontier is a blocker.

- [ ] **Step 4: Verify justified tradeoff remains admissible**

A less reversible selected option remains on the frontier when it has a genuinely higher robust score; the gate must not mechanically force maximal reversibility.

### Task 4: Content-Addressed Admission Token and Replay Defense

**Files:**
- Modify: `nolane/external_core/goal_design_stress.py`
- Modify: `tests/test_goal_design_stress_world_authority.py`

**Interfaces:**
- Produces token binding exact goal/scenario/options/selection/policy/world/profile state.

- [ ] **Step 1: Add RED token replay tests**

A token minted for option A must fail for option B. A changed scenario utility, world severity, evidence ref, policy threshold, or option rollback ref must make the old token stale.

- [ ] **Step 2: Implement exact input digests**

Canonicalize scenario/options by id; bind raw goal digest, canonical scenario-set digest, canonical option-set digest, selected option/class, policy digest, world/profile digests, assessment results and blockers.

- [ ] **Step 3: Implement `verify_token()` by full re-derivation**

Do not merely compare caller-provided digest fields. Re-run `authorize()` from the supplied decision inputs and require exact token equality.

- [ ] **Step 4: Implement companion decision binding**

`bind_decision(token, decision_receipt_id)` returns a content-addressed `DecisionStressReceipt` over receipt id + exact token id/digest.

### Task 5: Public Coherence-Plane Gate

**Files:**
- Modify: `nolane/external_core/goal_design.py`
- Modify: `tests/test_goal_design_coherence_plane.py`
- Modify: `tests/test_goal_design_stress_world_authority.py`

**Interfaces:**
- `GoalDesignCoherencePlane.admit_decision(..., stress_token: StressAdmissionToken | None = None)`.

- [ ] **Step 1: Preserve reversible compatibility path**

With a reversible selected option and no token, invoke the exact historical path and preserve receipt digest/id.

- [ ] **Step 2: Require and verify stress token before base admission for non-trivial selections**

Missing/unauthorized/stale/mismatched token raises `CoherenceError` with `stress` authority reason before `super().admit_decision()`.

- [ ] **Step 3: Upgrade existing costly/irreversible tests**

Tests targeting earlier blockers (rollback, uncertainty, counterfactual) must continue to reach those specific blockers. Where a test expects successful non-trivial admission, mint valid stress authority explicitly rather than adding a bypass flag.

- [ ] **Step 4: Verify historical receipt identity tests remain unchanged**

Run the existing authenticity/receipt suites and confirm v1/v2/v3 ids are byte-identical.

### Task 6: Runtime Integration and Audit Linkage

**Files:**
- Modify: `nolane/external_core/goal_design_runtime.py`
- Modify: `tests/test_goal_design_stress_world_authority.py`
- Modify if required: `tests/test_goal_design_sensitivity_reopening.py`

**Interfaces:**
- `GoalDesignRuntime.__init__(..., stress: GoalDesignStressAuthority | None = None)`
- `GoalDesignRuntime.admit(..., stress_worlds=(), recovery_profiles=(), stress_policy=None)`
- `GoalDesignRuntime.stress_receipt(receipt_id)`

- [ ] **Step 1: Mint token before non-trivial runtime admission**

Runtime calls `self.stress.authorize()` with the exact admission inputs and configured policy.

- [ ] **Step 2: Pass token through the coherence plane**

The same token is verified by the plane; runtime cannot bypass public admission authority.

- [ ] **Step 3: Bind accepted decision to companion receipt**

After decision receipt mint, call `bind_decision()` and store by decision receipt id. Reversible decisions without explicit stress inputs do not create companion receipts.

- [ ] **Step 4: Verify stress receipt lookup and tamper resistance**

A stored companion receipt must bind exactly one decision receipt and one exact token.

### Task 7: Adversarial Hardening

**Files:**
- Create: `tests/test_goal_design_stress_world_adversarial.py`
- Modify if required: `nolane/external_core/goal_design_stress.py`

**Interfaces:**
- Stress authority fail-closed invariants.

- [ ] **Step 1: Reject duplicate/unknown world and option identities**
- [ ] **Step 2: Reject NaN/infinite/out-of-range plausibility, severity and recovery metrics**
- [ ] **Step 3: Reject empty evidence and rollback/profile rebinding**
- [ ] **Step 4: Reject one-world coverage laundering and token input replay**
- [ ] **Step 5: Verify canonical ordering is identity-noise free**

### Task 8: Hosted Acceptance, Race Guard, Merge, Production Closure

**Files:**
- No unrelated production changes.

**Interfaces:**
- Produces exact-hosted evidence and safely integrated `main`.

- [ ] **Step 1: Run `python -m pytest -q tests/test_goal_design*.py` on Python 3.11 and 3.12**
- [ ] **Step 2: Require Refoundation Epoch 0 success on its configured Python matrix**
- [ ] **Step 3: Require R1.9 and R2.0i integrity success**
- [ ] **Step 4: Race-guard latest `main` immediately before merge**
- [ ] **Step 5: If main moved without D overlap, rebuild exact union preserving concurrent specialist blobs byte-for-byte and rerun acceptance**
- [ ] **Step 6: Merge only with expected-head protection**
- [ ] **Step 7: Verify actual-main Goal Design/R1.9/R2.0i push gates before declaring CLOSED/GREEN**

## Self-review

- Spec coverage: quantified stress, tail/failure coverage, recovery/containment, reversibility frontier, exact-input token, public-plane enforcement, runtime audit linkage, compatibility and hosted closure are all mapped to tasks.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: task interfaces use the exact names defined in Tasks 2–6.
- Scope: all changes remain within D Goal/Design plus D tests/docs; no Evaluation, Family-A, E, or F production ownership is modified.