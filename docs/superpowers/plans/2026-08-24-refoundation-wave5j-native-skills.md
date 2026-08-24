# Refoundation Epoch 0 — Wave 5J Native Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Native-cut over the complete Skills semantic owner, including `SkillScope`, while preserving historical behavior and exact compatibility identities.

**Architecture:** `nolane.memory.skills` becomes the only executable Skills authority and depends only on canonical Evidence + digest primitives. `cogcoder.organization.evolution` and `cogcoder.organization.types.SkillScope` become bridges; repository authority/version/facade/inventory/debt metadata is updated only after RED proves behavior parity.

**Tech Stack:** Python 3.11/3.13, dataclasses, Enum, pytest, GitHub Actions, repository audit projections.

**Spec:** `docs/superpowers/specs/2026-08-24-refoundation-wave5j-native-skills-design.md`

## Global Constraints

- Parent must remain exact accepted Wave-5I head `9423b5c6e7c0a4b821c44a78e300a4dd4855b5eb`.
- No historical file deletion or move.
- Canonical Skills must not execute imports from `cogcoder.organization.evolution` or `cogcoder.organization.types`.
- `cogcoder.organization.types` remains a mixed historical module and must not receive a whole-file Skills destination.
- Preserve skill proposal, evidence, promotion, quarantine, visibility and state semantics exactly.
- Target native debt is exactly 35: facade 25, legacy internal 2, historical only 7, frozen asset 1.
- Temporary write-carrier workflows must be deleted before acceptance.
- Acceptance requires exact post-cleanup hosted green on Python 3.11 and 3.13; never auto-merge.

---

### Task 1: RED authority and behavior contracts

**Files:**
- Create: `tests/test_refoundation_wave5j_native_skills.py`

**Interfaces:**
- Consumes: historical `cogcoder.organization.evolution` and `cogcoder.organization.types.SkillScope`.
- Produces: executable acceptance contract for `nolane.memory.skills`.

- [ ] **Step 1:** Add tests for canonical status/version, facade retirement, exact object identity, AST reverse-import absence, deterministic proposal identity, evidence rebinding, promotion thresholds, quarantine, visibility, state restore, inventory provenance, mixed-types non-conflation and debt 35.
- [ ] **Step 2:** Run hosted Refoundation CI on the RED head.
- [ ] **Step 3:** Require behavior/state tests to pass while only not-yet-cutover architecture/debt assertions fail.

### Task 2: Move executable Skills authority

**Files:**
- Modify: `nolane/memory/skills.py`
- Modify: `cogcoder/organization/evolution.py`
- Modify: `cogcoder/organization/types.py`

**Interfaces:**
- Consumes: `nolane.external_core.evidence.EvidenceRecord`, `nolane.core.canonical_digest.canonical_digest`.
- Produces: `SkillScope`, `SkillRecord`, `SkillEvolutionEngine` owned by `nolane.memory.skills`.

- [ ] **Step 1:** Replace the canonical facade with the historical implementation rewritten to canonical imports and `COMPONENT_VERSION = "0.0.1"`.
- [ ] **Step 2:** Replace `cogcoder.organization.evolution` with an explicit bridge preserving `SkillScope`, `SkillRecord`, `SkillEvolutionEngine`, plus historical dependency-name availability for `EvidenceRecord` and `canonical_digest`.
- [ ] **Step 3:** Remove the local `SkillScope` enum definition from mixed `types.py` and import the exact canonical `SkillScope` object instead.
- [ ] **Step 4:** Run focused Wave-5J contracts and all existing skill/evolution regressions.

### Task 3: Cut over authority, provenance and debt

**Files:**
- Modify: `cogcoder/refoundation/facades.py`
- Modify: `cogcoder/refoundation/component_versions.py`
- Modify: `cogcoder/refoundation/implementation_status.py`
- Modify: `cogcoder/refoundation/inventory.py`
- Modify: `tests/test_refoundation_component_versions.py`
- Modify: `tests/test_refoundation_implementation_status.py`
- Modify stale earlier-wave assertions only when they freeze Skills as permanently unmigrated.
- Regenerate: `CURRENT/NATIVE_DEBT.json`
- Regenerate: `CURRENT/NATIVE_DEBT.md`

**Interfaces:**
- Produces: `external.skills` as `CANONICAL_NATIVE`, version `0.0.1`, write authority true, debt 35.

- [ ] **Step 1:** Remove only `external.skills` from active facades.
- [ ] **Step 2:** Advance only `external.skills` local revision to 1.
- [ ] **Step 3:** Register native implementation owner `nolane.memory.skills` with historical source `cogcoder/organization/evolution.py`.
- [ ] **Step 4:** Pin only `evolution.py → nolane/memory/skills.py` in native destinations; do not map whole `types.py` to Skills.
- [ ] **Step 5:** Extend wave-independent accepted revision/native sets.
- [ ] **Step 6:** Run `python -m nolane.repository.audit --write`, prove `archive/INDEX.json` no-drift, then `--check`.
- [ ] **Step 7:** Require exactly 35 non-native components with facade 25 / legacy internal 2 / historical only 7 / frozen asset 1.

### Task 4: Cleanup and exact-head acceptance

**Files:**
- Create: `tests/test_refoundation_wave5j_bootstrap_cleanup.py`
- Delete any `.github/workflows/refoundation-wave5j-*.yml` temporary carrier before final acceptance.

- [ ] **Step 1:** Add cleanup contract asserting no temporary Wave-5J carrier exists.
- [ ] **Step 2:** Delete temporary carrier and verify branch head.
- [ ] **Step 3:** Run complete `Nolane-AI Refoundation Epoch 0` hosted matrix on exact clean head for Python 3.11 and 3.13.
- [ ] **Step 4:** Require compile, 67/67 dossier freshness, repository audit, all Refoundation contracts, zero-loss evidence, full organization/campaign/execution regressions and frozen Neural R2.3 metadata to succeed on both runtimes.
- [ ] **Step 5:** Record exact head, run ID and both artifact digests in the PR; mark Ready for Review only after all gates are green. Do not merge.
