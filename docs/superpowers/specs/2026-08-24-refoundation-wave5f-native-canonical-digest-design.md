# Refoundation Epoch 0 — Wave 5F Native Canonical Digest Design

## Status
Implementation design for the next stacked tranche after the accepted Wave 5E head `e10a948894653f33c3df30091e3bd456f489bba7`.

## Objective
Move real implementation authority for `core.canonical_digest` out of the mixed historical `cogcoder.organization.types` module and into a dedicated canonical primitive module without moving, deleting, or falsely classifying the rest of the historical types surface.

Canonical owner:

- `nolane.core.canonical_digest`

Owned public primitives:

- `canonical_json`
- `canonical_digest`

Component revision:

- `core.canonical_digest`: `0.0.0 -> 0.0.1`

## Why this tranche now
The accepted Memory Fabric, Lifecycle, Retrieval, Evidence, Artifact, Organization and repository-governance code still contains direct imports of canonical digest helpers through `cogcoder.organization.types`. That makes a historical mixed schema module remain a primitive dependency of otherwise canonical code.

The Master Spec orders primitive/shared substrate migration before higher cognitive layers. Context is not yet a safe next target because it depends on multiple still-unmigrated components (`external.knowledge`, `external.skills`, `external.self_model`, `external.planning`, `external.architecture`). A bounded digest extraction removes foundational reverse dependency without broadening into those layers.

## Semantic boundary
`core.canonical_digest` consists only of deterministic canonical JSON serialization and SHA-256 content identity:

- JSON keys sorted;
- compact separators `(',', ':')`;
- UTF-8;
- `ensure_ascii=False`;
- SHA-256 hex digest over the exact canonical JSON bytes.

No identity, event, memory, context, parameter-accounting, skill or other schema classes move in this tranche.

## Compatibility contract
`cogcoder.organization.types` remains present and continues exporting `canonical_json` and `canonical_digest`, but obtains them by importing from `nolane.core.canonical_digest`.

Required identity invariant:

```python
from cogcoder.organization import types as legacy
from nolane.core import canonical_digest as canonical_module

assert legacy.canonical_json is canonical_module.canonical_json
assert legacy.canonical_digest is canonical_module.canonical_digest
```

Historical organization callers therefore keep behavior and object identity while write/implementation authority reverses toward the canonical module.

## Reverse-import boundary
After cutover, active canonical/refoundation code must not import these two primitive helpers from `cogcoder.organization.types`.

The acceptance contract scans:

- `nolane/**/*.py`
- `cogcoder/refoundation/**/*.py`

for imports that source `canonical_json` or `canonical_digest` from `cogcoder.organization.types`.

Historical compatibility modules under `cogcoder/organization` may continue importing through `types` during later tranches; they are not evidence of canonical owner reversal.

## Mixed-source provenance
`cogcoder/organization/types.py` is a mixed historical source containing many still-unmigrated schemas. Wave 5F MUST NOT set a path-level inventory destination implying that the entire file moved to `nolane/core/canonical_digest.py`.

Provenance is recorded at component/symbol authority level:

- implementation ledger: `core.canonical_digest -> nolane.core.canonical_digest`;
- legacy source: `cogcoder/organization/types.py`;
- compatibility identity tests for both functions;
- no-delete/no-move historical source guarantee.

`schemas.identity` remains explicit `legacy_internal` debt after this tranche.

## Native-debt delta
Expected accepted delta from Wave 5E:

- total non-native: `40 -> 39`;
- `legacy_internal`: `4 -> 3`;
- `compatibility_facade`: remains `28`;
- `historical_only`: remains `7`;
- `frozen_asset`: remains `1`.

No compatibility facade is retired in this wave because `core.canonical_digest` was previously `legacy_internal`, not a facade.

## TDD gates
RED must prove the current accepted state fails only because:

1. `core.canonical_digest` is not canonical-native/version `0.0.1`;
2. canonical module/package does not yet own the helpers;
3. historical functions are still locally defined rather than canonical identities;
4. active canonical/refoundation code still reverse-imports digest helpers through historical types;
5. debt remains 40 instead of 39.

Behavior tests must already pass for the canonical JSON/digest semantics once compared against the accepted historical implementation oracle.

GREEN must additionally prove:

- exact helper behavior and deterministic digest vectors;
- historical-to-canonical function identity;
- no reverse import in active canonical/refoundation namespaces;
- `types.py` still exists and its unrelated schemas remain intact;
- no false path-level whole-file migration claim;
- generated native-debt projections are fresh;
- repository quarantine remains unchanged;
- temporary write-enabled bootstrap is removed before acceptance;
- full hosted Refoundation gate succeeds on Python 3.11 and 3.13.

## Explicitly out of scope
- `schemas.identity` extraction;
- `EventKind`, `AgentRank`, `AgentStatus`, `SkillScope`, `ParameterAccounting`, `AgentIdentity`, `CognitiveEvent`, `ContextCapsule` and other types;
- Knowledge/Skills/Experience/Self-model extraction;
- Context/Planning/Architecture extraction;
- historical deletion or move;
- Neural changes.
