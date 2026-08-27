# Wave 5A Native Evidence Foundations — Implementation Plan

> Execute contract-first. Preserve all Wave-4 quarantine/no-delete invariants. Do not broaden scope into shared-type extraction.

## Goal

Move executable authority for Artifact and Verification foundations from historical `cogcoder.organization.*` implementation owners into canonical `nolane.external_core.*` modules with exact public/state/failure parity and independent `0.0.1` component versions.

## Task 1 — RED native-foundation contracts

Create `tests/test_refoundation_wave5_native_evidence_foundations.py` before production changes.

The RED contract must require:

- `external.artifacts` and `external.verification` are `canonical_native` at `0.0.1`;
- neither remains an active compatibility facade;
- legacy imports are exact aliases of canonical public classes;
- canonical classes report canonical `__module__` ownership;
- native modules do not import their historical implementation modules;
- ArtifactStore deterministic/content-addressed/state behavior is preserved;
- VerificationAuthority accept/reject/promotion/rollback/event/state behavior is preserved;
- migration census destinations remain exact;
- native debt falls from 46 to exactly 44 without changing unrelated debt classes.

Observe hosted RED before implementation.

## Task 2 — Extract native Artifact source

Replace `nolane.external_core.artifacts` facade with native definitions for:

- `ArtifactRecord`;
- `ArtifactStore`.

Preserve byte/semantic behavior of the accepted implementation, including canonical metadata JSON and sorted evidence references.

Replace `cogcoder.organization.artifacts` implementation with a compatibility bridge that imports/re-exports the canonical classes. Do not delete the path.

## Task 3 — Extract native Verification source

Replace `nolane.external_core.verification` facade with native definitions for:

- `CandidateEvaluation`;
- `PromotionReceipt`;
- `RollbackReceipt`;
- `VerificationAuthority`.

Use canonical `nolane.organization.identity.AgentRegistry` and `nolane.organization.events.EventLedger` dependencies. Retain shared `EventKind` / parameter ceiling constants from the declared shared-type compatibility surface until their own extraction wave.

Replace `cogcoder.organization.verification` with a compatibility bridge to canonical classes.

## Task 4 — Invert implementation authority metadata

Update:

- `cogcoder.refoundation.facades.build_active_facade_bindings()` to remove the two migrated facade bindings;
- `cogcoder.refoundation.implementation_status._NATIVE` to declare exact canonical modules/provenance;
- `cogcoder.refoundation.component_versions` to advance only these components to revision 1.

Do not modify unrelated component versions or status.

## Task 5 — GREEN + debt materialization

Run/require:

```text
python -m nolane.repository.audit --write
python -m nolane.repository.audit --check
python -m pytest -q tests/test_refoundation_wave5_native_evidence_foundations.py
```

Commit refreshed `CURRENT/NATIVE_DEBT.json` and `.md` only if deterministically changed by the accepted ledger. `archive/INDEX.json` must remain semantically protected; any unexpected history-index change is a blocker requiring investigation.

Expected debt delta from Wave-4 parent:

- compatibility_facade: 33 → 31;
- legacy_internal: remains 5;
- historical_only: remains 7;
- frozen_asset: remains 1;
- total: 46 → 44.

## Task 6 — Hosted full verification

On exact Wave-5A head require Python 3.11 and 3.13 success for:

- compilation;
- 67 AI dossier freshness;
- repository audit freshness;
- every `test_refoundation_*.py` contract;
- zero-loss evidence generation/upload;
- all organization/campaign/execution regressions;
- frozen Neural R2.3 metadata verification.

Historical PR workflows must remain isolated from `refoundation/*` heads.

## Task 7 — Completion evidence

Open/update the Wave-5A PR with:

- exact parent Wave-4 SHA;
- exact accepted Wave-5A head;
- hosted run ID;
- Python 3.11/3.13 success;
- component versions/status before→after;
- native debt before→after;
- exact legacy bridges and canonical modules;
- explicit no-deletion/no-serialization-broadening statement.

Only then call Wave 5A accepted for integration.