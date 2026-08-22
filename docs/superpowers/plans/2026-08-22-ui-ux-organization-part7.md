# UI / UX Organization Part VII Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the seven persistent Frontend/UI and UX identities into a browser-grounded dual-authority engineering organization integrated with Part-V source mutation and Parts I–VI evidence/state.

**Architecture:** Add focused UI profile, observation and UX-design ledgers plus a coordinating `UIControlPlane`. Extend Part-V with an audited task-scoped cross-region coding grant for frontend identities while keeping the seven core-coding profiles unchanged; UI readiness composes Part-V coding readiness with rendered-state and independent visual/responsive/accessibility evidence.

**Tech Stack:** Python standard library/dataclasses/enums, existing `cogcoder.organization` ArtifactStore/TaskGraph/Authority/Planning/Architecture/Coding/SkillEvolution/EventLedger, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-22-ui-ux-organization-part7-design.md`

## Global Constraints

- Exactly seven permanent UI/UX identities: four `frontend-ui`, three `ux-product-design`.
- All retain universal cognition, personal memory/skills/self-models and <100M physical parameters.
- Frontend Chief and UX Chief remain direct workers.
- Frontend source mutation uses Part-V claims/patches/readiness through an audited task-scoped cross-region grant.
- Core-coding profile count remains exactly seven.
- UX identities receive no source-mutation grant in Part VII.
- Browser-grounded readiness requires rendered-state artifacts; source text alone is insufficient.
- Visual, responsive and accessibility gates are independent and fail closed.
- No automatic merge from UI readiness.
- Existing Parts I–VI authority remains canonical.

---

### Task 1: UI/UX profiles and deterministic routing

**Files:**
- Create: `cogcoder/organization/ui_profiles.py`
- Test: `tests/test_coding_agi_ui_profiles.py`

**Interfaces:**
- Consumes: `AgentRegistry`, existing seven UI/UX identities.
- Produces: `UIDomain`, `UIProfile`, `UIWorkRequest`, `UICandidateScore`, `UIAssignmentReceipt`, `UIProfileRegistry.route`.

- [ ] RED: registry contains exactly 7 profiles split 4 frontend/3 UX and all retain learning/direct-work flags from identity.
- [ ] RED: logic work routes `frontend.logic.01`; component work routes `frontend.component.01`; runtime/DOM work routes `frontend.browser-runtime.01`; flow work routes `ux.flow.01`; accessibility/visual work routes `ux.visual-accessibility.01`; cross-region/high-complexity requests can route the relevant Chief.
- [ ] RED: same request/current state gives same ranked candidates and digest.
- [ ] RED: snapshot serialization reads current neural version from authoritative `AgentRegistry` after a neural version change.
- [ ] Implement profile config and stable deterministic scoring without changing blueprint identity count.
- [ ] Run focused tests and require PASS.

---

### Task 2: Rendered observation and content-addressed browser artifacts

**Files:**
- Create: `cogcoder/organization/ui_observations.py`
- Test: `tests/test_coding_agi_ui_observations.py`

**Interfaces:**
- Consumes: `ArtifactStore`.
- Produces: `UIArtifactKind`, `Viewport`, `RenderObservation`, `UIObservationLedger.record`.

- [ ] RED: observation fails if browser-runtime, DOM snapshot or screenshot artifact is absent.
- [ ] RED: referenced artifact kind must match its declared role.
- [ ] RED: valid observation preserves viewport, artifact ids, task/work/producers and canonical digest.
- [ ] RED: CSSOM, accessibility-tree and interaction-trace are optional but kind-checked when present.
- [ ] RED: exact observation ledger state round-trips and counters reject inconsistent restore.
- [ ] Implement immutable observation ledger using existing content-addressed ArtifactStore ids, never embedding fake screenshot bytes as authority.
- [ ] Run focused tests and require PASS.

---

### Task 3: UX flow/design authority and testable acceptance

**Files:**
- Create: `cogcoder/organization/ui_design.py`
- Test: `tests/test_coding_agi_ui_design.py`

**Interfaces:**
- Consumes: `AgentRegistry`, `AuthorityGraph`, `EventLedger`.
- Produces: `UXAcceptanceCriterion`, `UXTransition`, `UXFlowSpec`, `UXDesignProposal`, `UXDesignLedger.propose`, `UXDesignLedger.accept`.

- [ ] RED: UX specialist can submit a proposal but cannot mark it authoritative.
- [ ] RED: only `ux.chief` can accept authoritative UX revision.
- [ ] RED: accepted revision contains concrete state transitions, responsive/a11y expectations and at least one testable acceptance criterion with evidence expectations.
- [ ] RED: revisions preserve parent/version history and canonical digest; a rejected/superseded proposal cannot masquerade as current revision.
- [ ] Implement `ux-design-state` authority ownership in runtime initialization and fail-closed restore.
- [ ] Run focused tests and require PASS.

---

### Task 4: Part-V cross-region coding grant

**Files:**
- Modify: `cogcoder/organization/coding.py`
- Test: `tests/test_coding_agi_ui_cross_region_coding.py`
- Regression: `tests/test_coding_agi_coding_profiles.py`
- Regression: `tests/test_coding_agi_coding_readiness.py`

**Interfaces:**
- Consumes: existing `CodingWorkRequest`, `CodeClaimLedger`, `CodingPatchLedger`, `TaskGraph`, `AgentRegistry`.
- Produces: `CrossRegionCodingGrant`, `ExternalCodingAssignmentReceipt`, `CodingControlPlane.grant_external_coder`, `revoke_external_grant`, `request_external_work`.

- [ ] RED: exact seven `core-coding` profiles remain unchanged after external grant.
- [ ] RED: only `coding.chief` or `nolane.central` can issue a cross-region grant.
- [ ] RED: first-generation grant subject must be in `frontend-ui`; UX identity grant is rejected.
- [ ] RED: grant is task-scoped and requires subject to own that TaskGraph lease before source claim/patch.
- [ ] RED: revoked/completed/aborted-task grant cannot authorize a new claim or patch.
- [ ] RED: external frontend patch still requires source claim coverage, current plan/architecture, compile/test evidence and independent Part-V verifier readiness.
- [ ] Implement separate external-grant/assignment state; do not add frontend identities to `CodingProfileRegistry.profiles()`.
- [ ] Preserve backward-compatible `from_state(state.get(..., {}))` defaults.
- [ ] Run Part-V focused regressions and require PASS.

---

### Task 5: UI quality evidence and composed readiness

**Files:**
- Create: `cogcoder/organization/ui.py`
- Test: `tests/test_coding_agi_ui_readiness.py`
- Test: `tests/test_coding_agi_ui_quality.py`

**Interfaces:**
- Consumes: `UIProfileRegistry`, `UIObservationLedger`, `UXDesignLedger`, `CodingControlPlane`, `CodingReadinessReceipt`, `ArtifactStore`, `TaskGraph`, `AgentRegistry`, `EventLedger`.
- Produces: `UIQualityKind`, `UIQualityEvidence`, `UIReadinessReceipt`, `UIControlPlane`.

- [ ] RED: a Part-V-ready patch with no render observation is not UI-ready.
- [ ] RED: visual PASS alone cannot substitute for responsive/accessibility PASS.
- [ ] RED: quality verifier equal to producer or outside `verification-testing` is rejected.
- [ ] RED: false accepts/regressions/failed quality evidence reject readiness.
- [ ] RED: responsive gate requires observations spanning at least two distinct viewport classes when required.
- [ ] RED: stale expected UX revision rejects readiness.
- [ ] RED: fully valid coding readiness + rendered observation + independent visual/responsive/accessibility evidence produces canonical UI readiness receipt but does not merge source.
- [ ] Implement UI work/assignment state, quality evidence store and readiness recomputation from current authoritative state.
- [ ] Run focused tests and require PASS.

---

### Task 6: Direct Frontend Chief, direct UX Chief, feedback and learning

**Files:**
- Test: `tests/test_coding_agi_ui_direct_work.py`
- Test: `tests/test_coding_agi_ui_feedback_learning.py`
- Modify: `cogcoder/organization/ui.py`

**Interfaces:**
- Consumes: existing `OrganizationRuntime.chief_direct_work`, Part-V external coding path, `SkillEvolutionEngine`, TaskGraph plan-gap flow, ArchitectureControlPlane concern flow.
- Produces: `UIControlPlane.propose_personal_skill`, `report_plan_gap`, `report_architecture_concern`.

- [ ] RED: `frontend.chief` personally owns a leased UI task, receives audited cross-region coding grant, claims source, submits patch, produces render observation and passes independent coding/UI readiness before ordinary chief direct completion.
- [ ] RED: `ux.chief` personally owns a leased design task, produces and accepts a bounded UX flow revision with concrete acceptance criteria, then completes through ordinary chief direct work with design artifact/reference.
- [ ] RED: frontend/UX specialist can emit plan gap and architecture concern without mutating those authoritative stores.
- [ ] RED: successful UI/UX episode creates a personal skill candidate; scope remains `CANDIDATE` until existing promotion flow.
- [ ] Implement minimal methods using existing authorities; no separate plan/architecture mutation API.
- [ ] Run focused tests and require PASS.

---

### Task 7: Runtime, context, snapshot and Part-VII CI

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Modify: `cogcoder/organization/context.py`
- Test: `tests/test_coding_agi_ui_snapshot.py`
- Test: `tests/test_coding_agi_ui_context.py`
- Create: `.github/workflows/coding-agi-ui-part7.yml`

**Interfaces:**
- Consumes: `UIControlPlane` plus all Parts I–VI runtime objects.
- Produces: `runtime.ui`, persisted `ui` state and UI-specific context artifact refs.

- [ ] RED: exact snapshot/restore preserves UI profiles, observations, UX revisions, UI work, quality evidence/readiness and Part-V external grants.
- [ ] RED: frontend/UX wake context contains `('ui-state', runtime.ui.digest)`.
- [ ] RED: frontend identity with active external source work also receives existing `coding-state`; UX identity does not receive private coding state merely by being in Part VII.
- [ ] RED: non-UI regions do not receive full UI-state artifact by default.
- [ ] Integrate `runtime.ui` after Coding/Debugging construction and before Context/Central construction; preserve older snapshot defaults.
- [ ] Add Python 3.11/3.13 CI running Part VII plus Parts I–VI organization regressions.
- [ ] Capture RED before production modules, then exact-head GREEN before merge.

## Self-review

- Issue #135 acceptance gates map to explicit tasks/tests.
- Dual authority is preserved: Frontend Chief and UX Chief cannot overwrite each other's authoritative state.
- Cross-region source mutation extends Part V rather than bypassing it.
- Browser-grounded evidence is content-addressed and typed; source text alone cannot pass.
- Visual/responsive/accessibility verification remains independent and fail-closed.
- No TODO/TBD placeholders and no claim that artifact contracts alone demonstrate broad visual AGI.
