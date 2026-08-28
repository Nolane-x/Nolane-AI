# Native Implementation Debt

Repository quarantine component: `0.0.0`.

This file is a generated human-readable view of `CURRENT/NATIVE_DEBT.json`. It lists every canonical semantic component whose executable implementation is not yet classified `canonical_native`. It does **not** mean the component is broken or unaccepted; it makes remaining migration work impossible to hide.

## Counts

- `compatibility_facade`: 2
- `frozen_asset`: 1
- `historical_only`: 5

## Components

### `external.capability_acquisition`

- Component version: `0.0.0`
- Status: `historical_only`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: historical capability-acquisition mechanisms; extraction not yet accepted
- Notes: Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.

### `external.causal`

- Component version: `0.0.0`
- Status: `historical_only`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: historical bounded causal programs; not a current dedicated organization component
- Notes: Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.

### `external.cognitive_library`

- Component version: `0.0.0`
- Status: `historical_only`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: historical reusable cognitive mechanisms; extraction not yet accepted
- Notes: Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.

### `external.experimentation`

- Component version: `0.0.0`
- Status: `historical_only`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: historical active experimentation mechanisms; extraction not yet accepted
- Notes: Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.

### `external.operations`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.operations`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/operations.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.research`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.research`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/research.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.transfer_meta`

- Component version: `0.0.0`
- Status: `historical_only`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: historical transfer/meta-learning mechanisms; extraction not yet accepted
- Notes: Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.

### `neural.shared`

- Component version: `0.0.0`
- Status: `frozen_asset`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: model/neural-r2.3
- Notes: Accepted frozen neural asset with separate runtime adapter and checkpoint authority.

> GENERATED VIEW — update implementation authority at its canonical source and regenerate; never hand-edit this debt projection.
