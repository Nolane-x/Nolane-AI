# Research Intelligence Part X Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans or subagent-driven-development. Test-first RED contracts precede production modules.

**Goal:** Build evidence-grounded Research Intelligence with distinct researchers, provenance/freshness/contradiction handling, synthesis, and independently verified engineering handoffs.

**Architecture:** Add `research_profiles.py`, `research_provenance.py`, and `research.py`; wire `runtime.research` and region-private context additively. Part VIII remains the independent verifier for authorizing research handoffs.

**Tech Stack:** Python dataclasses/enums, AgentRegistry, ArtifactStore, AssuranceControlPlane, SkillEvolutionEngine, OrganizationSnapshot, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-22-research-intelligence-part10-design.md`

## Global Constraints

- Exactly four permanent Research identities.
- Research domains remain operationally distinct.
- Every finding retains source locator, retrieval text, source version, mode, quality and evidence refs.
- Current external and internal/offline evidence remain distinguishable.
- Freshness is explicit and logical-epoch based.
- Live contradictory facts do not silently become shared truth.
- Repository archaeology requires repository-history provenance.
- Decision-authorizing handoff requires Part-VIII `VERIFIED`; `OVERRIDDEN` is insufficient.
- Research Chief performs direct multi-domain synthesis.
- Parts I–IX remain regression clean.

---

### Task 1: Research profiles and routing

**Files:**
- Create: `cogcoder/organization/research_profiles.py`
- Test: `tests/test_coding_agi_research_profiles.py`

**Interfaces:** `ResearchDomain`, `ResearchProfileRegistry`, `ResearchWorkRequest`, deterministic assignment receipt.

- [ ] RED exact four profiles.
- [ ] RED repository/docs/prior-art specialists are primary for distinct domains; Chief primary for cross research.
- [ ] RED request may originate from any registered region.
- [ ] RED profile serialization reflects current accepted neural version.
- [ ] GREEN implement dynamic registry.

### Task 2: Source provenance and findings

**Files:**
- Create: `cogcoder/organization/research_provenance.py`
- Test: `tests/test_coding_agi_research_provenance.py`

**Interfaces:** `EvidenceMode`, `SourceKind`, `SourceQuality`, `ResearchSource`, `ResearchFinding`, `ResearchProvenanceLedger`.

- [ ] RED source stores locator/retrieval/version/mode/quality/evidence/digest.
- [ ] RED source id/finding id cannot be rebound.
- [ ] RED non-Research author rejects.
- [ ] RED repository archaeology without repository-history source rejects.
- [ ] RED docs/API and prior-art source-kind mismatches reject.
- [ ] RED internal/offline and current-external remain different after snapshot restore.
- [ ] GREEN implement logical epoch and freshness.

### Task 3: Claim assessment and contradictions

**Files:**
- Modify: `cogcoder/organization/research_provenance.py`
- Test: `tests/test_coding_agi_research_claims.py`

**Interfaces:** `ClaimDisposition`, `ClaimAssessment`, `ContradictionResolution`.

- [ ] RED live incompatible values produce `CONTRADICTED`.
- [ ] RED expired source produces `STALE`.
- [ ] RED no findings produces `UNKNOWN`.
- [ ] RED explicit Research-Chief resolution preserves all competing finding ids.
- [ ] RED lower-quality selected finding cannot override every higher-quality live alternative.
- [ ] GREEN implement explicit resolution ledger.

### Task 4: Synthesis and content-addressed artifacts

**Files:**
- Create: `cogcoder/organization/research.py`
- Test: `tests/test_coding_agi_research_synthesis.py`

**Interfaces:** `ResearchSynthesis`, `ResearchControlPlane.synthesize`.

- [ ] RED stale finding makes synthesis non-shareable.
- [ ] RED unresolved contradiction makes synthesis non-shareable.
- [ ] RED resolved fresh multi-source synthesis is shareable and has content-addressed artifact.
- [ ] RED synthesis preserves source evidence modes and limitations.
- [ ] GREEN implement immutable synthesis records.

### Task 5: Engineering handoff and Part-VIII checking

**Files:**
- Modify: `cogcoder/organization/research.py`
- Test: `tests/test_coding_agi_research_handoff.py`

**Interfaces:** `ResearchHandoff`, `ResearchHandoffDisposition`.

- [ ] RED informative handoff requires shareable synthesis but no assurance.
- [ ] RED authorizing handoff with Part-VIII pending/rejected rejects.
- [ ] RED Part-VIII override remains insufficient for independent research check.
- [ ] RED exactly verified synthesis artifact permits authorizing handoff to planning/architecture/coding.
- [ ] GREEN implement handoff receipts without mutating target authority state.

### Task 6: Direct Research Chief and learning

**Files:**
- Test: `tests/test_coding_agi_research_direct_work.py`
- Test: `tests/test_coding_agi_research_learning.py`
- Modify: `cogcoder/organization/research.py`

- [ ] RED Chief directly synthesizes at least two research domains.
- [ ] RED synthesis carries limitations and provenance.
- [ ] RED Chief completes ordinary `chief_direct_work` with synthesis artifact.
- [ ] RED personal lesson remains `SkillScope.CANDIDATE` until governed promotion.
- [ ] GREEN reuse existing direct-work/evolution primitives.

### Task 7: Runtime, context, snapshot, CI

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Modify: `cogcoder/organization/context.py`
- Test: `tests/test_coding_agi_research_snapshot_context.py`
- Create: `.github/workflows/coding-agi-research-part10.yml`

- [ ] RED exact snapshot round trip.
- [ ] RED Research identities receive `research-state`.
- [ ] RED non-Research identities do not receive private Research ledger.
- [ ] GREEN additive runtime restore defaults.
- [ ] Python 3.11/3.13 workflow runs Part X plus Parts I–IX organization regressions.
- [ ] Capture valid RED and exact-head GREEN before merge.

## Self-review

Every Issue #138 acceptance gate maps to an explicit contract. No source-less shared truth path exists. No authorizing research handoff bypasses Part VIII. No TODO/TBD placeholders remain.
