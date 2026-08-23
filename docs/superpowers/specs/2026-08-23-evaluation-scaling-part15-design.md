# Part XV — Evaluation & Scaling Design

## Status
Approved architectural design for Issue #143. This is the final implementation part of the Coding AGI organization roadmap and extends the accepted Parts I–XIV without changing the 67 permanent identities or first-generation <100M physical-parameter ceiling.

## Goal
Create a fail-closed evidence boundary for organization-level capability claims, long-horizon reliability, matched-budget baseline/ablation evaluation, truthful parameter/compute accounting, reproducible external evaluation, and future scaling decisions.

## Non-goals
- This part does not claim Nolane is AGI or frontier-equivalent.
- It does not lift `PHYSICAL_PARAMETER_CEILING` or mutate first-generation `ParameterAccounting`.
- It does not train or deploy >100M models.
- It does not reinterpret internal/synthetic benchmarks as unrestricted external evidence.
- It does not replace Part VIII assurance, Part XII per-agent longitudinal evidence, Part XIV matched-budget Foundry benefit evidence, or existing release artifacts.

## Design choice
Use an `EvaluationScalingControlPlane` overlay composed of focused registries/ledgers. Accepted primitives remain canonical:
- Part VIII owns independent verification/assurance semantics.
- Part XII owns per-agent evolution and same-regime longitudinal evidence.
- Part XIII owns coordination/task/event lineage.
- Part XIV owns matched-budget ephemeral-team benefit evidence.
- `AgentRegistry` and `ParameterAccounting` remain the source of first-generation physical model accounting.
- `ArtifactStore` remains the durable content-addressed evidence/release store.

Part XV aggregates these primitives into organization-level evaluation, but never silently upgrades their evidence status.

## Module boundaries

### `evaluation_regimes.py`
Defines immutable benchmark and budget regimes.

`BenchmarkDomain` values:
- `CODING`
- `DEBUGGING`
- `PLANNING`
- `UI_UX`
- `SECURITY`
- `RESEARCH`
- `CROSS_DOMAIN`
- `LONG_HORIZON`

`EvidenceProvenanceClass` values:
- `INTERNAL_SYNTHETIC`
- `INTERNAL_REAL_REPOSITORY`
- `EXTERNAL_REPRODUCED`
- `EXTERNAL_INDEPENDENT`

`EvaluationMode` values:
- `SINGLE_AGENT`
- `FLAT_SWARM`
- `ORGANIZATION`
- `ORGANIZATION_NO_MEMORY`
- `ORGANIZATION_NO_TOOLS`
- `ORGANIZATION_NO_SPECIALIZATION`
- `ORGANIZATION_NO_COORDINATION`

`BenchmarkRegime` contains:
- benchmark/regime IDs;
- domain;
- task-set digest;
- environment/repository revision digest;
- freshness epoch;
- evaluator protocol version;
- allowed tool/core set digest;
- budget regime digest;
- provenance class;
- fresh/heldout flags;
- content digest.

A regime ID cannot be rebound. `EXTERNAL_INDEPENDENT` evidence must identify an evaluator outside the producing system identity set. Freshness and heldout status are explicit facts, not inferred from score.

### `evaluation_evidence.py`
Defines immutable organization observations and comparisons.

`EvaluationObservation` records:
- observation ID;
- regime ID/digest;
- mode;
- producer/system revision;
- score in `[0,1]`;
- task count/pass count;
- false accepts/regressions;
- compute units;
- tool calls;
- external-core calls;
- wall-clock milliseconds;
- energy estimate joules or `None`;
- active agents;
- evidence artifact IDs;
- permanent external verifier ID;
- evidence provenance class;
- digest.

All positive organization-level observations require clean external verification. Self-evaluation may be recorded as internal evidence but cannot authorize stronger claims.

`MatchedBudgetComparison` compares `ORGANIZATION` against `SINGLE_AGENT` or `FLAT_SWARM` only when regime, task set, repository revision, tool envelope and declared budget digest match. A win requires:
- strictly higher score;
- no higher false accepts;
- no higher regressions;
- resource usage within matched limits.

Mismatched regimes are `INCOMPARABLE`, never improvements.

`AblationAssessment` compares full organization with one declared ablation under identical regime/budget. It reports observed contribution without claiming causality beyond the controlled ablation.

### `evaluation_stress.py`
Defines long-horizon continuity stress evidence.

`StressScenarioKind` values:
- `SLEEP_WAKE_CONTINUITY`
- `PLAN_DRIFT`
- `MEMORY_CONTAMINATION`
- `TASK_REASSIGNMENT`
- `STALE_LEASE`
- `CONFLICT_BACKPRESSURE`
- `EPHEMERAL_RETIREMENT`

`LongHorizonStressObservation` records initial/final state digests, checkpoint/event anchors, task/plan revisions, contamination counters, stale-context counters, false accepts, regressions, recovery status, elapsed logical epochs and external evidence.

A stress suite is passing only when every required scenario has clean external evidence and zero false accepts/regressions, with continuity invariants preserved. Passing a short synthetic task never substitutes for long-horizon evidence.

### `evaluation_parameters.py`
Defines truthful organization parameter/compute accounting without changing first-generation model limits.

`ParameterFootprintReport` fields:
- `shared_physical_parameters` — unique shared substrate stored once;
- `local_physical_parameters` — sum of unique local deltas across selected permanent agents;
- `unique_stored_physical_parameters` — shared + local unique storage;
- `active_inference_physical_parameters` — unique physical parameters needed by the active set;
- `logical_deployed_parameter_footprint` — sum of per-agent logical views, explicitly labeled non-unique;
- active permanent agent IDs;
- active ephemeral count;
- compute units;
- latency milliseconds;
- energy estimate joules or `None`;
- digest.

Shared parameters are never multiplied by 67 and relabeled unique physical parameters.

`ScalingProposal` is an immutable request for a selected permanent agent/model family and may exceed 100M. It includes current/candidate physical counts, expected capability target, matched benchmark IDs, compute/storage/latency/energy deltas, evidence IDs and economic capacity digest.

`ScalingDecision` values:
- `REJECTED`
- `DEFERRED`
- `AUTHORIZED_FOR_FUTURE_EXPERIMENT`

No decision mutates `AgentRegistry`, `ParameterAccounting`, weights or accepted neural versions.

Authorization above 100M requires all of:
- clean independent external evidence;
- same-regime baseline/candidate comparison;
- positive score delta above an explicit minimum marginal-gain threshold;
- no false-accept or regression increase;
- declared compute/latency/storage/energy deltas;
- efficiency ratio not worse than the configured maximum;
- economic-capacity evidence;
- at least two independent verifier identities from different permanent regions;
- no unrestricted AGI/frontier claim dependency.

### `evaluation_claims.py`
Defines the claim boundary.

`ClaimClass` values:
- `INTERNAL_ENGINEERING_PROGRESS`
- `DECLARED_BENCHMARK_IMPROVEMENT`
- `ORGANIZATION_MATCHED_BUDGET_SUPERIORITY`
- `LONG_HORIZON_RELIABILITY`
- `CROSS_DOMAIN_TRANSFER`
- `EXTERNAL_REPRODUCIBLE_CAPABILITY`
- `AGI`
- `FRONTIER_EQUIVALENCE`

`ClaimDisposition` values:
- `SUPPORTED`
- `LIMITED`
- `BLOCKED`

`ClaimBoundaryEngine.assess()` is fail-closed. Minimum evidence rules:
- internal engineering progress may use clean internal evidence but must remain labeled internal;
- benchmark improvement requires same-regime clean external evidence;
- organization superiority requires wins over both single-agent and flat-swarm matched-budget baselines on declared tasks;
- long-horizon reliability requires the complete stress suite;
- cross-domain transfer requires evidence spanning at least three benchmark domains and one heldout cross-domain regime;
- external reproducible capability requires `EXTERNAL_INDEPENDENT` evidence plus release reproduction receipt;
- `AGI` and `FRONTIER_EQUIVALENCE` are hard-disabled in this first implementation regardless of local scores.

Central override, Part-VIII override, high internal score, model size, or number of agents never converts a blocked unrestricted claim into supported evidence.

### `evaluation_release.py`
Defines reproducible evaluation release receipts.

`EvaluationReleaseReceipt` includes:
- release ID/version;
- source commit SHA;
- benchmark regime IDs/digests;
- observation/comparison/stress IDs;
- parameter footprint report ID;
- claim assessment IDs;
- scaling decision IDs;
- artifact IDs/digests;
- evaluator protocol version;
- independent evaluator IDs;
- reproduction command digest;
- environment/toolchain digest;
- created logical epoch;
- digest.

A release cannot be marked externally reproducible unless at least one independent evaluator reproduces the declared artifact/evaluation digest under the declared protocol/environment. Release receipts are content-addressed and immutable.

### `evaluation.py`
`EvaluationScalingControlPlane` composes:
- benchmark regime registry;
- evaluation evidence ledger;
- long-horizon stress ledger;
- parameter/scaling authority;
- claim boundary engine;
- evaluation release ledger.

It provides no API that promotes neural weights, changes permanent identities, or bypasses existing verification authority.

Core API:
- `register_regime(...) -> BenchmarkRegime`
- `record_observation(...) -> EvaluationObservation`
- `compare_matched_budget(...) -> MatchedBudgetComparison`
- `assess_ablation(...) -> AblationAssessment`
- `record_stress(...) -> LongHorizonStressObservation`
- `assess_stress_suite(...) -> StressSuiteAssessment`
- `parameter_footprint(...) -> ParameterFootprintReport`
- `propose_scaling(...) -> ScalingProposal`
- `decide_scaling(...) -> ScalingDecisionReceipt`
- `assess_claim(...) -> ClaimAssessment`
- `create_release(...) -> EvaluationReleaseReceipt`
- `record_reproduction(...) -> ReproductionReceipt`

## Evidence freshness and externality
Evidence is external only when verifier identity is not the producer/subject identity and the provenance class says how it was obtained. `EXTERNAL_INDEPENDENT` additionally requires a non-organization evaluator identifier and reproducible protocol/artifact lineage.

A benchmark observation references an immutable regime digest. Changing task set, repo revision, tool permissions, model/system revision, or budget creates a new regime. Scores across different regime digests cannot be directly promoted as improvement.

## Matched-budget fairness
Budget equality means the declared budget regime digest is identical, including:
- compute-unit ceiling;
- tool-call ceiling;
- external-core-call ceiling;
- wall-clock ceiling;
- active-agent ceiling;
- repository/tool envelope.

Actual usage may be lower, but neither side may exceed the common limits. A more expensive organization does not win a matched-budget comparison merely by scoring higher.

## Ablation semantics
Ablations are controlled evidence, not proof that a component is universally necessary. Full organization is compared separately against no-memory, no-tools, no-specialization and no-coordination modes. Each assessment records score/safety/resource deltas and regime identity.

## Long-horizon continuity
Required suite:
1. sleep/wake after a long event gap;
2. plan revision while an agent sleeps;
3. stale/contradicted memory injection attempt;
4. task reassignment and old-lease output attempt;
5. cross-region conflict/backpressure recovery;
6. ephemeral specialist retirement followed by permanent continuation.

The suite measures continuity, contamination, stale-context and safety counters. Passing requires no hidden memory leakage, no stale-authority completion and externally evidenced final state integrity.

## Scaling semantics
The first-generation `<100,000,000` physical-parameter invariant remains active. `AUTHORIZED_FOR_FUTURE_EXPERIMENT` only means evidence supports running a separately governed future >100M experiment when infrastructure/economic capacity permits. It does not alter current production or accepted versions.

Minimum default scaling thresholds:
- candidate score delta >= `0.03` on declared matched regimes;
- no increase in false accepts/regressions;
- at least two independent permanent-region verifiers plus one external-independent evaluator;
- compute-cost ratio <= `1.75` for the measured capability gain package unless an explicit efficiency exception is independently justified;
- storage, latency and energy deltas must be present rather than omitted.

## Claim readiness rubric
`OrganizationReadinessReport` reports separate booleans/receipts for:
- benchmark coverage;
- matched-budget superiority;
- ablation coverage;
- long-horizon reliability;
- external reproducibility;
- parameter-accounting completeness;
- safety cleanliness;
- scaling evidence completeness.

There is no single opaque “AGI score”. A release may be engineering-ready while AGI/frontier claims remain blocked.

## Snapshot and restart
`EvaluationScalingControlPlane.to_state()` serializes all regimes, observations, comparisons, ablations, stress observations/assessments, parameter reports, scaling proposals/decisions, claim assessments, releases/reproductions and counters.

Restore validates digests, regime references, verifier externality, budget consistency, parameter arithmetic, claim dispositions and scaling thresholds. Pre-Part-XV snapshots use `state.get('evaluation_scaling', {})` and restore an empty evaluation layer.

## Runtime integration
Preserve the accepted Part-XIV runtime byte-for-byte in `runtime_part14.py`. New `runtime.py` subclasses it, constructs/restores `EvaluationScalingControlPlane`, and adds only the `evaluation_scaling` snapshot key.

## RED acceptance contracts
Tests must prove before GREEN implementation:
1. benchmark regime IDs/digests are immutable and fresh/heldout/provenance classes remain explicit;
2. internal/synthetic evidence cannot authorize external or unrestricted claims;
3. matched-budget comparison rejects regime, repo, task-set, tool-envelope or budget mismatch;
4. organization superiority requires clean wins over both single-agent and flat-swarm baselines;
5. false accepts/regressions block positive superiority even when score is higher;
6. memory/tools/specialization/coordination ablations use the exact same regime and report deltas separately;
7. complete long-horizon suite covers sleep/wake, plan drift, memory contamination, stale lease, backpressure and ephemeral retirement;
8. incomplete/dirty stress evidence blocks long-horizon reliability;
9. parameter report separates shared/local/unique-stored/active/logical-deployed footprints and does not multiply shared storage by 67;
10. >100M proposals never mutate first-generation ParameterAccounting or accepted neural versions;
11. >100M authorization requires marginal gain, clean safety, compute/storage/latency/energy accounting, economic evidence and independent cross-region/external verification;
12. AGI/frontier-equivalence claims remain blocked regardless of internal benchmark score or Central override;
13. external reproducibility requires immutable release artifacts, protocol/environment digests and independent reproduction;
14. exact snapshot round-trip rejects corrupt digests/counters/reference graphs;
15. pre-Part-XV runtime snapshots restore an empty evaluation layer and Parts I–XIV behavior remains unchanged.

## Capability claim boundary
Completing Part XV means the organizational substrate has a governed evaluation/scaling layer and the implementation roadmap I–XV is complete. It does not mean the system has demonstrated AGI. Strong capability claims remain contingent on future independent evidence satisfying the explicit claim gates above.