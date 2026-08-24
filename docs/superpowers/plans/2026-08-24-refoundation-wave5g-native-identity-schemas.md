# Refoundation Epoch 0 — Wave 5G Native Identity Schemas Implementation Plan

## Base
Exact accepted Wave 5F head: `49dc99908d4ff55b7f75928f688d62058f887730`.

Branch: `refoundation/epoch0-wave5g-native-identity-schemas`.

## Goal
Make `nolane.schemas.identity` the real implementation owner of the accepted permanent identity schema unit while preserving exact historical imports and mixed-source provenance.

## Sequence

### 1. RED contracts
Create `tests/test_refoundation_wave5g_native_identity_schemas.py` covering:

- legacy behavior of all five target primitives;
- exact enum values;
- parameter accounting validation and round-trip;
- AgentIdentity validation/defaults/round-trip;
- expected canonical status/version/write authority;
- expected canonical object ownership and historical identity bridge;
- active reverse-import scan for all target names in `nolane/` and `cogcoder/refoundation/`;
- mixed historical types source retained with `SkillScope`, `EventKind`, `CognitiveEvent`, `ContextCapsule` still available;
- no path-level whole-file destination for mixed `types.py`;
- debt expected `39 -> 38` with only legacy-internal count changing `3 -> 2`.

Run hosted CI and require behavior tests to pass before production changes.

### 2. Canonical schema package
Create:

- `nolane/schemas/__init__.py`
- `nolane/schemas/identity.py`

Move exact implementations of:

- `PHYSICAL_PARAMETER_CEILING`
- `AgentRank`
- `AgentStatus`
- `ParameterAccounting`
- `AgentIdentity`

No unrelated schema moves.

### 3. Historical bridge
Edit `cogcoder/organization/types.py` so those five names import from `nolane.schemas.identity`. Remove their local implementations while preserving all other historical symbols and imports required by remaining schemas.

### 4. Active import cutover
AST-rewrite active `nolane/**/*.py` and `cogcoder/refoundation/**/*.py` imports so target identity primitives come from `nolane.schemas.identity`. If an import also carries unrelated historical symbols, split it safely rather than broad-replacing the line.

### 5. Authority metadata
Advance only `schemas.identity` to revision 1 and add canonical-native implementation ledger record. Remove only its legacy-internal source hint.

Update cross-wave tests so prior tranches assert their own accepted owner boundaries without freezing identity schema debt forever.

Do not add a whole-file inventory destination for `cogcoder/organization/types.py`.

### 6. Deterministic debt materialization
Use one temporary write-enabled Wave-5G bootstrap, with explicit file staging only (never broad `git add nolane`/directory staging).

Before commit require:

- compile success;
- zero active reverse imports for the five identity primitives;
- `archive/INDEX.json` unchanged;
- repository audit fresh;
- targeted Wave-5G contracts green;
- no tracked Python bytecode;
- debt total 38;
- compatibility facade 28;
- historical-only 7;
- frozen asset 1;
- legacy-internal 2.

### 7. Cleanup gate
Add a test rejecting temporary Wave-5G write-enabled workflows. Confirm intended RED while bootstrap exists, then delete bootstrap.

### 8. Hosted acceptance
Exact post-cleanup head must pass the complete Refoundation workflow on Python 3.11 and 3.13 through compile, dossier freshness, repository audit, all Refoundation contracts, zero-loss bundle, full regressions and frozen Neural R2.3 metadata.

### 9. Acceptance receipt
Update PR with exact head/run/artifact digests and debt delta, mark Ready only after hosted green. Do not merge automatically.
