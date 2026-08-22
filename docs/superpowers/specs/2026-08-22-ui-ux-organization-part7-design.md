# UI / UX Organization Part VII — Design Specification

## Status

Implements Issue #135 on accepted Parts I–VI. The seven permanent UI/UX identities already exist in the first-generation 67-agent blueprint across two regions: Frontend UI Chief, Frontend Logic Coder, Component Engineer, Browser Runtime Engineer, UX Chief, UX Flow Architect, and Visual & Accessibility Designer.

Part VII does not create prompt personas and does not claim broad visual AGI. It gives these identities governed browser-grounded work, rendered-state evidence, dual Frontend/UX authority, cross-region source-mutation access through Part-V coding controls, independent UI quality gates, direct Chief work and restart-safe context.

## 1. Goals

1. Keep exactly seven permanent UI/UX identities with non-identical operational specializations.
2. Require rendered/browser evidence for UI implementation acceptance; source text alone is insufficient.
3. Preserve separate authority: Frontend Chief owns implementation/render-state decisions; UX Chief owns UX flow/design acceptance.
4. Let frontend identities mutate source only through an explicit audited Part-V cross-region coding grant and ordinary code claims/patch provenance/readiness.
5. Make responsive, accessibility and visual regressions independently detectable.
6. Make both Frontend Chief and UX Chief direct workers rather than routers.
7. Preserve personal memory/skills and evidence-gated learning.

## 2. Authority topology

Part VII spans two existing regions:

- `frontend-ui`: `frontend.chief`, `frontend.logic.01`, `frontend.component.01`, `frontend.browser-runtime.01`.
- `ux-product-design`: `ux.chief`, `ux.flow.01`, `ux.visual-accessibility.01`.

Runtime adds two authoritative objects:

- `frontend-ui-state` — owner `frontend.chief`.
- `ux-design-state` — owner `ux.chief`.

The combined `UIControlPlane` coordinates both stores but never collapses their authority. A frontend agent may propose UX changes, but only UX Chief can accept a UX flow/design revision. A UX agent may request implementation, but source mutation requires a Part-V coding assignment/grant.

## 3. Profiles and routing

`UIProfileRegistry` derives profiles from both UI/UX regions while retaining all universal cognitive capabilities and personal learning.

Operational domains:

- Frontend UI Chief: cross-frontend implementation, rendered integration, browser-grounded repair.
- Frontend Logic Coder: state management, data flow, application interaction logic.
- Component Engineer: components, composition, styles, design-system implementation.
- Browser Runtime Engineer: DOM/CSSOM/browser execution/runtime diagnosis.
- UX Chief: cross-product interaction design, acceptance ownership, bounded direct redesign.
- UX Flow Architect: user journeys, information architecture, interaction transitions.
- Visual & Accessibility Designer: visual hierarchy, design tokens, accessibility, responsive behavior.

Routing is deterministic from requested domains/signals/current workload. Ties use stable agent id. Profile serialization must read current neural versions from `AgentRegistry`, not cache stale versions.

## 4. Rendered observation model

A UI result is not browser-grounded merely because source files changed. `UIObservationLedger` records immutable `RenderObservation` objects containing:

- observation id;
- task/work id;
- producer agent;
- viewport tuple `(width, height, device_scale)`;
- browser runtime artifact id;
- DOM snapshot artifact id;
- screenshot artifact id;
- optional CSSOM artifact id;
- optional accessibility-tree artifact id;
- optional interaction-trace artifact id;
- evidence refs;
- digest.

All referenced artifacts must exist in the existing content-addressed `ArtifactStore`. Artifact kinds are checked (`browser-runtime`, `dom-snapshot`, `screenshot`, `cssom-snapshot`, `accessibility-tree`, `interaction-trace`). Invalid or rebound artifact references fail closed.

`RenderObservation` proves that the agent reasoned over a rendered state contract; it does not claim that the current repository contains a full production browser farm.

## 5. UX flow/design state

`UXDesignLedger` stores immutable revisions of bounded interaction models. `UXFlowSpec` contains:

- flow id and revision;
- task/requirement refs;
- actor;
- goal and user-visible states;
- transitions;
- design-token refs;
- responsive expectations;
- accessibility expectations;
- testable acceptance criteria;
- evidence refs;
- parent revision and digest.

Only `ux.chief` may accept an authoritative UX revision. UX specialists can submit proposals; accepted revisions preserve history. Acceptance criteria are concrete statements and evidence expectations, not prose-only design advice.

## 6. Cross-region coding grant

Part V deliberately rejected unknown/non-core coders until a later audited cross-region path existed. Part VII supplies that path.

`CodingControlPlane` gains `CrossRegionCodingGrant` and `request_external_work` without changing the exact seven core-coding profiles.

Rules:

- grant subject must be a permanent identity outside `core-coding`;
- first-generation Part-VII grants are limited to `frontend-ui` identities;
- grant actor must be `coding.chief` or `nolane.central`;
- grant is scoped to a task id and expires when the task is completed/aborted or is explicitly revoked;
- source claims and patch submission still require current TaskGraph lease;
- external assignee still uses the same `CodeClaimLedger`, `CodingPatchLedger`, plan/architecture versions, compile/test evidence and independent Part-V verifier gate;
- UX identities are not granted source mutation by Part VII.

This preserves one source-mutation authority path rather than creating a UI-specific patch bypass.

## 7. UI implementation readiness

`UIControlPlane.assess_ui_readiness` composes existing Part-V coding readiness with browser-grounded UI evidence.

A UI implementation is ready only if:

1. its Part-V `CodingReadinessReceipt.ready` is true;
2. patch producer is a valid frontend identity with an active/valid cross-region grant for that task;
3. at least one render observation references the same task/work and current patch lineage;
4. visual evidence passes;
5. responsive evidence passes;
6. accessibility evidence passes;
7. interaction/E2E evidence passes when the UX spec declares interactive acceptance;
8. quality verifier is independent from the producer and belongs to `verification-testing`;
9. evidence has zero false accepts and zero regressions;
10. accepted UX revision, if required by the work request, matches the revision expected by the implementation.

No UI readiness receipt merges source automatically.

## 8. UI quality evidence

`UIQualityEvidence` records:

- evidence id;
- verifier agent id;
- kind: `VISUAL_DIFF`, `RESPONSIVE`, `ACCESSIBILITY`, `INTERACTION_E2E`;
- passed;
- false accepts;
- regressions;
- observation ids;
- evidence refs.

The verifier must be a `verification-testing` identity and cannot equal the source producer. Visual-only success cannot substitute for accessibility or responsive evidence. Responsive evidence must cover at least two distinct viewport classes when a responsive gate is required.

## 9. Direct Chief work

### Frontend Chief

Acceptance includes a task leased directly to `frontend.chief`. Coding Chief issues an audited task-scoped cross-region coding grant. Frontend Chief personally claims source, submits a patch, produces rendered observation artifacts, obtains independent coding/UI evidence and completes through the ordinary `chief_direct_work` path.

### UX Chief

Acceptance includes a task leased directly to `ux.chief`. UX Chief personally produces and accepts a bounded `UXFlowSpec` revision with testable acceptance criteria and evidence. It does not delegate the design decision and does not require source mutation.

## 10. Feedback protocols

All seven UI/UX identities may emit:

- `PLAN_GAP_DETECTED` to Planning Chief for missing UI/UX work/dependencies;
- `ARCHITECTURE_CONCERN` to Architecture Chief for frontend boundaries/contracts;
- requirement ambiguity/change proposals through existing Part-III authority where applicable.

They cannot silently mutate the master plan, architecture graph or requirements graph.

## 11. Memory and learning

Part VII reuses Part-I memory and `SkillEvolutionEngine`.

Examples of personal skill candidates:

- frontend state synchronization pattern;
- component composition repair;
- browser runtime diagnosis;
- responsive layout rule;
- accessibility remediation pattern;
- interaction-flow simplification.

A successful UI/UX episode may propose a personal candidate, but promotion remains governed by existing evidence thresholds. Failed visual/interaction hypotheses remain episodic evidence, not active global rules.

## 12. Snapshot and context

Runtime adds `runtime.ui: UIControlPlane` and persists:

- UI profiles;
- render observations;
- UX proposals/revisions;
- UI work requests/assignments;
- quality evidence/readiness receipts;
- cross-region coding grant state (inside Part V coding state);
- counters and provenance.

Context Compiler adds:

- `('ui-state', runtime.ui.digest)` for frontend/UX identities;
- current UX revision refs and relevant event delta;
- existing `coding-state` for frontend identities when they hold source work.

Other regions do not receive full UI private state by default.

## 13. Fail-closed rules

- unknown/non-UI identity in UI routing -> reject;
- source-only UI completion with no render observation -> reject;
- artifact kind/id mismatch -> reject;
- frontend source mutation without valid task-scoped Part-V cross-region grant -> reject;
- UX source mutation through Part VII -> reject;
- non-UX-Chief authoritative UX acceptance -> reject;
- self-verification -> reject;
- verifier outside `verification-testing` -> reject;
- missing visual/responsive/accessibility required gate -> reject;
- single-viewport evidence cannot satisfy a multi-viewport responsive gate;
- false-accept/regression evidence -> reject;
- stale UX revision -> reject;
- snapshot digest/counter/profile mismatch -> reject restore;
- no automatic merge from UI readiness.

## 14. Acceptance tests

- exactly seven permanent UI/UX identities, split 4 frontend + 3 UX, with distinct domains;
- deterministic routing for frontend logic, component, browser runtime, UX flow, accessibility/visual and cross-region Chief work;
- render observation requires content-addressed browser/DOM/screenshot artifacts;
- source text alone cannot satisfy UI readiness;
- UX Chief alone accepts authoritative UX revisions and produces concrete acceptance criteria;
- frontend cross-region coding grant is task-scoped, audited, revocable and does not alter the seven core-coding profiles;
- Frontend Chief personally implements a difficult UI change through ordinary source claim/patch/readiness/direct-work paths;
- UX Chief personally redesigns and accepts a bounded interaction flow;
- responsive/accessibility/visual regressions are independently rejected;
- UI agents can emit plan/architecture feedback without mutating authority;
- personal UI/UX skill remains candidate until normal promotion;
- exact snapshot/restore and context digest;
- all Parts I–VI regressions remain green on Python 3.11/3.13.
