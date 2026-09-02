# C11 Counterfactual Policy Qualification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add counterfactual, scope-bound qualification evidence for externally adopted metareasoning policies without granting Reasoning/Invention deployment or self-promotion authority.

**Architecture:** C11 is an additive immutable protocol layered after C10. It binds parent/candidate policy outcomes to exact matched contexts, derives per-trial effect vectors, qualifies only non-regressing evidence across an exact regime, and emits explicit applicability/abstention receipts.

**Tech Stack:** Python 3.11/3.13, dataclasses, enums, canonical content digests, pytest, GitHub Actions Refoundation matrix.

**Spec:** `docs/superpowers/specs/2026-09-01-reasoning-policy-qualification-design.md`

## Global Constraints

- Target component version is `external.reasoning_invention == 0.0.5`, canonical revision `5`.
- Existing C1–C10 schemas remain unchanged.
- New schema is `reasoning-policy-qualification-v1`.
- C11 has evidence/qualification authority only; it cannot route/deploy policies or mutate D/E/Memory/Truth/Cognitive Library/Assurance/Neural state.
- No hidden scalar utility or average may erase a tail regression.
- Out-of-scope applicability fails closed as `ABSTAIN_OUT_OF_SCOPE`.
- No force-push/rebase; resync concurrent `main` through history-preserving integration.

---

### Task 1: Specify C11 behavior and adversarial contracts

**Files:**
- Create: `tests/test_refoundation_post_epoch0_reasoning_policy_qualification.py`
- Create: `tests/test_refoundation_post_epoch0_reasoning_policy_qualification_adversarial.py`

**Interfaces:**
- Consumes: C10 `MetareasoningPolicy`, `PolicyMetricVector`, `PolicyRevisionProposal`, `PolicyShadowEvaluation`, `PolicyAdoptionReceipt`.
- Produces expected C11 API: `PolicyTrialContext`, `PolicyRegime`, `PolicyEffectVector`, `MatchedPolicyTrial`, `PolicyRegimeQualification`, `PolicyApplicabilityReceipt`, `bind_matched_policy_trial`, `qualify_policy_regime`, `evaluate_policy_applicability`.

- [ ] **Step 1: Write behavior tests before production exists**

Cover:

```python
context = PolicyTrialContext(...)
regime = PolicyRegime(...)
trial = bind_matched_policy_trial(
    proposal,
    shadow,
    parent_policy=parent,
    candidate_policy=candidate,
    context=context,
    parent_episode_id="holdout-parent-a",
    candidate_episode_id="holdout-candidate-a",
    parent_metrics=PolicyMetricVector(...),
    candidate_metrics=PolicyMetricVector(...),
)
assert trial.verdict is MatchedTrialVerdict.PARETO_NON_REGRESSING
```

Then prove qualification requires at least two distinct tasks, all trials match the same regime, all trial episodes are unique, the adoption receipt binds the candidate policy, and out-of-regime context produces `ABSTAIN_OUT_OF_SCOPE`.

- [ ] **Step 2: Write adversarial tests**

Cover forged IDs, duplicate tags, reused episode authority, cross-proposal/shadow trials, one tail-regressing trial hidden among improvements, regime/world/library/action-class mismatch, forged applicability receipt, bool-smuggling and NaN/infinity.

- [ ] **Step 3: Run canonical Refoundation workflow and capture RED**

Expected failure before production module exists:

```text
ModuleNotFoundError: nolane.external_core.reasoning_policy_qualification
```

Compile/materialization/audit should remain green before pytest collection.

- [ ] **Step 4: Commit the RED contract**

Commit message:

```text
test: specify C11 counterfactual policy qualification
```

---

### Task 2: Implement immutable counterfactual qualification protocol

**Files:**
- Create: `nolane/external_core/reasoning_policy_qualification.py`
- Test: `tests/test_refoundation_post_epoch0_reasoning_policy_qualification.py`
- Test: `tests/test_refoundation_post_epoch0_reasoning_policy_qualification_adversarial.py`

**Interfaces:**
- `PolicyTrialContext(...).context_id: str`
- `PolicyRegime(...).regime_id: str`
- `bind_matched_policy_trial(...) -> MatchedPolicyTrial`
- `qualify_policy_regime(...) -> PolicyRegimeQualification`
- `evaluate_policy_applicability(...) -> PolicyApplicabilityReceipt`

- [ ] **Step 1: Implement canonical primitives**

Use the existing C-family validation style: `_text`, `_sequence`, canonical duplicate-free IDs, finite-number validation rejecting booleans, `_identity(prefix, state)`, strict `to_state`/`from_state` equality checks.

- [ ] **Step 2: Implement exact context and regime objects**

`PolicyTrialContext` stores task/objective/environment/world/ontology/evidence-root/library/action-class/frontier references plus tags.

`PolicyRegime` stores only environment/world/ontology/library/action-class plus required tags.

Provide an exact deterministic matcher:

```python
def context_matches_regime(context: PolicyTrialContext, regime: PolicyRegime) -> bool:
    return (
        context.environment_id == regime.environment_id
        and context.world_revision_id == regime.world_revision_id
        and context.ontology_revision_id == regime.ontology_revision_id
        and context.cognitive_library_digest == regime.cognitive_library_digest
        and context.action_class_id == regime.action_class_id
        and set(regime.required_context_tag_ids).issubset(context.context_tag_ids)
    )
```

No wildcard path exists.

- [ ] **Step 3: Implement derived effect and matched trial**

Derive effect values rather than accepting them from callers. Normalize all axes so positive means candidate improvement. Bind parent/candidate episodes to C10 holdout evidence and reject development evidence or duplicate episode IDs.

- [ ] **Step 4: Implement regime qualification**

Require at least two trials and two distinct task IDs. Reject reused episode authority, duplicate trial IDs, mismatched proposal/shadow/policy lineage, any regime mismatch and any regressing trial. Success requires at least one improved metric across the evidence set.

- [ ] **Step 5: Implement applicability receipt**

Return `QUALIFIED_FOR_CONTEXT` only when the exact context matches the qualified regime. Otherwise return `ABSTAIN_OUT_OF_SCOPE`. Authority string is fixed to `qualification_evidence_only`.

- [ ] **Step 6: Run focused tests**

Run:

```bash
python -m pytest -q \
  tests/test_refoundation_post_epoch0_reasoning_policy_qualification.py \
  tests/test_refoundation_post_epoch0_reasoning_policy_qualification_adversarial.py
```

Expected: all C11 tests pass.

- [ ] **Step 7: Commit GREEN runtime**

Commit message:

```text
feat: add C11 counterfactual policy qualification
```

---

### Task 3: Cut Reasoning/Invention family to v0.0.5 / revision 5

**Files:**
- Modify: `nolane/external_core/reasoning_invention.py`
- Modify: `nolane/external_core/reasoning_frontier.py`
- Modify: `nolane/external_core/reasoning_metacontrol.py`
- Modify: `nolane/external_core/reasoning_review.py`
- Modify: `nolane/external_core/reasoning_meta_learning.py`
- Modify: `nolane/external_core/reasoning_episode.py`
- Modify: `nolane/external_core/reasoning_policy_evolution.py`
- Modify: `nolane/external_core/reasoning_evaluation.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify: `tests/test_refoundation_component_versions.py`
- Modify: C family version expectations in existing Reasoning/Invention tests.
- Create: `tests/test_refoundation_post_epoch0_reasoning_v005_revision.py`

**Interfaces:**
- Every Reasoning/Invention family module reports `COMPONENT_VERSION = "0.0.5"`.
- Canonical `component_revision_map()["external.reasoning_invention"] == 5`.

- [ ] **Step 1: Add failing revision-coherence test**

Assert every Reasoning/Invention family module, including C11, is `0.0.5` and the canonical revision map is `5`.

- [ ] **Step 2: Run test and confirm pre-cutover RED**

Expected: old C1–C10 family modules and canonical revision still report `0.0.4` / `4`.

- [ ] **Step 3: Perform atomic family cutover**

Change component version literals only; do not change old schema versions.

- [ ] **Step 4: Run focused C8–C11 + metadata suite**

Expected: pass.

- [ ] **Step 5: Commit cutover**

Commit message:

```text
feat: cut Reasoning/Invention family to v0.0.5
```

---

### Task 4: Close canonical C11 surfaces and source-authority checks

**Files:**
- Modify: `CURRENT/REASONING_INVENTION_C_LAYER.md`
- Modify: `CURRENT/EXTERNAL_CORE.md`
- Modify: `nolane/metadata/_component_specs.py`
- Modify: `nolane/metadata/implementation_status.py`
- Create: `tests/test_refoundation_post_epoch0_reasoning_policy_qualification_authority.py`

**Interfaces:**
- Canonical docs describe C1–C11 v0.0.5 and `reasoning-policy-qualification-v1`.
- Authority test scans C11 source for prohibited mutable/deployment/Assurance/model-write APIs.

- [ ] **Step 1: Add source-authority test**

Reject exported/write surfaces suggesting `set_current_policy`, `route_policy`, `deploy_policy`, `execute`, `mint_assurance`, `promote_capability`, model writes or Memory/Truth writes.

- [ ] **Step 2: Update canonical docs/metadata**

Document matched counterfactual attribution, tail blocking, exact regime scope and explicit out-of-scope abstention.

- [ ] **Step 3: Run focused metadata/source tests**

Expected: pass.

- [ ] **Step 4: Commit canonical closure**

Commit message:

```text
docs: close C11 canonical reasoning surfaces
```

---

### Task 5: Latest-main integration and exact hosted acceptance

**Files:**
- No new architecture files unless verification exposes a defect.

**Interfaces:**
- Final branch history contains latest accepted `main` without rebase/force-push.
- Exact PR synthetic merge is verified on Python 3.11 and 3.13.

- [ ] **Step 1: Race-check current `main` and PR head**

If `main` advanced, compare changed files and perform a history-preserving merge. Resolve only real authority conflicts; never choose ours/theirs blindly for revision maps.

- [ ] **Step 2: Run exact hosted Refoundation matrix**

Require compile, 67/67 dossier materialization, repository audit, Refoundation tests, Truth/Knowledge tests, zero-loss evidence, organization/campaign/execution regressions and Neural R2.3 verification on both Python legs.

- [ ] **Step 3: Classify broad release workflows**

Do not call historical frozen-boundary failures C11 regressions unless behavior evidence shows C11 causation.

- [ ] **Step 4: Final race guard**

Require `behind_by = 0`, PR mergeable, and final head/base unchanged after verification.

- [ ] **Step 5: Update PR title/body**

Title:

```text
Post-Epoch 0: Reasoning / Invention C-layer v0.0.5
```

Record exact RED evidence, substantive commits, final head/base/synthetic-merge SHAs and Python 3.11/3.13 counts. Keep PR unmerged unless explicitly integrating it into `main` becomes the requested operation.
