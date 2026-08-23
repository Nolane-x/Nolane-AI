# Real-Repository Evaluation Campaign Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic post-roadmap campaign harness that freezes real-repository tasks, records fair baseline/organization runs, derives Part-XV observations, and packages independent reproduction evidence without changing claim or neural authority.

**Architecture:** The campaign layer is an evidence producer over Part XV, not a competing judge. Focused immutable ledgers own repository snapshots, tasks/splits, run receipts, ingestion/reproduction, while a small façade manages lifecycle and runtime snapshot integration.

**Tech Stack:** Python 3.11/3.13, dataclasses/enums, existing `canonical_digest`, `ArtifactStore`, `EvaluationScalingControlPlane`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-23-real-repository-evaluation-campaign-design.md`

## Global Constraints
- Never mutate neural versions, model weights, or first-generation parameter accounting.
- Never unlock `AGI` or `FRONTIER_EQUIVALENCE` claim classes.
- Part XV remains the sole comparison/claim/scaling authority.
- Frozen campaign inputs are immutable and content-addressed.
- Heldout contamination fails closed.
- Real repository revisions must be exact immutable digests, never branch names.
- All new state must round-trip exactly and pre-campaign snapshots restore an empty campaign layer.
- Python 3.11 and 3.13 must pass campaign tests plus Parts I–XV regressions.

---

### Task 1: Repository snapshots and task manifests

**Files:**
- Create: `cogcoder/organization/campaign_repository.py`
- Create: `cogcoder/organization/campaign_tasks.py`
- Test: `tests/test_coding_agi_campaign_tasks_repository.py`

**Interfaces:**
- Produces `RepositorySnapshotRegistry`, `CampaignTaskRegistry`, `CampaignPartition`, `CampaignTaskManifest`.
- Consumes `canonical_digest`, `BenchmarkDomain`, `EvaluationMode`.

- [ ] Write failing tests for exact revision requirements, id rebinding, content digests and partition immutability.
- [ ] Run the tests and confirm missing-module RED.
- [ ] Implement immutable registries and frozen partition semantics.
- [ ] Run tests to GREEN.
- [ ] Commit.

### Task 2: Campaign lifecycle and freeze contract

**Files:**
- Create: `cogcoder/organization/campaign.py`
- Test: `tests/test_coding_agi_campaign_lifecycle.py`

**Interfaces:**
- Produces `CampaignStatus`, `EvaluationCampaign`, `EvaluationCampaignControlPlane`.
- Consumes Task 1 registries.

- [ ] Write failing tests for DRAFT→FROZEN→RUNNING→EVIDENCE_READY→REPRODUCING→COMPLETE and terminal fail states.
- [ ] Confirm RED.
- [ ] Implement forward-only lifecycle and freeze digest.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 3: Runner specifications and immutable run receipts

**Files:**
- Create: `cogcoder/organization/campaign_runner.py`
- Test: `tests/test_coding_agi_campaign_runner.py`

**Interfaces:**
- Produces `CampaignRunSpec`, `CampaignRunReceipt`, `CampaignRunLedger`.
- Consumes frozen campaign/task/repository data and Part-XV `EvaluationMode`.

- [ ] Write RED tests preventing arbitrary score injection, duplicate run rebinding, post-freeze mismatch and unsupported modes.
- [ ] Confirm RED.
- [ ] Implement run specs/receipts with task-level pass/failure and resource counters only.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 4: Heldout contamination firewall

**Files:**
- Create: `cogcoder/organization/campaign_contamination.py`
- Test: `tests/test_coding_agi_campaign_contamination.py`

**Interfaces:**
- Produces `ContaminationFinding`, `CampaignContaminationLedger`.
- Consumes frozen partition/task manifests and evidence/training refs.

- [ ] Write RED tests for heldout refs leaking into training/distillation inputs and for non-heldout safe refs.
- [ ] Confirm RED.
- [ ] Implement deterministic contamination findings and quarantine flag.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 5: Deterministic Part-XV ingestion

**Files:**
- Create: `cogcoder/organization/campaign_ingest.py`
- Test: `tests/test_coding_agi_campaign_ingest.py`

**Interfaces:**
- Produces `CampaignIngestReceipt`, `CampaignIngestor`.
- Consumes Part-XV `BenchmarkRegimeRegistry` and `EvaluationEvidenceLedger`.

- [ ] Write RED tests deriving task_count/pass_count/score/resources from run receipts; reject incomplete modes, missing artifacts, contaminated heldout, evaluator spoofing and mismatched budgets.
- [ ] Confirm RED.
- [ ] Implement regime creation/reuse plus deterministic observation recording.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 6: Reproduction package and independent receipt

**Files:**
- Create: `cogcoder/organization/campaign_reproduction.py`
- Test: `tests/test_coding_agi_campaign_reproduction.py`

**Interfaces:**
- Produces `CampaignReproductionPackage`, `CampaignReproductionReceipt`, `CampaignReproductionLedger`.
- Consumes campaign freeze digest, Part-XV observation ids and artifact digests.

- [ ] Write RED tests for tampering, internal-agent evaluator spoofing and digest mismatch.
- [ ] Confirm RED.
- [ ] Implement package/receipt binding and independent evaluator requirements.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 7: Runtime integration, snapshot, CI and full regression

**Files:**
- Create: `cogcoder/organization/runtime_part15.py` as byte-identical accepted Part-XV runtime.
- Modify: `cogcoder/organization/runtime.py` to add `evaluation_campaign` only.
- Test: `tests/test_coding_agi_campaign_snapshot.py`
- Test: `tests/test_coding_agi_campaign_adversarial.py`
- Create: `.github/workflows/coding-agi-evaluation-campaign.yml`

**Interfaces:**
- `OrganizationRuntime.evaluation_campaign` is an `EvaluationCampaignControlPlane` bound to existing `evaluation_scaling` and artifacts.

- [ ] Write snapshot/backward/adversarial RED tests.
- [ ] Confirm complete RED on Python 3.11/3.13 with Parts I–XV compiling cleanly.
- [ ] Implement runtime façade and exact state restore.
- [ ] Run campaign + Parts I–XV regressions on Python 3.11 and 3.13.
- [ ] Run independent Parts I–XV workflows on the exact candidate SHA.
- [ ] Compare branch to main; verify no neural/parameter/claim-authority mutation.
- [ ] Merge exact head only after all gates are green.
