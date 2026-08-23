# Refoundation Wave 3 AI-First Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `CURRENT/` plus `shared/`, `regions/`, `ai/`, and `nolane.ai` the canonical authority for all 67 permanent AI identities while preserving exact accepted runtime behavior.

**Architecture:** Static source manifests own global, regional, and individual data. `nolane.ai` loads and resolves those layers into exact accepted identity projections and generated per-AI dossiers. `cogcoder.refoundation.organization_spec` becomes a compatibility bridge so downstream code is preserved while authority direction is inverted.

**Tech Stack:** Python 3.11/3.13 stdlib (`dataclasses`, `json`, `pathlib`), JSON/Markdown canonical data, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-23-refoundation-wave3-ai-first-authority-design.md`

## Global Constraints
- Exactly 67 permanent identities: 1 Central, 15 Chiefs, 20 senior specialists, 31 specialists.
- Every permanent identity remains below 100M physical parameters.
- Shared Neural physical parameters remain exactly 56,000,000.
- Local physical parameters remain 40M Central / 34M Chief / 20M senior specialist / 8M specialist.
- No user-facing Agent product/UI scope.
- No destructive historical deletion in Wave 3.
- Generated `RESOLVED.*` files are derived artifacts, never write authority.
- `nolane.ai` must not import `cogcoder.refoundation.organization_spec`.

---

### Task 1: Freeze AI-first authority contracts

**Files:**
- Create: `tests/test_refoundation_wave3_ai_first_authority.py`

**Interfaces:**
- Consumes: accepted `build_first_generation_blueprint()` and current Refoundation tests.
- Produces: executable Wave-3 architecture contract.

- [ ] **Step 1: Add failing tests for CURRENT law, 67/15 source cardinality, resolver parity, dependency direction, generated-view drift, and update-scope isolation.**
- [ ] **Step 2: Run `python -m pytest -q tests/test_refoundation_wave3_ai_first_authority.py`; expected RED because `nolane.ai` and canonical source directories do not exist.**
- [ ] **Step 3: Commit the RED contract unchanged.**

### Task 2: Create architecture-law surface

**Files:**
- Create: `CURRENT/README.md`
- Create: `CURRENT/SYSTEM_DEFINITION.md`
- Create: `CURRENT/TERMINOLOGY.md`
- Create: `CURRENT/ORGANIZATION.md`
- Create: `CURRENT/NEURAL_CORE.md`
- Create: `CURRENT/EXTERNAL_CORE.md`
- Create: `CURRENT/RESEARCH_SCOPE.md`
- Create: `CURRENT/STATUS.md`

**Interfaces:**
- Consumes: approved Wave-3 design.
- Produces: explicit present-architecture precedence and terminology law.

- [ ] **Step 1: Write the eight law files with `CURRENT/` precedence, current research-only scope, and Tool-within-External-Core ontology.**
- [ ] **Step 2: Run focused CURRENT-law contract tests.**
- [ ] **Step 3: Commit with the canonical source implementation.**

### Task 3: Create global/regional/individual source manifests

**Files:**
- Create: `shared/neural-core/manifest.json`
- Create: `shared/external-core/manifest.json`
- Create: `regions/<15-region-id>/manifest.json`
- Create: `ai/<67-agent-id>/profile.json`

**Interfaces:**
- Produces: single-source global/regional/private data inputs consumed by `nolane.ai.catalog`.

- [ ] **Step 1: Materialize shared manifests from the accepted 56M/universal/general-tool definitions.**
- [ ] **Step 2: Materialize exactly 15 region manifests with chief/member sets and accepted External Core bindings.**
- [ ] **Step 3: Materialize exactly 67 individual profiles preserving accepted role/rank/local-parameter/memory/skill/authority/tool data.**
- [ ] **Step 4: Validate cardinality, uniqueness, region membership, and below-100M accounting in focused tests.**

### Task 4: Implement canonical `nolane.ai` loader and resolver

**Files:**
- Create: `nolane/ai/__init__.py`
- Create: `nolane/ai/types.py`
- Create: `nolane/ai/catalog.py`
- Create: `nolane/ai/resolver.py`

**Interfaces:**
- Produces: `build_canonical_identity_states()`, `load_profiles()`, `load_regions()`, `resolve_ai(agent_id, ...)`, `resolve_all(...)`, `render_resolved_markdown(...)`.

- [ ] **Step 1: Implement immutable manifest/result dataclasses and fail-closed JSON validation.**
- [ ] **Step 2: Implement deterministic loaders sorted by canonical agent/region id.**
- [ ] **Step 3: Implement resolver composition and exact accepted identity-state projection.**
- [ ] **Step 4: Add optional version overrides used only to calculate Global/Regional/Individual impact without mutating source.**
- [ ] **Step 5: Run focused parity and scope-isolation tests.**

### Task 5: Invert Refoundation identity authority

**Files:**
- Modify: `cogcoder/refoundation/organization_spec.py`

**Interfaces:**
- Consumes: canonical exports from `nolane.ai.catalog`.
- Preserves: legacy constants/dataclasses/functions imported by existing Refoundation/capability code.

- [ ] **Step 1: Replace authored identity/region implementation with explicit compatibility re-exports from `nolane.ai.catalog`.**
- [ ] **Step 2: Assert `nolane.ai` source never imports the compatibility module.**
- [ ] **Step 3: Run all existing Refoundation identity/capability tests for zero-loss parity.**

### Task 6: Materialize and seal per-AI resolved dossiers

**Files:**
- Create: `ai/<67-agent-id>/RESOLVED.json`
- Create: `ai/<67-agent-id>/RESOLVED.md`
- Create: `tools/refoundation/generate_ai_resolved_views.py`

**Interfaces:**
- Consumes: `nolane.ai.resolver`.
- Produces: deterministic generated human/machine current composition for every AI.

- [ ] **Step 1: Implement generator that rewrites only `RESOLVED.json`/`RESOLVED.md`.**
- [ ] **Step 2: Materialize all 134 resolved files.**
- [ ] **Step 3: Recompute in tests and byte-compare generated views to prevent drift/manual edits.**

### Task 7: Full verification and hosted acceptance

**Files:**
- Modify only if a verified regression exposes an implementation defect.

- [ ] **Step 1: Run `python -m compileall -q cogcoder/organization cogcoder/refoundation nolane`.**
- [ ] **Step 2: Run `python -m pytest -q tests/test_refoundation_*.py`.**
- [ ] **Step 3: Run the existing full organization/campaign/execution regression command from the Refoundation workflow.**
- [ ] **Step 4: Run frozen Neural R2.3 metadata verification.**
- [ ] **Step 5: Open stacked Wave-3 draft PR against Wave 2c and use hosted `Nolane-AI Refoundation Epoch 0` on Python 3.11/3.13 as acceptance authority.**
- [ ] **Step 6: Record exact head, workflow run, job IDs, and any RED→GREEN fixes in the PR body.**
