# Refoundation Epoch 0 — Wave 5F Native Canonical Digest Implementation Plan

## Base
Exact accepted Wave 5E head: `e10a948894653f33c3df30091e3bd456f489bba7`.

Stacked branch: `refoundation/epoch0-wave5f-native-canonical-digest`.

## Goal
Make `nolane.core.canonical_digest` the real implementation owner of `canonical_json` and `canonical_digest`, preserve exact historical import identity through `cogcoder.organization.types`, remove active canonical/refoundation reverse imports to the historical owner, and reduce native debt by exactly one legacy-internal component.

## Execution sequence

### 1. Establish RED contracts
Create `tests/test_refoundation_wave5f_native_canonical_digest.py` covering:

- `core.canonical_digest` status/version/write authority;
- canonical package/module existence and public exports;
- exact historical-to-canonical function identity;
- deterministic canonical JSON vectors and SHA-256 digest vectors;
- Unicode/non-ASCII behavior;
- map-order invariance and array-order sensitivity;
- no direct `canonical_json`/`canonical_digest` imports from `cogcoder.organization.types` in `nolane/**/*.py` and `cogcoder/refoundation/**/*.py`;
- historical `types.py` remains present with unrelated schema symbols still available;
- no false whole-file canonical destination claim for mixed `types.py`;
- exact expected debt delta `40 -> 39`, with `legacy_internal 4 -> 3` and all other debt categories unchanged.

Run hosted Refoundation CI before production changes. RED is clean only if behavior vectors pass and failures are limited to authority/module/import/debt conditions.

### 2. Create canonical primitive owner
Create:

- `nolane/core/__init__.py`
- `nolane/core/canonical_digest.py`

The module owns only:

- `canonical_json(value)`;
- `canonical_digest(value)`.

Do not move unrelated schemas.

### 3. Reverse the historical implementation edge
Edit `cogcoder/organization/types.py`:

- remove local `hashlib` dependency if no longer needed elsewhere;
- import `canonical_json` and `canonical_digest` from `nolane.core.canonical_digest`;
- remove the two local function definitions;
- preserve all unrelated types/classes exactly.

### 4. Remove active reverse imports
For every active file under:

- `nolane/`;
- `cogcoder/refoundation/`;

that imports either helper from `cogcoder.organization.types`, rewrite only those helper imports to `nolane.core.canonical_digest`.

If an import line also contains unrelated historical types, split the import so only the digest helpers move. Do not migrate adjacent schema dependencies opportunistically.

### 5. Advance component authority metadata
Update:

- `cogcoder/refoundation/component_versions.py`: `core.canonical_digest = 1`;
- `cogcoder/refoundation/implementation_status.py`: add canonical-native record pointing to `nolane.core.canonical_digest`, with legacy source `cogcoder/organization/types.py`;
- keep `schemas.identity` legacy-internal;
- update cross-wave accepted-version/native-owner tests without freezing later tranches.

Do not add a path-level inventory mapping from the entire mixed `types.py` file to `nolane/core/canonical_digest.py`.

### 6. Regenerate deterministic debt projections
Use `python -m nolane.repository.audit --write` in a temporary branch-scoped bootstrap workflow.

Hard gates before commit:

- `archive/INDEX.json` has no diff;
- repository audit is fresh;
- Wave 5F targeted contracts pass;
- total non-native is 39;
- compatibility facade remains 28;
- historical-only remains 7;
- frozen asset remains 1;
- legacy-internal becomes 3.

### 7. Cleanup RED
Add a contract that rejects the temporary Wave 5F write-enabled bootstrap workflow.

Confirm it fails only while bootstrap exists, then delete the workflow.

### 8. Hosted acceptance
On the exact post-cleanup head, require the full `Nolane-AI Refoundation Epoch 0` workflow to succeed on both Python 3.11 and Python 3.13 through:

- compile;
- 67/67 dossier freshness;
- repository quarantine audit freshness;
- all Refoundation contracts;
- zero-loss evidence generation/upload;
- all organization/campaign/execution regressions;
- frozen Neural R2.3 metadata checks.

### 9. Acceptance receipt
Only after exact-head hosted green:

- update PR body with exact accepted head/run IDs/debt delta/artifact digests;
- mark PR Ready for review;
- do not merge automatically.

## Rollback
The stacked branch can be abandoned without affecting Wave 5E. Historical imports remain available throughout because `cogcoder.organization.types` is retained as a bridge. No historical file deletion or move is permitted in this wave.
