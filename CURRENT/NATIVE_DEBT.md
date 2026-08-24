# Native Implementation Debt

Repository quarantine component: `0.0.0`.

This file is a generated human-readable view of `CURRENT/NATIVE_DEBT.json`. It lists every canonical semantic component whose executable implementation is not yet classified `canonical_native`. It does **not** mean the component is broken or unaccepted; it makes remaining migration work impossible to hide.

## Counts

- `compatibility_facade`: 28
- `frozen_asset`: 1
- `historical_only`: 7
- `legacy_internal`: 4

## Components

### `core.canonical_digest`

- Component version: `0.0.0`
- Status: `legacy_internal`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/types.py
- Notes: Semantic component is active/internal or composition-only, but no dedicated canonical source module is accepted yet.

### `evaluation.campaign`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.evaluation.campaign`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/campaign.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `evaluation.claims`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.evaluation.claims`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/evaluation_claims.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `evaluation.evidence`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.evaluation.evidence`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/evaluation_evidence.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `evaluation.parameters`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.evaluation.parameters`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/evaluation_parameters.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `evaluation.regimes`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.evaluation.regimes`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/evaluation_regimes.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `evaluation.release`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.evaluation.release`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/evaluation_release.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `evaluation.scaling`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.evaluation.scaling`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/evaluation.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `evaluation.stress`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.evaluation.stress`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/evaluation_stress.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.architecture`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.architecture`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/architecture.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.assurance`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.assurance`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/assurance.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

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

### `external.coding.claims`

- Component version: `0.0.0`
- Status: `legacy_internal`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/coding_claims.py
- Notes: Semantic component is active/internal or composition-only, but no dedicated canonical source module is accepted yet.

### `external.coding.control`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.coding`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/coding.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.coding.patches`

- Component version: `0.0.0`
- Status: `legacy_internal`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/coding.py
- Notes: Semantic component is active/internal or composition-only, but no dedicated canonical source module is accepted yet.

### `external.cognitive_library`

- Component version: `0.0.0`
- Status: `historical_only`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: historical reusable cognitive mechanisms; extraction not yet accepted
- Notes: Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.

### `external.context`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.memory.context`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/memory_context.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.debugging`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.debugging`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/debugging.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.epistemic`

- Component version: `0.0.0`
- Status: `historical_only`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: historical R2 mechanisms; no dedicated current organization implementation
- Notes: Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.

### `external.execution.control`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.execution`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/execution.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.execution.executor`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.execution_executor`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/execution_tools.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.execution.workspace`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.execution_workspace`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/execution_workspace.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.experience`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.memory.experience`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/experience.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.experimentation`

- Component version: `0.0.0`
- Status: `historical_only`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: historical active experimentation mechanisms; extraction not yet accepted
- Notes: Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.

### `external.individual_evolution`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.individual_evolution`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/individual_evolution.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.integration`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.integration`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/integration.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.invokable_cores`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.invokable`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/external_core.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.knowledge`

- Component version: `0.0.0`
- Status: `historical_only`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: historical R2 mechanisms; no dedicated current organization implementation
- Notes: Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.

### `external.operations`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.operations`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/operations.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.planning`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.planning`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/planning.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.requirements`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.requirements`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/requirements.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.research`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.research`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/research.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.self_model`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.self_model`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/self_model.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.skills`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.memory.skills`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/evolution.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `external.transfer_meta`

- Component version: `0.0.0`
- Status: `historical_only`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: historical transfer/meta-learning mechanisms; extraction not yet accepted
- Notes: Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.

### `external.ui_ux`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.external_core.ui_ux`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/ui.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `neural.inference_bridge`

- Component version: `0.0.0`
- Status: `compatibility_facade`
- Canonical module: `nolane.neural.inference_bridge`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/execution_inference.py
- Notes: Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.

### `neural.shared`

- Component version: `0.0.0`
- Status: `frozen_asset`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: model/neural-r2.3
- Notes: Accepted frozen neural asset with separate runtime adapter and checkpoint authority.

### `schemas.identity`

- Component version: `0.0.0`
- Status: `legacy_internal`
- Canonical module: `none`
- Canonical write authority: `false`
- Legacy/provenance sources: cogcoder/organization/types.py
- Notes: Semantic component is active/internal or composition-only, but no dedicated canonical source module is accepted yet.

> GENERATED VIEW — update implementation authority at its canonical source and regenerate; never hand-edit this debt projection.
