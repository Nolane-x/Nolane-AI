# Individual Evolution Part XII Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make improvement distributed, evidence-gated and reversible for all 67 permanent Nolane identities.

**Architecture:** Add universal evolution profiles, immutable experience/attribution records, and an `IndividualEvolutionControlPlane` that composes existing SkillEvolutionEngine, SelfModelRegistry, VerificationAuthority, Part-VIII AssuranceControlPlane and Part-XI runtime state. Neural production promotion stays behind Part-VIII assurance; existing primitives remain authoritative.

**Tech Stack:** Python dataclasses/enums, AgentRegistry, SkillEvolutionEngine, SelfModelRegistry, VerificationAuthority, AssuranceControlPlane, MemoryContextControlPlane, OrganizationSnapshot, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-22-individual-evolution-part12-design.md`

## Global Constraints

- Exactly 67 permanent identities must have an evolution profile and INITIAL neural lineage.
- Every identity must be `learning_capable=True` and remain below `100,000,000` physical parameters.
- Personal memory and skill namespaces remain unique and unchanged through evolution.
- Skill sharing evidence grows stronger PERSONAL -> REGIONAL -> GLOBAL.
- Dirty or self-produced evidence cannot activate learning.
- Self-model updates require clean external evidence.
- Production neural promotion must use Part-VIII assurance, not direct low-level promotion.
- Rollback restores the exact accepted predecessor.
- Specialization signature must not drift during learning.
- Longitudinal improvement requires same-regime comparable evidence.
- Parts I–XI remain regression clean.

---

### Task 1: Universal evolution identity profiles

**Files:**
- Create: `cogcoder/organization/evolution_profiles.py`
- Test: `tests/test_coding_agi_evolution_profiles.py`

**Produces:** `EvolutionProfile`, `EvolutionProfileRegistry`, `specialization_signature`.

- [ ] Write RED asserting exactly 67 profiles, unique memory/skill namespaces, valid self models, learning capability and `<100M` parameters.
- [ ] RED assert specialization signature is stable across neural/self-model version changes.
- [ ] Run focused test and confirm missing `evolution_profiles.py` causes RED.
- [ ] GREEN derive profiles dynamically from AgentRegistry + SelfModelRegistry.
- [ ] Re-run focused tests.

### Task 2: Experience and attribution ledger

**Files:**
- Create: `cogcoder/organization/experience.py`
- Test: `tests/test_coding_agi_experience_attribution.py`

**Produces:** `ExperienceOutcome`, `LearningLayer`, `ExperienceRecord`, `AttributionReceipt`, `ExperienceLedger`.

- [ ] RED each identity may record only its own experience.
- [ ] RED immutable experience id/digest and snapshot round-trip.
- [ ] RED positive attribution rejects self evidence and dirty evidence.
- [ ] RED failed/dirty evidence becomes preserved negative attribution.
- [ ] GREEN implement content-addressed experience/attribution records with event anchors.

### Task 3: Skill governance and specialization retention

**Files:**
- Create/Modify: `cogcoder/organization/individual_evolution.py`
- Test: `tests/test_coding_agi_skill_governance.py`
- Test: `tests/test_coding_agi_specialization_retention.py`

**Produces:** `SkillGovernanceReceipt`, `IndividualEvolutionControlPlane.propose_skill_from_experience`, `.attach_skill_evidence`, `.promote_skill`.

- [ ] RED candidate skill is not active knowledge.
- [ ] RED self-verifier does not count for PERSONAL.
- [ ] RED PERSONAL requires 1 clean external verifier.
- [ ] RED REGIONAL requires 2 clean external verifier identities.
- [ ] RED GLOBAL requires 3 clean external verifier identities, at least two verifier regions, and at least one verifier outside owner region.
- [ ] RED dirty evidence quarantines the skill and blocks all promotion.
- [ ] RED promotions preserve owner, content digest, role, region, external cores and namespaces.
- [ ] GREEN wrap existing SkillEvolutionEngine rather than changing primitive scope semantics.

### Task 4: Self-model evidence evolution

**Files:**
- Modify: `cogcoder/organization/individual_evolution.py`
- Test: `tests/test_coding_agi_self_model_evolution.py`

**Produces:** `SelfModelEvolutionReceipt`, `.update_self_model_competence`.

- [ ] RED producer self-evidence rejects.
- [ ] RED failed/false-accept/regression evidence rejects.
- [ ] RED clean external evidence updates bounded competence and advances self-model version.
- [ ] RED receipt records old/new versions, domain, score and evidence.
- [ ] GREEN delegate authoritative mutation to SelfModelRegistry.update_competence.

### Task 5: Neural challenger, Part-VIII assurance and exact lineage

**Files:**
- Modify: `cogcoder/organization/individual_evolution.py`
- Test: `tests/test_coding_agi_neural_challenger.py`

**Produces:** `LineageKind`, `EvolutionLineageEvent`, `NeuralChallengerRecord`, `.register_neural_challenger`, `.promote_neural_challenger`, `.rollback_neural`.

- [ ] RED INITIAL lineage exists for all 67 agents.
- [ ] RED challenger `>=100M`, failed, false-accept, regression or missing evidence remains rejected.
- [ ] RED accepted low-level challenger cannot production-promote without authorized Part-VIII promotion receipt.
- [ ] RED heldout + cross-version + multiple independent verifiers authorize production promotion through AssuranceControlPlane.
- [ ] RED promotion records immutable previous/new accepted version.
- [ ] RED rollback restores exact predecessor and appends ROLLED_BACK lineage event.
- [ ] GREEN never call `VerificationAuthority.promote_candidate` directly from production evolution path.

### Task 6: Longitudinal improvement evidence

**Files:**
- Modify: `cogcoder/organization/individual_evolution.py`
- Test: `tests/test_coding_agi_longitudinal_evolution.py`

**Produces:** `LongitudinalObservation`, `ImprovementReceipt`, `.record_observation`, `.assess_improvement`.

- [ ] RED observation requires external clean evidence and score `[0,1]`.
- [ ] RED same benchmark + same regime + strictly higher latest score can produce improvement.
- [ ] RED different regime cannot authorize improvement.
- [ ] RED latest regression/false-accept evidence blocks improvement.
- [ ] RED specialization signature must match baseline/current.
- [ ] GREEN preserve immutable observation ids/digests.

### Task 7: Runtime, snapshot and backward restore

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Test: `tests/test_coding_agi_individual_evolution_snapshot.py`

**Produces:** `OrganizationRuntime.individual_evolution` and runtime key `individual_evolution`.

- [ ] RED exact OrganizationSnapshot round-trip after experience, skill evidence, self-model update and neural lineage activity.
- [ ] RED old runtime state without `individual_evolution` restores with 67 fresh INITIAL lineage entries derived from restored registry.
- [ ] GREEN wire runtime creation/to_state/from_state additively after assurance/self_models/memory_context are available.

### Task 8: Adversarial matrix and CI

**Files:**
- Test: `tests/test_coding_agi_individual_evolution_adversarial.py`
- Create: `.github/workflows/coding-agi-individual-evolution-part12.yml`

- [ ] RED self-verification, dirty skill evidence, weak regional/global sharing, self-model inflation, >100M neural challenger, unassured production promotion, specialization drift and cross-regime improvement all fail closed.
- [ ] GREEN only through production code; do not weaken contracts.
- [ ] CI Python 3.11/3.13 runs Part XII plus all Parts I–XI organization tests.
- [ ] Capture a valid RED head before production modules exist.
- [ ] Capture exact-head GREEN on Python 3.11/3.13 and independent Parts I–XI workflows.
- [ ] Merge only with `expected_head_sha`; close Issue #140.

## CI command

```bash
python -m py_compile cogcoder/organization/*.py
python -m pytest -q \
  tests/test_coding_agi_evolution_*.py \
  tests/test_coding_agi_experience_*.py \
  tests/test_coding_agi_skill_governance.py \
  tests/test_coding_agi_specialization_retention.py \
  tests/test_coding_agi_self_model_evolution.py \
  tests/test_coding_agi_neural_challenger.py \
  tests/test_coding_agi_longitudinal_evolution.py \
  tests/test_coding_agi_individual_evolution_*.py \
  tests/test_coding_agi_memory_*.py \
  tests/test_coding_agi_context_intelligence.py \
  tests/test_coding_agi_research_*.py \
  tests/test_coding_agi_ops_*.py \
  tests/test_coding_agi_assurance_*.py \
  tests/test_coding_agi_ui_*.py \
  tests/test_coding_agi_debug_*.py \
  tests/test_coding_agi_code_claims.py \
  tests/test_coding_agi_coding_*.py \
  tests/test_coding_agi_foundation_*.py \
  tests/test_coding_agi_central_*.py \
  tests/test_coding_agi_requirements_*.py \
  tests/test_coding_agi_master_plan.py \
  tests/test_coding_agi_planning_*.py \
  tests/test_coding_agi_plan_reconciliation.py \
  tests/test_coding_agi_architecture_*.py \
  tests/test_coding_agi_integration_*.py
```

## Self-review

- Every Issue #140 acceptance gate maps to Tasks 1–8.
- No learning path silently writes another agent's identity/specialization.
- No skill promotion path relies only on primitive verifier count without excluding self-verification.
- Neural production path explicitly depends on Part VIII.
- Parameter ceiling remains strict `<100M`.
- Longitudinal evidence requires same-regime comparability.
- Backward restore is additive.
- No TODO/TBD placeholders remain.
