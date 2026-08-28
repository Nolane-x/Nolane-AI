# Refoundation Wave 5AM Native Evaluation Campaign Plan

**Goal:** move the complete seven-module `evaluation.campaign` cluster from historical `cogcoder.organization` executable ownership into canonical `nolane.evaluation` authority without semantic drift, reducing native debt from 11 to 10.

**Exact base:** `e30e4e9371d77ddf1c1101421cf68c87c42137b5` (Wave 5AL GREEN / current main when this plan was written).

## Invariants

- Establish a hosted RED contract before production ownership changes.
- Migrate all seven modules together: `campaign`, `campaign_repository`, `campaign_tasks`, `campaign_contamination`, `campaign_runner`, `campaign_reproduction`, `campaign_ingest`.
- Preserve exact historical object identity through explicit re-export bridges.
- Canonical modules may import only canonical `nolane.*` dependencies; no reverse `cogcoder.organization` import.
- Preserve campaign state transitions, freeze/digest behavior, repository/task manifests, contamination, run receipts, reproduction, ingestion, deterministic state serialization and round-trip behavior.
- Advance only `evaluation.campaign` from `0.0.0` to `0.0.1`.
- Retire only the active `evaluation.campaign` facade.
- Do not cut over any external component in this wave.
- `CURRENT/NATIVE_DEBT` must materialize exactly 10 remaining non-native records.
- Wave 5AL receipt must stay monotonic and permit later debt reduction.
- Final completion requires fresh exact-head Refoundation Epoch 0 CI green on Python 3.11 and 3.13.

## Public authority moved

- `campaign`: `CampaignStatus`, `EvaluationCampaign`, `EvaluationCampaignControlPlane`
- `campaign_repository`: `RepositorySnapshot`, `RepositorySnapshotRegistry`
- `campaign_tasks`: `CampaignPartition`, `CampaignTaskManifest`, `CampaignTaskRegistry`
- `campaign_contamination`: `ContaminationKind`, `ContaminationFinding`, `CampaignContaminationLedger`
- `campaign_runner`: `CampaignRunSpec`, `CampaignRunReceipt`, `CampaignRunLedger`
- `campaign_reproduction`: `CampaignReproductionPackage`, `CampaignReproductionReceipt`, `CampaignReproductionLedger`
- `campaign_ingest`: `CampaignIngestReceipt`, `CampaignIngestor`

## Dependency remap

Historical relative imports are replaced only with these canonical authorities:

- `nolane.core.canonical_digest`
- `nolane.evaluation.regimes`
- `nolane.evaluation.scaling`
- canonical `nolane.evaluation.campaign*` helper modules
- `nolane.organization.identity`
- `nolane.external_core.artifacts`
- `nolane.external_core.evidence`

## Tasks

1. Add `tests/test_refoundation_wave5am_native_evaluation_campaign.py`. Lock canonical helper-module existence/ownership, exact legacy identity for all 19 public objects, no reverse legacy imports, representative campaign state round-trip semantics, native implementation status/version/facade retirement, debt count 10, and CURRENT status receipt. Commit and prove hosted RED while the prior baseline stays green.
2. Zero-loss migrate repository/task/contamination implementations into canonical helper modules and retarget only imports.
3. Zero-loss migrate campaign/runner/reproduction/ingest implementations into canonical modules; set main component metadata to `evaluation.campaign` / `0.0.1` / historical migration source.
4. Replace all seven historical modules with explicit exact-object compatibility bridges and `__all__` declarations.
5. Advance component revision, retire the campaign facade, grant canonical-native implementation authority, and update exact accepted revision/native/write-authority oracles.
6. Materialize `CURRENT/NATIVE_DEBT.json` + `.md` to 10 records, add Wave 5AM status receipt, and make predecessor debt assertions monotonic if required.
7. Run fresh exact-head CI. On any failure use systematic debugging and fix root cause without weakening the contracts. After both Python lanes are green, update the PR with RED/final evidence and mark ready for review.