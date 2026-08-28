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
- Wave 5AA candidate: `external.execution.control` -> native `nolane.external_core.execution`
- Wave 5AB prerequisite: canonical coding profile/routing authority -> `nolane.external_core.coding_profiles`
- Wave 5AC candidate: `external.coding.control` -> native `nolane.external_core.coding`
- Wave 5AD candidate: `external.debugging` -> native `nolane.external_core.debugging` semantic closure
- Wave 5AE candidate: `external.ui_ux` -> native `nolane.external_core.ui_ux` semantic closure
- Wave 5AF candidate: `evaluation.regimes` -> native `nolane.evaluation.regimes`
- Wave 5AG candidate: `evaluation.evidence` -> native `nolane.evaluation.evidence`
- Wave 5AH candidate: `evaluation.stress` -> native `nolane.evaluation.stress`
- Wave 5AI candidate: `evaluation.claims` -> native `nolane.evaluation.claims`
- Wave 5AJ candidate: `evaluation.parameters` -> native `nolane.evaluation.parameters`
- Wave 5AK candidate: `evaluation.release` -> native `nolane.evaluation.release`
- Wave 5AL candidate: `evaluation.scaling` -> native `nolane.evaluation.scaling`

The core requirements-to-integration chain remains:

`Requirements -> Planning -> Architecture -> Integration`

Wave 5R opened the next dependency-safe extraction front with invokable-core schema/registry authority depending only on canonical `organization.identity`. Wave 5S moved the isolated Git-worktree execution workspace under canonical authority. Wave 5T moved exclusive source-mutation claim authority under canonical ownership. Historical `cogcoder.organization.execution_workspace` and `cogcoder.organization.code_claims` are exact-object import/provenance bridges rather than executable ownership.

Wave 5U moves the shared execution schemas (`ToolAction`, `ExecutionAction`, execution budgets/counters, inference requests, and decision receipts) from historical `cogcoder.organization.execution_types` to canonical `nolane.external_core.execution_types`, with canonical JSON/digest authority and exact historical object identity preserved. This is a prerequisite extraction rather than a semantic debt retirement: `external.execution.executor` and `external.execution.control` remain compatibility facades at that wave boundary.

Wave 5V moves patch candidates, source-scope normalization, claim coverage, patch status, tool invocation receipts and patch-ledger snapshot authority from historical `cogcoder.organization.coding_patches` to canonical `nolane.external_core.coding_patches`. The canonical patch layer depends only on canonical coding claims and canonical digest identity; historical coding-patches imports preserve exact public object identity.

Wave 5W moves the fail-closed external-core executor, content-addressed core invocation receipts, bounded filesystem/Git/search/subprocess dispatch, task-lease enforcement, source-mutation claim checks and mirrored coding-tool receipts from historical `cogcoder.organization.execution_tools` to canonical `nolane.external_core.execution_executor`. The canonical executor now imports canonical artifact, identity, invokable-core, execution-schema/workspace, coding-claim/patch and digest authorities directly. Historical `cogcoder.organization.execution_tools` is an exact public-object bridge; `external.execution.control` remains a separate compatibility facade and is not claimed by Wave 5W.

Wave 5X establishes canonical event/context schema authority without falsely retiring semantic component debt. `EventKind` and `CognitiveEvent` are now owned by `nolane.organization.events`; `ContextCapsule` is owned by `nolane.external_core.context`; historical `cogcoder.organization.types` preserves exact object bridges. Canonical `nolane` modules no longer reverse-import these shared schemas from the mixed historical types module. `external.context`, `neural.inference_bridge`, and `external.execution.control` remain explicit non-native boundaries until their own dependency-safe cutovers. The projection therefore remains at 24 non-native component records.

Wave 5Y retires the `external.context` compatibility boundary by moving the base `ContextCompiler`, bounded context-intelligence/continuity/delta receipts, Memory/Context profile routing, contradiction-repair control plane and memory-aware adapter under canonical ownership. `ContextCapsule` remains owned by `nolane.external_core.context`; the five historical organization context modules are exact semantic public-object bridges. Canonical context code contains no reverse import of those historical context authorities. The generated native-debt projection therefore moves from 24 to 23 records while `neural.inference_bridge` and `external.execution.control` remain explicit compatibility boundaries. The resulting projection has 23 non-native component records.

Wave 5Z retires the `neural.inference_bridge` compatibility boundary by moving `AgentInferenceBackend`, `CognitiveStateEncoder`, deterministic fixture inference and the hash-gated R2.3 adapter under canonical `nolane.neural.inference_bridge` ownership. The canonical bridge imports only canonical digest, context, execution-schema and identity authorities; historical `cogcoder.organization.execution_inference` is now an exact public-object bridge. `external.execution.control` remains the next separate compatibility boundary rather than being mixed into this cutover. The generated projection therefore moves from 23 to 22 non-native component records.

Wave 5AA retires `external.execution.control` by moving execution-session state, step and terminal receipts, budget/lease/backend enforcement, terminal evidence creation and the `OrganizationExecutionControlPlane` itself under canonical `nolane.external_core.execution` ownership. The canonical control plane now imports native artifact, inference, executor, execution-schema/workspace, invokable-core, identity, task and canonical digest authorities directly. Historical `cogcoder.organization.execution` is an exact semantic public-object bridge. The generated native-debt projection therefore moves from 22 to 21 non-native component records while coding, debugging, UI, assurance, operations, research, individual-evolution and evaluation boundaries remain explicit debt.

Wave 5AB is a prerequisite-only extraction for the coding boundary. `CodingDomain`, `CodingProfile`, `CodingWorkRequest`, `CodingCandidateScore`, `CodingAssignmentReceipt`, and `CodingProfileRegistry` now have canonical semantic ownership in `nolane.external_core.coding_profiles`, directly depending on canonical identity and digest authority. Historical `cogcoder.organization.coding_profiles` is reduced to an exact public-object bridge. This prerequisite deliberately does not claim `external.coding.control`: that component remains a compatibility facade and the generated native-debt projection remains at 21 non-native component records.

Wave 5AC retires `external.coding.control` by moving `PatchVerificationEvidence`, `CodingReadinessReceipt`, coding assignment/source-claim/patch submission/readiness gates, planning and architecture feedback, personal-skill proposal flow, and `CodingControlPlane` snapshot authority under native `nolane.external_core.coding` ownership. The canonical control plane imports canonical coding profiles, claims, patches, planning, architecture, skills, identity, tasks, events and digest authorities directly, with no reverse `cogcoder.organization` import. Historical `cogcoder.organization.coding` is now an exact semantic public-object bridge. The generated native-debt projection therefore moves from 21 to 20 non-native component records.

Wave 5AD retires `external.debugging` by moving failure-case state, deterministic reproduction/evidence ledgers, root-cause hypothesis authority, six-profile debugging routing, coding handoff/resolution receipts, debugging control-plane snapshot authority, and post-resolution personal-skill proposal flow under native `nolane.external_core.debugging` ownership. The accepted debugging implementation executes inside the canonical package and resolves coding, skills, identity, tasks, events and digest dependencies only through canonical authorities. Historical `cogcoder.organization.debugging`, `debug_evidence`, `debug_hypotheses`, and `debug_profiles` are exact semantic public-object bridges. The generated native-debt projection therefore moves from 20 to 19 non-native component records.

Wave 5AE retires `external.ui_ux` by moving UI assignment/routing, cross-region coding grants and handoff, render-observation provenance, authoritative UX design flows, visual/responsive/accessibility/interaction quality gates, UI readiness receipts, and post-work personal-skill proposal flow under native `nolane.external_core.ui_ux` ownership. The accepted UI implementation executes inside the canonical package; UI coding, design, observation, and profile helpers are canonical-owned modules and resolve coding, artifacts, skills, identity, authority, events and digest dependencies without reverse `cogcoder.organization` imports. Historical `cogcoder.organization.ui`, `ui_coding`, `ui_design`, `ui_observations`, and `ui_profiles` are exact semantic public-object bridges. The generated native-debt projection therefore moves from 19 to 18 non-native component records.

Wave 5AF retires `evaluation.regimes` by moving benchmark-domain, evidence-provenance, evaluation-mode, immutable regime/budget identity and deterministic benchmark-registry snapshot authority under native `nolane.evaluation.regimes` ownership. The canonical regime layer depends only on `nolane.core.canonical_digest`; historical `cogcoder.organization.evaluation_regimes` is an exact public-object bridge. The generated native-debt projection therefore moves from 18 to 17 non-native component records while the remaining evaluation evidence/stress/parameters/release/claims/scaling/campaign boundaries remain explicit debt.

Wave 5AG retires `evaluation.evidence` by moving evaluation observations, canonical digest validation, matched-budget comparisons, organization-superiority assessments, controlled ablation assessments and evidence-ledger snapshot authority under native `nolane.evaluation.evidence` ownership. The canonical evidence layer resolves benchmark regimes, organization identity, verification evidence and canonical digest only through `nolane` authorities; historical `cogcoder.organization.evaluation_evidence` is an exact semantic public-object bridge. The generated native-debt projection therefore moves from 17 to 16 non-native component records while evaluation stress/parameters/release/claims/scaling/campaign and the remaining External Core/historical/frozen boundaries stay explicit debt.

Wave 5AH retires `evaluation.stress` by moving long-horizon stress scenarios, observations, required-scenario suite assessments and deterministic stress-ledger snapshot authority under native `nolane.evaluation.stress` ownership. The canonical stress layer resolves organization identity, verification evidence and canonical digest only through `nolane` authorities; historical `cogcoder.organization.evaluation_stress` is an exact semantic public-object bridge. The generated native-debt projection therefore moves from 16 to 15 non-native component records while evaluation parameters/release/claims/scaling/campaign and the remaining External Core/historical/frozen boundaries stay explicit debt.

Wave 5AI retires `evaluation.claims` by moving claim classification, immutable claim/readiness receipts and the claim-boundary control engine under native `nolane.evaluation.claims` ownership. The canonical claims layer resolves evaluation evidence, benchmark regimes, long-horizon stress, organization identity and canonical digest only through `nolane` authorities; historical `cogcoder.organization.evaluation_claims` becomes an exact semantic public-object bridge. The generated native-debt projection therefore moves from 15 to 14 non-native component records.

Wave 5AJ retires `evaluation.parameters` by moving physical/logical parameter-footprint accounting, scaling proposal receipts, evidence-governed efficiency checks and scaling-decision authority under native `nolane.evaluation.parameters` ownership. The canonical parameters layer resolves evaluation evidence, benchmark provenance, organization identity and canonical digest only through `nolane` authorities; historical `cogcoder.organization.evaluation_parameters` becomes an exact semantic public-object bridge. The generated native-debt projection therefore moves from 14 to 13 non-native component records and unblocks a truthful later `evaluation.release` cutover.

Wave 5AK retires `evaluation.release` by moving release receipts, aggregate evaluation provenance, reproduction receipts and external-reproducibility validation under native `nolane.evaluation.release` ownership. The canonical release layer resolves artifacts, evaluation evidence, parameter accounting, benchmark regimes, stress evidence, organization identity and canonical digest only through `nolane` authorities; historical `cogcoder.organization.evaluation_release` becomes an exact semantic public-object bridge. The generated native-debt projection therefore moves from 13 to 12 non-native component records.

Wave 5AL retires `evaluation.scaling` by moving the evaluation-scaling composition control plane, empty-state semantics and snapshot reconstruction under native `nolane.evaluation.scaling` ownership. The canonical scaling layer composes artifacts, claims, evidence, parameters, regimes, release, stress and organization identity only through canonical `nolane` authorities; historical `cogcoder.organization.evaluation` becomes an exact control-plane bridge. The generated native-debt projection therefore moves from 12 to 11 non-native component records.

## Repository authority and remaining debt

`CURRENT/REPOSITORY_AUTHORITY.md` defines repository precedence and quarantine semantics. `archive/INDEX.json` is the generated root-history census. `CURRENT/NATIVE_DEBT.json` / `.md` expose every canonical semantic component that is not yet `canonical_native`, so extraction can continue independently using local `0.0.N` component versions.

Wave 5V reduced generated native debt to 25 remaining non-native component records. Wave 5W retires exactly `external.execution.executor`, reducing that debt from 25 to 24 while leaving `external.execution.control` and all unrelated compatibility/historical/frozen boundaries unchanged. Wave 5Y reduces the projection to 23; Wave 5Z retires exactly `neural.inference_bridge`, reducing it to 22. Wave 5AA retires exactly `external.execution.control`, reducing the projection to 21 non-native component records. Wave 5AB is prerequisite-only and intentionally keeps that count at 21 while canonicalizing shared coding-profile/routing authority ahead of the `external.coding.control` cutover. Wave 5AC retires exactly `external.coding.control`, reducing the generated projection to 20 non-native component records. Wave 5AD retires exactly `external.debugging`, reducing the generated projection to 19 non-native component records. Wave 5AE retires exactly `external.ui_ux`, reducing the generated projection to 18 non-native component records. Wave 5AF retires exactly `evaluation.regimes`, reducing the generated projection to 17 non-native component records. Wave 5AG retires exactly `evaluation.evidence`, reducing the generated projection to 16 non-native component records. Wave 5AH retires exactly `evaluation.stress`, reducing the generated projection to 15 non-native component records.

The dependency graph and the actual import graph must both be clean before a boundary is cut over. In particular, Assurance and Individual Evolution currently expose hidden legacy import coupling beyond their high-level manifest edges; those surfaces must be retargeted or decomposed before authority migration rather than moved cosmetically.

No current status statement implies that all runtime or External Core surfaces are already native. Compatibility, determinism, evidence, repository quarantine, and the 67 permanent first-generation AI identity constraints remain fail-closed throughout Refoundation.

## Wave 5AM — native evaluation campaign cluster

- `evaluation.campaign` now owns the complete seven-module campaign semantic closure under `nolane.evaluation`.
- Historical `cogcoder.organization.campaign*` modules are exact-object compatibility bridges only.
- Component revision advances to `0.0.1`; active facade authority is retired.
- Repository native debt decreases from 11 to 10 non-native component records.

## Wave 5AN — native external assurance cluster

- `external.assurance` now owns the complete three-module assurance semantic closure under `nolane.external_core`.
- Historical `cogcoder.organization.assurance*` modules are exact-object compatibility bridges only.
- Component revision advances to `0.0.1`; active facade authority is retired.
- Repository native debt decreases from 10 to 9 non-native component records.

