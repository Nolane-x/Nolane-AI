# Reasoning / Invention Metareasoning v0.0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete `external.reasoning_invention` v0.0.2 with bounded epistemic-frontier, value-of-thought metacontrol, fresh-context adversarial review, meta-learning evidence, and exact revision closure while preserving C1–C7 authority separation.

**Architecture:** Keep `reasoning_invention.py` schema v1 backward compatible and add four focused additive protocol modules under the same component identity. Each module owns immutable, content-addressed artifacts only. Metacontrol returns Pareto action sets and fail-closed stop/abstain dispositions; review enforces an auditable context partition; meta-learning compiles descriptive outcome evidence without applying policy changes.

**Tech Stack:** Python 3.11/3.13, frozen dataclasses, enums, `nolane.core.canonical_digest`, pytest, GitHub Actions Refoundation gates.

**Spec:** `docs/superpowers/specs/2026-08-31-reasoning-invention-metacontrol-design.md`

## Global Constraints

- `external.reasoning_invention` canonical component version after this plan: `0.0.2`.
- Preserve existing `reasoning-invention-v1` serialization and identities.
- New schemas: `reasoning-frontier-v1`, `reasoning-metacontrol-v1`, `reasoning-review-v1`, `reasoning-meta-learning-v1`.
- No import of `CapabilityAcquisitionGovernor`, `TransferMetaGovernor`, `AssuranceControlPlane`, mutable Cognitive Library registration APIs, or neural mutation APIs in the new modules.
- No canonical scalar utility and no single-winner choice among non-dominated actions.
- Branch budget range is exactly `1..7`.
- Every derived identity must be recomputed and verified during `from_state`.
- All numeric APIs reject booleans and non-finite values.
- Do not merge until exact final head is green on hosted Python 3.11 and 3.13 canonical gates.

---

### Task 1: RED — revision and frontier contracts

**Files:**
- Create: `tests/test_refoundation_post_epoch0_reasoning_metacontrol.py`

**Interfaces:**
- Consumes: existing `nolane.external_core.reasoning_invention` and `nolane.metadata.component_versions.component_version`.
- Produces test contract for: `reasoning_frontier`, `reasoning_metacontrol`, `reasoning_review`, `reasoning_meta_learning`.

- [ ] **Step 1: Write failing declaration/revision test**

```python
def test_reasoning_invention_revision_is_coherent():
    core = importlib.import_module("nolane.external_core.reasoning_invention")
    evaluation = importlib.import_module("nolane.external_core.reasoning_evaluation")
    assert core.COMPONENT_VERSION == "0.0.2"
    assert evaluation.COMPONENT_VERSION == "0.0.2"
    assert str(component_version("external.reasoning_invention")) == "0.0.2"
```

- [ ] **Step 2: Write failing frontier tests**

Construct `DecisionUnknown`, two structurally different `RivalHypothesisRef` rows and a `ReasoningFrontier`. Assert canonical order invariance, `branch_budget <= 7`, live-rival count cannot exceed budget, tampered IDs fail restore, same source/target representation is rejected, and assumption inversion must target an assumption in the frontier through the binder.

- [ ] **Step 3: Commit RED tests only**

```bash
git add tests/test_refoundation_post_epoch0_reasoning_metacontrol.py
git commit -m "test: declare reasoning metacontrol v0.0.2"
```

- [ ] **Step 4: Verify hosted RED**

Expected failure is missing modules and/or `0.0.1 != 0.0.2`; unrelated baseline failures must not be treated as valid RED evidence.

---

### Task 2: GREEN — epistemic frontier artifacts

**Files:**
- Create: `nolane/external_core/reasoning_frontier.py`
- Test: `tests/test_refoundation_post_epoch0_reasoning_metacontrol.py`

**Interfaces:**
- Produces:
  - `UnknownKind`
  - `HypothesisCategory`
  - `DecisionUnknown`
  - `RivalHypothesisRef`
  - `ReasoningFrontier`
  - `AssumptionInversion`
  - `RepresentationShift`
  - `bind_assumption_inversion(frontier, ...)`
  - `bind_representation_shift(frontier, ...)`

- [ ] **Step 1: Implement strict helpers and enums**

Use `canonical_digest`; normalize set-like IDs lexicographically; reject bool numeric values, NaN and infinity.

- [ ] **Step 2: Implement `DecisionUnknown`**

Fields: `description`, `kind`, `impact`, `uncertainty`, `decision_relevance`, `discovery_path_ids`, `could_overturn_decision`, derived `unknown_id`. Scores are `[0,1]`; discovery paths require at least one ID.

- [ ] **Step 3: Implement `RivalHypothesisRef`**

Fields: `hypothesis_id`, `category`, `structural_family_id`, `prediction_ids`, `falsifier_ids`, `evidence_for_ids`, `evidence_against_ids`, derived `rival_id`. Prediction and falsifier sets are mandatory.

- [ ] **Step 4: Implement `ReasoningFrontier`**

Fields: `reasoning_receipt_id`, `objective_id`, `cognitive_library_digest`, `unknowns`, `rivals`, `assumption_ids`, `hard_constraint_ids`, `branch_budget`, derived `frontier_id`. Require at least one rival, unique hypothesis IDs, `1 <= branch_budget <= 7`, and `len(rivals) <= branch_budget`.

- [ ] **Step 5: Implement inversion/representation artifacts and binders**

`AssumptionInversion` binds the frontier ID, exact assumption ID, inversion statement, consequence IDs, surviving invariant IDs and challenger hypothesis IDs. Binder rejects assumptions absent from the frontier.

`RepresentationShift` binds frontier ID, distinct source/target representation IDs, mapping IDs, new-affordance IDs, lost-information IDs and challenger hypothesis IDs. The binder only validates frontier identity and creates the immutable artifact.

- [ ] **Step 6: Add canonical `to_state` / `from_state` on all artifacts and run focused tests**

Expected: frontier tests green; revision test remains red until Task 6.

- [ ] **Step 7: Commit**

```bash
git add nolane/external_core/reasoning_frontier.py tests/test_refoundation_post_epoch0_reasoning_metacontrol.py
git commit -m "feat: add bounded reasoning frontier"
```

---

### Task 3: GREEN — value-of-thought metacontrol

**Files:**
- Create: `nolane/external_core/reasoning_metacontrol.py`
- Test: `tests/test_refoundation_post_epoch0_reasoning_metacontrol.py`

**Interfaces:**
- Consumes: `ReasoningFrontier`.
- Produces:
  - `MetaActionKind`
  - `ControlDisposition`
  - `ReasoningActionProposal`
  - `MetareasoningBudget`
  - `ReasoningControlDecision`
  - `dominates_action(left, right) -> bool`
  - `pareto_action_frontier(proposals) -> tuple[ReasoningActionProposal, ...]`
  - `plan_next_reasoning_actions(frontier, budget, proposals) -> ReasoningControlDecision`

- [ ] **Step 1: Add RED tests for action dominance and stopping semantics**

Test that a strictly better action dominates, equal/trade-off vectors do not; order does not affect Pareto output; wrong-frontier proposals fail; over-cost proposals are filtered; zero action budget does not continue.

- [ ] **Step 2: Implement action proposal**

Fields: `frontier_id`, `kind`, `target_ids`, `expected_decision_value`, `expected_information_gain`, `uncertainty_reduction`, `estimated_cost`, `residual_risk`, `reason`, derived `action_id`.

Maximize: decision value, information gain, uncertainty reduction. Minimize: cost, residual risk.

- [ ] **Step 3: Implement explicit budget**

Fields: `frontier_id`, `remaining_actions`, `remaining_cost`, `minimum_actionable_gain`, `budget_id`. `remaining_actions` may be zero; remaining cost is non-negative.

- [ ] **Step 4: Implement control decision**

Dispositions: `CONTINUE`, `HALT_NO_FURTHER_VALUE`, `ABSTAIN_UNRESOLVED`. Store only Pareto action IDs, unresolved overturning unknown IDs and reason. No accepted/promoted/reused field.

- [ ] **Step 5: Implement `plan_next_reasoning_actions`**

Validate exact frontier binding. Viable proposals must fit remaining cost and clear the declared marginal-gain floor using `max(expected_decision_value, expected_information_gain, uncertainty_reduction)`. If viable actions exist and actions remain, return `CONTINUE` with the Pareto action set. If none exist and an overturning unknown remains, return `ABSTAIN_UNRESOLVED`; otherwise return `HALT_NO_FURTHER_VALUE`.

- [ ] **Step 6: Run focused tests and commit**

```bash
git add nolane/external_core/reasoning_metacontrol.py tests/test_refoundation_post_epoch0_reasoning_metacontrol.py
git commit -m "feat: add value-of-thought metacontrol"
```

---

### Task 4: GREEN — fresh-context adversarial review

**Files:**
- Create: `nolane/external_core/reasoning_review.py`
- Test: `tests/test_refoundation_post_epoch0_reasoning_metacontrol.py`

**Interfaces:**
- Produces:
  - `FreshReviewVerdict`
  - `FreshContextReviewRequest`
  - `SpecificationGamingFinding`
  - `FreshContextReviewReceipt`
  - `bind_fresh_context_review(request, ...) -> FreshContextReviewReceipt`

- [ ] **Step 1: Add RED tests for context independence**

Producer/reviewer agent IDs must differ. Producer/reviewer session IDs must differ. `review_context_ids` and `withheld_rationale_ids` must be disjoint. Evidence packet IDs must be included in review context. Every requested check must be completed by the receipt.

- [ ] **Step 2: Add RED anti-spec-gaming tests**

`SUPPORTED_FOR_SCOPE` fails if objections, counterexamples or any `SpecificationGamingFinding(blocking=True)` exists. `REJECTED` requires at least one objection, counterexample or blocking gaming finding. `REVISE` requires at least one objection or gaming finding.

- [ ] **Step 3: Implement request/finding/receipt and binder**

Every object is frozen/content-addressed. The binder checks exact reviewer identity/session and reproduced evidence is a subset of the request evidence packet. It does not import Assurance.

- [ ] **Step 4: Run focused tests and commit**

```bash
git add nolane/external_core/reasoning_review.py tests/test_refoundation_post_epoch0_reasoning_metacontrol.py
git commit -m "feat: add fresh-context adversarial review"
```

---

### Task 5: GREEN — meta-learning evidence without self-edit

**Files:**
- Create: `nolane/external_core/reasoning_meta_learning.py`
- Test: `tests/test_refoundation_post_epoch0_reasoning_metacontrol.py`

**Interfaces:**
- Consumes: `MetaActionKind`.
- Produces:
  - `MetareasoningActionOutcome`
  - `MetareasoningLearningMetrics`
  - `MetareasoningLearningEvidence`
  - `compile_metareasoning_learning_evidence(outcomes) -> MetareasoningLearningEvidence`

- [ ] **Step 1: Add RED tests**

Require distinct action outcomes; at least two outcomes; at least one non-empty C7 evaluation receipt ID across the bundle; canonical order invariance; tamper rejection; information efficiency equals total observed information gain divided by total cost; no policy-update or mutation API exists.

- [ ] **Step 2: Implement action outcome**

Fields: `frontier_id`, `control_decision_id`, `action_id`, `action_kind`, `evaluation_receipt_id`, `outcome_evidence_ids`, `decision_correct`, `observed_information_gain`, `actual_cost`, `regression_count`, `generalized`, `robust`, derived `outcome_id`.

- [ ] **Step 3: Implement aggregate learning evidence**

Expose descriptive metrics: `outcome_count`, per-action-kind counts, correct-decision count, information efficiency, regression count, generalized count and robust count. The evidence bundle contains canonical outcome IDs and evaluation receipt IDs only; it has no method that writes a policy.

- [ ] **Step 4: Run focused tests and commit**

```bash
git add nolane/external_core/reasoning_meta_learning.py tests/test_refoundation_post_epoch0_reasoning_metacontrol.py
git commit -m "feat: add metareasoning learning evidence"
```

---

### Task 6: GREEN — canonical revision cutover

**Files:**
- Modify: `nolane/external_core/reasoning_invention.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify: `nolane/metadata/_component_specs.py`
- Modify: `nolane/metadata/implementation_status.py`
- Modify: `CURRENT/REASONING_INVENTION_C_LAYER.md`
- Modify: `CURRENT/EXTERNAL_CORE.md`
- Test: `tests/test_refoundation_post_epoch0_reasoning_metacontrol.py`

**Interfaces:**
- Consumes: additive modules from Tasks 2–5 and existing C7 evaluation.
- Produces: coherent canonical `external.reasoning_invention == 0.0.2` declaration.

- [ ] **Step 1: Bump only component revision, not v1 schema**

Change `reasoning_invention.py` `COMPONENT_VERSION` from `0.0.1` to `0.0.2`, leaving `SCHEMA_VERSION = "reasoning-invention-v1"` unchanged.

Change `_COMPONENT_REVISIONS["external.reasoning_invention"]` from `1` to `2`.

- [ ] **Step 2: Update component description/status**

Document that the canonical component now includes immutable protocol spine, closed-loop evaluation, epistemic frontier, metacontrol, fresh-context adversarial review and descriptive meta-learning evidence, while mutable authorities remain separate.

- [ ] **Step 3: Update architecture docs**

Add the Reasoning Ecology outer loop, v0.0.2 schema inventory, stop/abstain semantics, fresh-context limitations and meta-learning no-self-edit invariant.

- [ ] **Step 4: Run revision test**

The Task 1 declaration/revision test must now pass.

- [ ] **Step 5: Commit**

```bash
git add nolane/external_core/reasoning_invention.py nolane/metadata/component_versions.py nolane/metadata/_component_specs.py nolane/metadata/implementation_status.py CURRENT/REASONING_INVENTION_C_LAYER.md CURRENT/EXTERNAL_CORE.md tests/test_refoundation_post_epoch0_reasoning_metacontrol.py
git commit -m "feat: cut reasoning invention v0.0.2"
```

---

### Task 7: Adversarial hardening

**Files:**
- Modify: `tests/test_refoundation_post_epoch0_reasoning_metacontrol.py`
- Modify only implementation files implicated by a failing test.

- [ ] **Step 1: Add RED adversarial tests**

Cover bool-as-number, NaN/Infinity, duplicate IDs, forged IDs, caller-order drift, same producer/reviewer, same session, context/rationale overlap, branch budget `0`/`8`, rival overflow, wrong frontier, supported review with blocking gaming finding, meta-learning duplicate outcomes, and forbidden mutable-authority strings.

- [ ] **Step 2: Fix only reproduced defects**

Every defect fix must follow RED → GREEN. Do not weaken an existing assertion to obtain green.

- [ ] **Step 3: Commit hardening**

```bash
git add tests/test_refoundation_post_epoch0_reasoning_metacontrol.py nolane/external_core/reasoning_frontier.py nolane/external_core/reasoning_metacontrol.py nolane/external_core/reasoning_review.py nolane/external_core/reasoning_meta_learning.py
git commit -m "test: harden reasoning metacontrol boundaries"
```

---

### Task 8: Exact-head hosted verification and PR closure

**Files:**
- Update PR #236 metadata only after exact-head verification.

- [ ] **Step 1: Compare branch to latest `main`**

Require `behind_by == 0`. If main advanced, merge latest main into the feature branch without force-push and rerun exact-head gates.

- [ ] **Step 2: Inspect hosted workflow runs for exact head SHA**

Require canonical Python 3.11 and 3.13 Refoundation gates, compile/audit/dossier/frozen-neural gates and broad regression gates expected by the repository. Classify every failure before modifying code.

- [ ] **Step 3: Verify authority boundary by source scan**

New reasoning modules must not contain mutable governor imports or direct calls to Cognitive Library registration, Capability Acquisition promotion, Transfer/Meta acceptance, Assurance issuance or neural mutation.

- [ ] **Step 4: Update PR title/body**

Rename the PR to reflect `Reasoning / Invention C-layer v0.0.2`. Record exact base/head SHAs, the original C1–C7 work, C8 metareasoning additions, RED/GREEN evidence, changed-file census and final hosted gate status.

- [ ] **Step 5: Keep the PR unmerged unless explicitly authorized**

If exact-head verification is fully green, it may be marked ready for review; do not claim certified completion while any required gate is pending or failing.