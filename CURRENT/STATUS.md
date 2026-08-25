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

The core requirements-to-integration chain remains:

`Requirements -> Planning -> Architecture -> Integration`

Wave 5R opened the next dependency-safe extraction front with invokable-core schema/registry authority depending only on canonical `organization.identity`. Wave 5S moved the isolated Git-worktree execution workspace under canonical authority. Wave 5T now moves exclusive source-mutation claim authority under canonical ownership before attempting the execution executor boundary. Historical `cogcoder.organization.execution_workspace` and `cogcoder.organization.code_claims` are exact-object import/provenance bridges rather than executable ownership.

The executor is intentionally not marked native in Wave 5T. Its manifest requires `external.coding.claims`, which is resolved here, while the actual implementation also carries hidden coupling to coding-patch receipt mirroring and shared execution action types. Those edges must be retargeted or separated before `external.execution.executor` can truthfully claim canonical authority.

## Repository authority and remaining debt

`CURRENT/REPOSITORY_AUTHORITY.md` defines repository precedence and quarantine semantics. `archive/INDEX.json` is the generated root-history census. `CURRENT/NATIVE_DEBT.json` / `.md` expose every canonical component that is not yet `canonical_native`, so extraction can continue independently using local `0.0.N` component versions.

Wave 5T removes only `external.coding.claims` from the Wave 5S debt set. The generated debt projection therefore contains 26 remaining non-native component records: 19 compatibility facades, 5 historical-only boundaries, 1 legacy-internal boundary, and 1 frozen neural asset. Execution executor/control, coding patches/control, context, assurance, operations, research, UI/UX, evaluation, neural inference and historical-only capability boundaries remain explicit debt until their own parity-tested extraction waves are accepted.

The dependency graph and the actual import graph must both be clean before a boundary is cut over. In particular, Assurance and Individual Evolution currently expose hidden legacy import coupling beyond their high-level manifest edges; those surfaces must be retargeted or decomposed before authority migration rather than moved cosmetically.

No current status statement implies that all runtime or External Core surfaces are already native. Compatibility, determinism, evidence, repository quarantine, and the 67 permanent first-generation AI identity constraints remain fail-closed throughout Refoundation.
