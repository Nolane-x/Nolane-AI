# Current Refoundation Status

Architecture generation: `A1` (Refoundation Epoch 0).

## Accepted baseline

Accepted and merged to `main`:
- Wave 1: zero-loss canonical foundation
- Wave 2: native identity/authority/events
- Wave 2b: native task-control/coordination
- Wave 2c: native Nolane Central control plane
- Wave 3: AI-first canonical authority (`CURRENT/`, `shared/`, 15 `regions/`, 67 `ai/` profiles, `nolane.ai`, and 134 generated resolved dossier views)

Wave 4 established historical-authority quarantine and the repository audit/debt machinery used by later extraction waves. Historical root R-series artifacts, old root `CURRENT_*` pointers, checkpoint provenance, and historical workflows remain evidence, but they do not outrank current authority.

## Current native-extraction lineage

The downstream Refoundation lineage is continuing semantic ownership extraction without treating historical file layout as current authority. The latest cutovers and refinements are:

- Wave 5M: `external.requirements` -> native `nolane.external_core.requirements`
- Wave 5N: `external.planning` -> native `nolane.external_core.planning`
- Wave 5O: `external.architecture` -> native `nolane.external_core.architecture`
- Wave 5P: `external.integration` -> native `nolane.external_core.integration`
- Wave 5Q: Compatibility implementation moved under `nolane.external_core.compatibility` as a native internal Architecture/Integration boundary while preserving the historical import bridge.
- Wave 5R candidate: `external.invokable_cores` -> native `nolane.external_core.invokable`
- Wave 5S candidate: `external.execution.workspace` -> native `nolane.external_core.execution_workspace`
- Wave 5T candidate: `external.coding.claims` -> native `nolane.external_core.coding_claims`
- Wave 5U prerequisite: canonical execution schemas -> `nolane.external_core.execution_types`
- Wave 5V candidate: `external.coding.patches` -> native `nolane.external_core.coding_patches`
- Wave 5W candidate: `external.execution.executor` -> native `nolane.external_core.execution_executor`
- Wave 5X prerequisite: canonical event/context schema authority -> `nolane.organization.events` + `nolane.external_core.context`
- Wave 5Y candidate: `external.context` -> native `nolane.memory.context` semantic closure
- Wave 5Z candidate: `neural.inference_bridge` -> native `nolane.neural.inference_bridge`

The core requirements-to-integration chain remains:

`Requirements -> Planning -> Architecture -> Integration`

Wave 5R opened the next dependency-safe extraction front with invokable-core schema/registry authority depending only on canonical `organization.identity`. Wave 5S moved the isolated Git-worktree execution workspace under canonical authority. Wave 5T moved exclusive source-mutation claim authority under canonical ownership. Historical `cogcoder.organization.execution_workspace` and `cogcoder.organization.code_claims` are exact-object import/provenance bridges rather than executable ownership.

Wave 5U moves the shared execution schemas (`ToolAction`, `ExecutionAction`, execution budgets/counters, inference requests, and decision receipts) from historical `cogcoder.organization.execution_types` to canonical `nolane.external_core.execution_types`, with canonical JSON/digest authority and exact historical object identity preserved. This is a prerequisite extraction rather than a semantic debt retirement: `external.execution.executor` and `external.execution.control` remain compatibility facades at that wave boundary.

Wave 5V moves patch candidates, source-scope normalization, claim coverage, patch status, tool invocation receipts and patch-ledger snapshot authority from historical `cogcoder.organization.coding_patches` to canonical `nolane.external_core.coding_patches`. The canonical patch layer depends only on canonical coding claims and canonical digest identity; historical coding-patches imports preserve exact public object identity.

Wave 5W moves the fail-closed external-core executor, content-addressed core invocation receipts, bounded filesystem/Git/search/subprocess dispatch, task-lease enforcement, source-mutation claim checks and mirrored coding-tool receipts from historical `cogcoder.organization.execution_tools` to canonical `nolane.external_core.execution_executor`. The canonical executor now imports canonical artifact, identity, invokable-core, execution-schema/workspace, coding-claim/patch and digest authorities directly. Historical `cogcoder.organization.execution_tools` is an exact public-object bridge; `external.execution.control` remains a separate compatibility facade and is not claimed by Wave 5W.

Wave 5X establishes canonical event/context schema authority without falsely retiring semantic component debt. `EventKind` and `CognitiveEvent` are now owned by `nolane.organization.events`; `ContextCapsule` is owned by `nolane.external_core.context`; historical `cogcoder.organization.types` preserves exact object bridges. Canonical `nolane` modules no longer reverse-import these shared schemas from the mixed historical types module. `external.context`, `neural.inference_bridge`, and `external.execution.control` remain explicit non-native boundaries until their own dependency-safe cutovers. The projection therefore remains at 24 non-native component records.

Wave 5Y retires the `external.context` compatibility boundary by moving the base `ContextCompiler`, bounded context-intelligence/continuity/delta receipts, Memory/Context profile routing, contradiction-repair control plane and memory-aware adapter under canonical ownership. `ContextCapsule` remains owned by `nolane.external_core.context`; the five historical organization context modules are exact semantic public-object bridges. Canonical context code contains no reverse import of those historical context authorities. The generated native-debt projection therefore moves from 24 to 23 records while `neural.inference_bridge` and `external.execution.control` remain explicit compatibility boundaries. The resulting projection has 23 non-native component records.

Wave 5Z retires the `neural.inference_bridge` compatibility boundary by moving `AgentInferenceBackend`, `CognitiveStateEncoder`, deterministic fixture inference and the hash-gated R2.3 adapter under canonical `nolane.neural.inference_bridge` ownership. The canonical bridge imports only canonical digest, context, execution-schema and identity authorities; historical `cogcoder.organization.execution_inference` is now an exact public-object bridge. `external.execution.control` remains the next separate compatibility boundary rather than being mixed into this cutover. The generated projection therefore moves from 23 to 22 non-native component records.

## Repository authority and remaining debt

`CURRENT/REPOSITORY_AUTHORITY.md` defines repository precedence and quarantine semantics. `archive/INDEX.json` is the generated root-history census. `CURRENT/NATIVE_DEBT.json` / `.md` expose every canonical semantic component that is not yet `canonical_native`, so extraction can continue independently using local `0.0.N` component versions.

Wave 5V reduced generated native debt to 25 remaining non-native component records. Wave 5W retires exactly `external.execution.executor`, reducing that debt from 25 to 24 while leaving `external.execution.control` and all unrelated compatibility/historical/frozen boundaries unchanged. Wave 5Y reduces the projection to 23; Wave 5Z retires exactly `neural.inference_bridge`, reducing it to 22 while `external.execution.control` remains explicit debt.

The dependency graph and the actual import graph must both be clean before a boundary is cut over. In particular, Assurance and Individual Evolution currently expose hidden legacy import coupling beyond their high-level manifest edges; those surfaces must be retargeted or decomposed before authority migration rather than moved cosmetically.

No current status statement implies that all runtime or External Core surfaces are already native. Compatibility, determinism, evidence, repository quarantine, and the 67 permanent first-generation AI identity constraints remain fail-closed throughout Refoundation.
