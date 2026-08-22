# Data, Infrastructure & Reliability Part IX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans or subagent-driven-development. Test-first RED contracts precede production modules.

**Goal:** Turn Data, Infrastructure and Reliability identities into evidence-grounded operational authorities with migration safety, reproducible release artifacts, adverse-condition recovery and matched-condition performance claims.

**Architecture:** Add operational profiles plus focused Data, Infrastructure and Reliability ledgers, composed by an `OperationsControlPlane` that consumes Part-VIII assurance without rewriting its truth. Runtime/context/snapshot integration remains additive and backward-compatible.

**Tech Stack:** Python dataclasses/enums, existing AgentRegistry/ArtifactStore/AuthorityGraph/EventLedger/SkillEvolution/Assurance/OrganizationSnapshot, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-22-data-infrastructure-reliability-part9-design.md`

## Global Constraints

- Exactly 12 operational identities: 4 Data + 4 Infrastructure + 4 Reliability.
- Migration changes require rollback, compatibility and validation evidence.
- Reproducible builds require matched source/dependency/toolchain/environment/command basis and identical artifact digest.
- Release candidates require rollback and observability.
- Reliability matrix requires disk/network/process/restart/duplicate/out-of-order scenarios.
- Clean recovery requires zero data loss and zero duplicate side effects.
- Performance claims require matched conditions and measured samples.
- Reliability remains distinct from Debugging.
- Part-VIII override stays override; it is never relabeled verified.
- Each of the three Chiefs performs direct bounded expert work.
- Parts I–VIII remain regression-clean.

---

### Task 1: Operational profiles and routing

**Files:**
- Create: `cogcoder/organization/operations_profiles.py`
- Test: `tests/test_coding_agi_ops_profiles.py`

**Interfaces:**
- Produces: `OperationsDomain`, `OperationsProfileRegistry`, `OperationsWorkRequest`, deterministic assignment receipt.

- [ ] RED exact 12 profiles split 4/4/4 across regions.
- [ ] RED each specialist routes to its own primary domain; Chiefs route cross-region-domain work inside their own region.
- [ ] RED profile serialization reflects current accepted neural version.
- [ ] GREEN implement dynamic profile registry without stale cached neural versions.

### Task 2: Data migration and consistency ledger

**Files:**
- Create: `cogcoder/organization/data_operations.py`
- Test: `tests/test_coding_agi_ops_data.py`

**Interfaces:**
- Produces: `MigrationPlan`, `MigrationReadinessReceipt`, `PersistenceInvariant`, `ConsistencyExercise`, `DataOperationsLedger`.

- [ ] RED migration id cannot be rebound.
- [ ] RED missing rollback, compatibility or validation evidence rejects readiness.
- [ ] RED forward/rollback artifacts must be distinct and Data-authored.
- [ ] RED persistence/cache consistency records preserve evidence and exact snapshot state.
- [ ] GREEN implement immutable records and counters.

### Task 3: Reproducible build, observability and release

**Files:**
- Create: `cogcoder/organization/infrastructure_operations.py`
- Test: `tests/test_coding_agi_ops_infrastructure.py`

**Interfaces:**
- Produces: `BuildManifest`, `BuildReproductionReceipt`, `ObservabilityBundle`, `ReleaseCandidate`, `InfrastructureOperationsLedger`.

- [ ] RED replay build with mismatched source/dependency/toolchain/environment/command basis rejects reproducibility.
- [ ] RED matched basis but changed artifact digest rejects.
- [ ] RED exact replay artifact digest passes.
- [ ] RED release without rollback or observability rejects.
- [ ] GREEN implement content-addressed operational receipts.

### Task 4: Reliability failure matrix and recovery semantics

**Files:**
- Create: `cogcoder/organization/reliability_operations.py`
- Test: `tests/test_coding_agi_ops_reliability.py`

**Interfaces:**
- Produces: `FailureScenarioKind`, `FailureExercise`, `ReliabilityMatrixReceipt`, `ReliabilityOperationsLedger`.

- [ ] RED six mandatory scenarios are exact and explicit.
- [ ] RED missing scenario rejects matrix readiness.
- [ ] RED recovered scenario with data loss or duplicate side effect remains unclean.
- [ ] RED matched workload/environment across all scenarios is required.
- [ ] GREEN implement failure injection evidence and recovery tags.

### Task 5: Matched-condition performance claims

**Files:**
- Modify: `cogcoder/organization/reliability_operations.py`
- Test: `tests/test_coding_agi_ops_performance.py`

**Interfaces:**
- Produces: `PerformanceMeasurement`, `PerformanceClaimReceipt`.

- [ ] RED zero-sample measurements reject.
- [ ] RED workload/environment mismatch rejects claim.
- [ ] RED numerically unsupported claimed improvement rejects.
- [ ] RED measured matched-condition improvement passes.
- [ ] GREEN implement deterministic measurement/claim receipts.

### Task 6: Operational readiness and Part-VIII integration

**Files:**
- Create: `cogcoder/organization/operations.py`
- Test: `tests/test_coding_agi_ops_readiness.py`

**Interfaces:**
- Consumes: Data/Infrastructure/Reliability ledgers + `AssuranceControlPlane`.
- Produces: `OperationalReadinessDisposition`, `OperationalReadinessReceipt`.

- [ ] RED Part-VIII pending/rejected subject blocks readiness.
- [ ] RED verified assurance + ready migration/build/release/reliability chain produces `READY`.
- [ ] RED explicit Central assurance override produces `READY_WITH_ASSURANCE_OVERRIDE`, never `READY`.
- [ ] RED failed migration/build/reliability receipt blocks release.
- [ ] GREEN implement recomputed coordinator; no auto-merge/deploy side effects.

### Task 7: Direct Chiefs and operational learning

**Files:**
- Test: `tests/test_coding_agi_ops_direct_work.py`
- Test: `tests/test_coding_agi_ops_learning.py`
- Modify: `cogcoder/organization/operations.py`

**Interfaces:**
- Produces: personal operational skill candidates and direct-work artifacts.

- [ ] RED Data Chief directly validates a migration + rollback chain.
- [ ] RED Infrastructure Chief directly produces a reproducible build/release chain.
- [ ] RED Reliability Chief directly executes adverse-condition recovery/performance evidence.
- [ ] RED learned operational lesson remains `SkillScope.CANDIDATE` until governed promotion.
- [ ] GREEN use ordinary `chief_direct_work` and existing SkillEvolutionEngine.

### Task 8: Runtime, context, snapshot and CI

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Modify: `cogcoder/organization/context.py`
- Test: `tests/test_coding_agi_ops_snapshot.py`
- Test: `tests/test_coding_agi_ops_context.py`
- Create: `.github/workflows/coding-agi-operations-part9.yml`

**Interfaces:**
- Produces: `runtime.operations`, region-scoped operational context and exact state restore.

- [ ] RED snapshot round-trips all Part-IX state exactly.
- [ ] RED Data/Infrastructure/Reliability contexts receive only their own private operational state digest.
- [ ] RED unrelated regions do not receive full operational private state.
- [ ] Integrate runtime additively after assurance; preserve older snapshot defaults.
- [ ] Python 3.11/3.13 workflow runs Part IX plus Parts I–VIII regressions.
- [ ] Capture valid RED then exact-head GREEN before merge.

## Self-review

Every Issue #137 acceptance gate maps to at least one explicit contract. No operational region can self-create Part-VIII verification truth. Reliability tests adverse behavior rather than merely classifying bugs. No TODO/TBD placeholders remain.
