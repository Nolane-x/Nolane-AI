# Refoundation Epoch 0 — Wave 4 Historical Authority Quarantine

## Status

Approved architecture continuation after Wave 3 AI-first authority was merged to `main`.

## Problem

Wave 1–3 established canonical present-architecture authority, but the repository still exposes historical R-series delivery notes, release/recovery manifests, old `CURRENT_*` pointers, checkpoint artifacts, legacy implementation surfaces, and many historical GitHub Actions workflows alongside current source. The remaining material is scientifically useful and often required for provenance, but its physical placement and CI behavior can still make historical state look current and can consume hosted runners during Refoundation work.

Wave 4 must make the distinction executable and auditable without deleting evidence or silently breaking historical reproduction paths.

## Design

### 4A — Authority quarantine

1. `CURRENT/` remains the only present-architecture documentation authority.
2. A machine-readable repository history index inventories every ambiguous root historical artifact and records its original path, classification, content digest, archive target, move status, and deletion prohibition.
3. A machine-readable native-debt ledger inventories every canonical component whose implementation status is not `canonical_native` so future extraction waves cannot silently forget residual facades, legacy internals, historical-only mechanisms, or frozen assets.
4. A canonical repository-audit module provides deterministic `--check` / `--write` generation for both ledgers.
5. Historical workflows that accept pull requests must fail the Wave-4 contract unless they explicitly skip `refoundation/*` PR heads. The Refoundation workflow is exempt and remains the authoritative gate.
6. No Wave-4A operation deletes historical source or evidence.

### 4B — Physical archive

Physical moves are allowed only for root historical artifacts that pass a reference audit. A move requires:

- exact source SHA/digest recorded;
- no unresolved active runtime/import dependency;
- archive target recorded before the move;
- compatibility/reproduction impact recorded;
- `delete_allowed=false` remains true in the provenance record even after relocation (the history may be moved, never discarded by this wave).

Artifacts still referenced by tests, workflows, release reproduction, checkpoint loading, or evidence code remain `quarantined_in_place` until a later migration receipt updates those references safely.

## Root historical candidate policy

A root file is an ambiguous historical candidate when its name matches one of these current Wave-4 families:

- `R<digit>...` historical R-series delivery/release/recovery/readiness/evidence material;
- `archive/root-history/legacy_weight_pointer/CURRENT_ONE_WEIGHT_*` legacy current-weight pointers;
- root `archive/root-history/legacy_current_status/CURRENT_STATUS.md` (superseded architecturally by `CURRENT/STATUS.md`);
- `archive/root-history/historical_checkpoint_pointer/CHECKPOINT_MANIFEST.json` when it is a historical checkpoint pointer rather than current architecture law.

The audit module must enumerate candidates from the filesystem, not from a hand-maintained finite list, then require complete index coverage.

## Workflow isolation policy

For every `.github/workflows/*.yml` / `*.yaml` except the dedicated Refoundation workflow:

- if the workflow does not subscribe to `pull_request`, no Refoundation-head guard is required;
- if it does subscribe to `pull_request`, its jobs must explicitly prevent execution when `github.head_ref` starts with `refoundation/`;
- existing normal PR, push, schedule, and manual behavior is otherwise preserved.

This is CI routing, not a weakening of historical scientific gates.

## Native debt policy

`CURRENT/NATIVE_DEBT.json` is generated from the implementation ledger and contains every component whose status is not `canonical_native`. It is not a claim that these components are broken; it is an explicit remaining-migration inventory. Each entry records component version, implementation status, canonical module when present, legacy sources, current write-authority flag, and notes.

## Versioning

Repository-history quarantine begins at `0.0.0`. Future modifications to this repository-governance component increment only its local `0.0.N` version. Historical R/Part numbers do not become current architecture versions.

## Zero-loss invariants

- no historical artifact is deleted;
- no accepted runtime serialization changes;
- 67 AI profiles and 134 resolved dossiers remain fresh;
- existing Wave 1–3 fingerprints/regressions remain green;
- frozen Neural R2.3 evidence remains unchanged;
- archive/index generation is deterministic and idempotent;
- native-debt coverage is exhaustive;
- Refoundation PRs no longer execute historical PR workflows.

## Acceptance

Wave 4 is accepted only after Python 3.11 and 3.13 hosted gates pass the new quarantine contracts plus all prior Refoundation, organization, campaign, execution, dossier-freshness, and Neural metadata regressions.