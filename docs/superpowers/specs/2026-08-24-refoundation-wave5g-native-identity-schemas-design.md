# Refoundation Epoch 0 — Wave 5G Native Identity Schemas Design

## Status
Implementation design for the next stacked tranche after accepted Wave 5F head `49dc99908d4ff55b7f75928f688d62058f887730`.

## Objective
Move implementation authority for `schemas.identity` out of the mixed historical `cogcoder.organization.types` module into a dedicated canonical schema package while retaining the historical module as an exact compatibility bridge.

Canonical owner:

- `nolane.schemas.identity`

Owned public primitives:

- `PHYSICAL_PARAMETER_CEILING`
- `AgentRank`
- `AgentStatus`
- `ParameterAccounting`
- `AgentIdentity`

Component revision:

- `schemas.identity`: `0.0.0 -> 0.0.1`

## Why these five objects form one semantic unit
`AgentIdentity` embeds `AgentRank`, `AgentStatus`, and `ParameterAccounting`. `ParameterAccounting` enforces the first-generation `PHYSICAL_PARAMETER_CEILING`. Splitting any one of these back to `cogcoder.organization.types` would leave a hidden reverse dependency inside the canonical identity schema.

`evaluation.parameters` does not own `ParameterAccounting`; it owns evaluation-specific footprint/proposal/decision authority. Therefore the small `ParameterAccounting` value object and the physical ceiling it enforces belong to the identity schema substrate.

The component description also mentions namespace schemas. In the accepted implementation, memory/skill namespaces are validated non-empty fields on `AgentIdentity`; there is no separate namespace class to migrate.

## Explicit non-members
The following neighboring objects remain in historical mixed types and are not promoted by this tranche:

- `SkillScope`
- `EventKind`
- `CognitiveEvent`
- `ContextCapsule`
- memory/evidence aliases already bridged to their own canonical owners

No claim is made that all of `cogcoder/organization/types.py` has migrated.

## Compatibility contract
`cogcoder.organization.types` remains present. It imports the five identity primitives from `nolane.schemas.identity` and exports those exact objects.

Required identity invariants include:

```python
from cogcoder.organization import types as legacy
from nolane.schemas import identity as canonical

assert legacy.AgentRank is canonical.AgentRank
assert legacy.AgentStatus is canonical.AgentStatus
assert legacy.ParameterAccounting is canonical.ParameterAccounting
assert legacy.AgentIdentity is canonical.AgentIdentity
assert legacy.PHYSICAL_PARAMETER_CEILING == canonical.PHYSICAL_PARAMETER_CEILING
```

## Behavioral parity
Wave 5G preserves:

- exact enum values;
- non-negative integer parameter accounting;
- bool rejection for parameter counts;
- total physical parameters strictly below 100,000,000;
- state round-trip;
- all permanent identity non-empty field requirements;
- required cognitive capability and authority floors;
- learning-capable invariant;
- Central/Chief direct-work rules;
- Central chief-parent prohibition;
- Regional Chief self-chief invariant;
- status defaults;
- all namespace/task/checkpoint/self-model/version fields and state defaults.

## Reverse-import boundary
After cutover, active canonical/refoundation code must not import any of the five identity primitives from `cogcoder.organization.types`.

Acceptance scans:

- `nolane/**/*.py`
- `cogcoder/refoundation/**/*.py`

Historical `cogcoder.organization` modules may continue importing through the compatibility bridge until their own owner tranches are accepted.

## Mixed-source provenance
`cogcoder/organization/types.py` remains a mixed source containing event/context/skill schemas. Wave 5G MUST NOT add a path-level destination that implies the entire file moved to `nolane/schemas/identity.py`.

Provenance is component/symbol-level through:

- implementation ledger `schemas.identity -> nolane.schemas.identity`;
- legacy source `cogcoder/organization/types.py`;
- exact object identity parity tests;
- retained historical source;
- no false whole-file canonical destination.

## Native-debt delta
Expected accepted delta from Wave 5F:

- total non-native: `39 -> 38`;
- `legacy_internal`: `3 -> 2`;
- `compatibility_facade`: remains `28`;
- `historical_only`: remains `7`;
- `frozen_asset`: remains `1`.

The two expected remaining legacy-internal records are `external.coding.claims` and `external.coding.patches`.

## TDD acceptance
RED must first prove accepted historical behavior and fail only on missing canonical owner/version/identity, reverse imports, and debt.

GREEN must prove:

- canonical ownership/version `0.0.1`;
- exact historical bridge identity;
- behavioral/state parity;
- active canonical/refoundation reverse-import count zero for all five primitives;
- `organization.identity` consumes canonical schemas;
- historical mixed source remains present and unrelated symbols remain there;
- no false whole-file destination;
- native debt exactly 38 with expected category counts;
- no tracked Python bytecode;
- no temporary write-enabled Wave-5G workflow at acceptance;
- full hosted Refoundation workflow green on Python 3.11 and 3.13.

## Out of scope
- event schema extraction;
- context schema extraction;
- skill schema extraction;
- Knowledge/Skills/Experience/Self-model implementation migration;
- Context/Planning/Architecture migration;
- evaluation parameter authority migration;
- historical source deletion/move;
- Neural changes.
