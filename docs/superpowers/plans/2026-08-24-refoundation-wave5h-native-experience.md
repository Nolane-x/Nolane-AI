# Refoundation Epoch 0 — Wave 5H Native Experience Implementation Plan

## Base
Exact accepted Wave-5G head: `5783e0c1e120152b30bfb0cb98b9128237e4399c`.

Branch: `refoundation/epoch0-wave5h-native-experience`.

## Goal
Make `nolane.memory.experience` the real implementation owner of the complete five-object Experience semantic unit, preserve exact historical imports, and reduce compatibility-facade debt by exactly one.

## Sequence

### 1. RED contracts
Create `tests/test_refoundation_wave5h_native_experience.py` covering:

- desired canonical status/version/write authority;
- removal from active facade registry;
- exact historical-to-canonical identity for all five symbols;
- no reverse import to `cogcoder.organization.experience`;
- exact canonical dependency imports;
- experience ownership, deterministic ID and idempotence;
- domain/summary validation;
- positive/negative attribution semantics and external verifier requirement;
- deterministic attribution ID and EvidenceRecord round-trip;
- ledger state restore and missing-experience failure;
- pinned inventory destination;
- exact debt target 37 with facade count 27.

Hosted RED is clean only when behavior tests pass against the accepted historical implementation and failures remain architecture/debt-only.

### 2. Native implementation owner
Replace the facade body of `nolane/memory/experience.py` with the accepted implementation, changing only imports to canonical dependencies:

- `nolane.organization.identity.AgentRegistry`
- `nolane.organization.events.EventLedger`
- `nolane.external_core.evidence.EvidenceRecord`
- `nolane.core.canonical_digest.canonical_digest`

Set component version `0.0.1` and retain `MIGRATED_FROM`.

### 3. Historical bridge
Replace `cogcoder/organization/experience.py` with explicit imports of all five canonical symbols and an explicit `__all__`.

### 4. Authority/provenance metadata
Using a temporary deterministic bootstrap:

- remove `external.experience` from active facades;
- add canonical-native implementation ledger record;
- advance only `external.experience` revision to 1;
- add dedicated inventory destination for historical experience file;
- update cross-wave accepted owner/version tests without freezing later waves;
- make earlier debt tests monotonic where they currently freeze Experience as a facade.

### 5. Debt materialization
Run repository audit write/check and require:

- total non-native 37;
- compatibility facade 27;
- legacy internal 2;
- historical only 7;
- frozen asset 1;
- archive index no-drift;
- bytecode hygiene clean.

Use explicit file staging only.

### 6. Cleanup gate
Add an acceptance test rejecting `.github/workflows/refoundation-wave5h-bootstrap.yml`, then delete the temporary write-enabled workflow.

### 7. Exact-head hosted acceptance
Require complete Refoundation workflow success on Python 3.11 and 3.13 through compile, dossier freshness, repository audit, all Refoundation contracts, zero-loss evidence, full organization/campaign/execution regressions and frozen Neural R2.3 metadata.

### 8. Acceptance receipt
Update PR body with exact head/run/artifact digests and mark Ready. Do not merge automatically.
