# Part XV — Evaluation & Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed organization-level evaluation, claim-boundary, reproducibility and future-scaling authority on top of accepted Parts I–XIV.

**Architecture:** Add focused evaluation modules that consume accepted Part VIII, XII, XIII and XIV evidence rather than replacing them. Keep first-generation 67 identities and `<100M` production parameter accounting unchanged; >100M is only a future-experiment decision receipt.

**Tech Stack:** Python 3.11/3.13, dataclasses/enums, accepted Nolane organization primitives, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-23-evaluation-scaling-part15-design.md`

## Global Constraints
- Permanent organization remains exactly 67 identities.
- Current `PHYSICAL_PARAMETER_CEILING=100_000_000` and `ParameterAccounting` behavior remain unchanged.
- Internal/synthetic evidence never authorizes unrestricted external claims.
- Matched-budget comparisons require identical regime/task/repository/tool/budget digests.
- Positive organization superiority requires clean wins over both single-agent and flat-swarm baselines.
- Long-horizon reliability requires the complete six-scenario stress suite.
- Shared/local/unique-stored/active/logical-deployed parameter footprints are reported separately.
- Future >100M authorization never mutates production registry/model state.
- `AGI` and `FRONTIER_EQUIVALENCE` remain hard-blocked in this implementation.
- Runtime integration is additive and pre-Part-XV snapshots restore an empty evaluation layer.

---

### Task 1: Benchmark regimes and immutable evaluation observations

**Files:**
- Create: `cogcoder/organization/evaluation_regimes.py`
- Create: `cogcoder/organization/evaluation_evidence.py`
- Test: `tests/test_coding_agi_evaluation_regimes.py`
- Test: `tests/test_coding_agi_evaluation_observations.py`

**Interfaces:**
- `BenchmarkRegimeRegistry.register(...) -> BenchmarkRegime`
- `EvaluationEvidenceLedger.record_observation(...) -> EvaluationObservation`
- Enums: `BenchmarkDomain`, `EvidenceProvenanceClass`, `EvaluationMode`.

- [ ] Write RED tests proving regime IDs cannot be rebound, regime digest changes when task/repo/tool/budget/freshness/provenance changes, and provenance/fresh/heldout flags remain explicit.
- [ ] Write RED tests proving external-positive observations need a clean permanent external verifier, while internal observations remain recordable but internally labeled.
- [ ] Run `pytest -q tests/test_coding_agi_evaluation_regimes.py tests/test_coding_agi_evaluation_observations.py`; expect missing Part-XV module imports.
- [ ] Implement immutable content-addressed regimes/observations with exact `to_state()/from_state()` validation.
- [ ] Run the Task-1 tests GREEN and commit.

### Task 2: Matched-budget baselines and controlled ablations

**Files:**
- Extend: `cogcoder/organization/evaluation_evidence.py`
- Test: `tests/test_coding_agi_evaluation_baselines.py`
- Test: `tests/test_coding_agi_evaluation_ablations.py`

**Interfaces:**
- `compare_matched_budget(organization_id, baseline_id) -> MatchedBudgetComparison`
- `assess_ablation(full_id, ablation_id) -> AblationAssessment`

- [ ] Write RED tests for `ORGANIZATION` vs `SINGLE_AGENT` and `FLAT_SWARM`, rejecting mismatched regime/task-set/repo/tool/budget digests.
- [ ] Require higher score plus no worse false accepts/regressions and resource usage within common limits.
- [ ] Write RED tests for `ORGANIZATION_NO_MEMORY`, `NO_TOOLS`, `NO_SPECIALIZATION`, `NO_COORDINATION`; each must use the same regime and report score/safety/resource deltas separately.
- [ ] Implement deterministic comparison/ablation receipts and snapshot validation.
- [ ] Run Task-2 tests GREEN and commit.

### Task 3: Long-horizon stress and organization reliability

**Files:**
- Create: `cogcoder/organization/evaluation_stress.py`
- Test: `tests/test_coding_agi_evaluation_stress.py`
- Test: `tests/test_coding_agi_evaluation_continuity.py`

**Interfaces:**
- `record_stress(...) -> LongHorizonStressObservation`
- `assess_suite(observation_ids) -> StressSuiteAssessment`
- Enum `StressScenarioKind` with six required scenario classes plus task reassignment.

- [ ] Write RED cases for sleep/wake after long event gap, plan drift while asleep, stale/contradicted memory injection, stale lease after reassignment, conflict/backpressure recovery and ephemeral retirement continuation.
- [ ] Assert any missing scenario, dirty external evidence, false accept, regression, stale-context violation or contamination violation blocks reliability.
- [ ] Implement immutable stress observations and required-scenario set assessment.
- [ ] Run Task-3 tests GREEN and commit.

### Task 4: Truthful parameter footprint and future scaling authority

**Files:**
- Create: `cogcoder/organization/evaluation_parameters.py`
- Test: `tests/test_coding_agi_evaluation_parameters.py`
- Test: `tests/test_coding_agi_evaluation_scaling.py`

**Interfaces:**
- `ParameterScalingAuthority.parameter_footprint(...) -> ParameterFootprintReport`
- `propose_scaling(...) -> ScalingProposal`
- `decide_scaling(...) -> ScalingDecisionReceipt`
- Enum `ScalingDecision`: `REJECTED`, `DEFERRED`, `AUTHORIZED_FOR_FUTURE_EXPERIMENT`.

- [ ] Write RED accounting test showing 56M shared + multiple local deltas stores shared only once in `unique_stored_physical_parameters`, while `logical_deployed_parameter_footprint` is explicitly non-unique.
- [ ] Write RED test proving >100M proposal leaves registry neural version and `ParameterAccounting` untouched.
- [ ] Require candidate matched-regime delta >=0.03, no worse false accepts/regressions, compute ratio <=1.75 unless independently justified, explicit storage/latency/energy deltas, economic-capacity evidence, two cross-region permanent verifiers and one external-independent evaluator.
- [ ] Implement fail-closed proposal/decision receipts and exact arithmetic validation.
- [ ] Run Task-4 tests GREEN and commit.

### Task 5: Claim boundary and readiness rubric

**Files:**
- Create: `cogcoder/organization/evaluation_claims.py`
- Test: `tests/test_coding_agi_evaluation_claims.py`
- Test: `tests/test_coding_agi_evaluation_readiness.py`

**Interfaces:**
- `ClaimBoundaryEngine.assess(...) -> ClaimAssessment`
- `readiness(...) -> OrganizationReadinessReport`
- Enums `ClaimClass`, `ClaimDisposition`.

- [ ] Write RED tests for internal engineering progress, declared benchmark improvement, matched-budget organization superiority, long-horizon reliability, cross-domain transfer and external reproducible capability.
- [ ] Assert organization superiority needs both single-agent and flat-swarm wins.
- [ ] Assert cross-domain transfer needs at least three domains plus one heldout cross-domain regime.
- [ ] Assert `AGI` and `FRONTIER_EQUIVALENCE` are always `BLOCKED`, even with high scores, Central authority or Part-VIII override receipts.
- [ ] Implement claim assessments with explicit limitations/evidence IDs; no opaque AGI score.
- [ ] Run Task-5 tests GREEN and commit.

### Task 6: Reproducible evaluation release, control plane, runtime and snapshot

**Files:**
- Create: `cogcoder/organization/evaluation_release.py`
- Create: `cogcoder/organization/evaluation.py`
- Create: `cogcoder/organization/runtime_part14.py` as byte-for-byte accepted Part-XIV `runtime.py`.
- Modify: `cogcoder/organization/runtime.py`
- Test: `tests/test_coding_agi_evaluation_release.py`
- Test: `tests/test_coding_agi_evaluation_snapshot.py`

**Interfaces:**
- `EvaluationReleaseLedger.create_release(...) -> EvaluationReleaseReceipt`
- `record_reproduction(...) -> ReproductionReceipt`
- `EvaluationScalingControlPlane` composes Tasks 1–5.
- Runtime adds optional `evaluation_scaling` and state key only.

- [ ] Write RED release tests requiring source SHA, regime/observation/stress/claim/scaling/artifact references, protocol/environment/reproduction-command digests and independent evaluator IDs.
- [ ] Require external reproducibility only after independent reproduction binds the same release/artifact/evaluation digest.
- [ ] Write RED snapshot tests for exact rich round-trip, corrupt digest/reference/counter rejection, and old Part-XIV snapshots restoring empty evaluation state.
- [ ] Implement release ledger, façade control plane and thin runtime Part-XV wrapper over byte-identical `runtime_part14.py`.
- [ ] Run Part-XV snapshot/release tests plus Parts I–XIV organization regressions GREEN and commit.

### Task 7: Adversarial contracts, CI and exact-head integration

**Files:**
- Create: `tests/test_coding_agi_evaluation_adversarial.py`
- Create: `.github/workflows/coding-agi-evaluation-scaling-part15.yml`

**Interfaces:**
- No new production API.

- [ ] Write adversarial cases for benchmark rebind, synthetic→external laundering, self-verification, mismatched budget win, score-up-but-false-accept regression, incomplete stress suite, shared-parameter double counting, >100M prestige-only proposal, missing energy/latency/storage accounting, verifier-region collusion, fake external evaluator, AGI/frontier override attempt, corrupt release reproduction and snapshot tampering.
- [ ] Add Python 3.11/3.13 workflow: compile organization package; run `tests/test_coding_agi_evaluation_*.py` plus all prior organization regression suites I–XIV.
- [ ] Freeze tests-only RED head and open a draft PR. Confirm Parts I–XIV compile and collection fails only because Part-XV modules are absent.
- [ ] Build one GREEN candidate from the accepted RED lineage; do not weaken tests.
- [ ] Verify GREEN on Python 3.11 and 3.13.
- [ ] Verify independent Parts I–XIV workflows on the same exact GREEN SHA; R1.9/R2.0i are supplementary, known unrelated legacy bundle failures are not relabeled Part-XV failures.
- [ ] Compare `main`→branch, update PR, mark ready, merge with `expected_head_sha`, verify `main`, close Issue #143, and record that roadmap I–XV implementation is complete while AGI claims remain blocked.

## Self-review
- Spec coverage: all Issue #143 acceptance gates map to Tasks 1–7.
- Placeholder scan: no TODO/TBD or unspecified behavior remains.
- Type consistency: evaluation control plane consumes accepted `AgentRegistry`, `ArtifactStore`, Part VIII assurance, Part XII individual evolution, Part XIII coordination and Part XIV Foundry evidence without changing their authority semantics.
- Scope: this completes the organizational evaluation/scaling substrate only; actual >100M training/deployment and unrestricted AGI/frontier claims remain outside scope.