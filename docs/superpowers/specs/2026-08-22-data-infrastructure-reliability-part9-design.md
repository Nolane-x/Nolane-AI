# Data, Infrastructure & Reliability Part IX — Design Specification

## Status

Implements Issue #137 on accepted Parts I–VIII. The first-generation blueprint already contains twelve permanent operational identities: four Data, four Infrastructure and four Reliability identities.

Part IX turns those identities into three independent operational authority regions with a shared readiness coordinator. It does not collapse reliability into debugging, and it does not let deployment authority rewrite Verification/Security truth from Part VIII.

## 1. Authority boundaries

1. Data Chief owns schema/storage/migration/cache-consistency state.
2. Infrastructure Chief owns reproducible build, deployment, release and observability state.
3. Reliability Chief owns failure-scenario, recovery and measured-performance state.
4. Debugging explains defects; Reliability proves behavior under adverse operating conditions and recovery semantics.
5. Part VIII remains independent assurance authority. Operations may consume `VERIFIED` or explicit `OVERRIDDEN` state but never relabel an override as verification.
6. All operational artifacts are content-addressed or digest-grounded.
7. Each Chief remains a direct expert worker rather than a router only.

## 2. Operational profiles

`OperationsProfileRegistry` derives exactly twelve identities from three regions.

Data:
- Data Chief: cross-data arbitration and direct work.
- Schema & Migration Agent: schema evolution, compatibility and rollback.
- Persistence Agent: storage, transactions, durability and persistence.
- Cache & Consistency Agent: cache invalidation, coherence and consistency.

Infrastructure:
- Infrastructure Chief: cross-infrastructure arbitration and direct work.
- CI & Environment Agent: toolchain, build and environment reproducibility.
- Deployment Agent: rollout, rollback and deployment topology.
- Observability & Release Agent: package/release manifests, logs, metrics and traces.

Reliability:
- Reliability Chief: cross-reliability arbitration and direct work.
- Performance Agent: matched-condition benchmarking and resource profiling.
- Reliability Concurrency Agent: scheduling, duplicate/out-of-order and state-concurrency behavior.
- Recovery Agent: retry, idempotency, circuit breaking, checkpoints and graceful degradation.

Chiefs are multi-domain within their own region but specialists remain primary for their narrow domain. Routing is deterministic and profile state reads the current accepted neural version from AgentRegistry.

## 3. Data migration ledger

A `MigrationPlan` records:
- migration id;
- producer identity;
- from/to schema versions;
- forward migration artifact id/digest;
- rollback artifact id/digest;
- compatibility evidence refs;
- data-validation evidence refs;
- whether the migration is online/offline;
- idempotency declaration;
- digest.

A migration id cannot be rebound. `MigrationReadinessReceipt` is ready only when rollback is explicit, forward and rollback artifacts are distinct, compatibility evidence exists, validation evidence exists and the producer belongs to the Data region.

Schema/API migration readiness is evidence, not a prose declaration. A failed receipt remains historical truth; callers create a new migration revision to change the evidence basis.

## 4. Persistence and cache consistency

`PersistenceInvariant` records a named durability/transaction invariant plus evidence refs. `ConsistencyExercise` records cache/source versions, operation sequence, observed result, expected result and evidence refs. Cache consistency claims cannot be promoted from a single ungrounded textual note.

These records are scoped to Data memory and may become verified operational lessons only through normal skill promotion.

## 5. Reproducible build manifests

A `BuildManifest` records:
- source digest;
- dependency-lock digest;
- toolchain digest;
- environment digest;
- build-command digest;
- produced artifact id and artifact digest;
- producer identity;
- evidence refs;
- digest.

A build manifest is immutable. `BuildReproductionReceipt` compares an original manifest with an independently produced replay manifest under the same source/dependency/toolchain/environment/build-command digests. Reproducible means both the execution basis and artifact digest match.

A changed environment/toolchain produces a new basis; it is not silently treated as equivalent.

## 6. Release and observability

`ObservabilityBundle` records log-schema digest, metric-schema digest, trace-schema digest, SLO refs and evidence refs.

`ReleaseCandidate` links:
- reproducible build receipt;
- package artifact;
- configuration digest;
- deployment topology digest;
- rollback artifact;
- observability bundle;
- release evidence.

Release readiness fails closed when build reproducibility, rollback or observability evidence is absent.

## 7. Reliability failure matrix

`FailureScenarioKind` includes the six mandatory heldout operating failures:
- disk full;
- network timeout;
- process kill;
- restart;
- duplicate event;
- out-of-order event.

`FailureExercise` records scenario, workload digest, environment digest, injection artifact refs, recovery-strategy tags, recovered flag, data-loss count, duplicate-side-effect count and evidence refs.

A `ReliabilityMatrixReceipt` is complete only when every mandatory scenario has a clean exercise under the same declared workload/environment basis. Clean means recovered with zero data loss and zero duplicate side effects.

This is deliberately distinct from Debugging: a bug can be understood while a system still lacks idempotent/recoverable behavior under process, network or ordering failures.

## 8. Recovery semantics

Recovery strategy tags are explicit capabilities such as `retry`, `idempotency`, `circuit-breaker`, `checkpoint`, `rollback`, `degrade` and `deduplicate`. Failure exercises preserve which mechanisms were actually exercised; Part IX never infers recovery properties from implementation naming alone.

## 9. Measured performance claims

`PerformanceMeasurement` records:
- workload digest;
- environment digest;
- metric name/unit;
- baseline value;
- candidate value;
- lower-is-better flag;
- sample counts;
- evidence refs;
- digest.

`PerformanceClaimReceipt` is valid only when baseline/candidate share the same workload and environment basis, both have non-zero sample counts and the claimed direction is numerically supported. A performance claim from mismatched conditions is rejected even if the candidate number looks better.

## 10. Operational readiness coordinator

`OperationsControlPlane` owns three subledgers and can issue `OperationalReadinessReceipt` for a release. Readiness requires:
- migration receipts ready for all referenced migrations;
- reproducible build receipt successful;
- release candidate complete with rollback and observability;
- complete clean reliability matrix;
- any referenced performance claim valid;
- linked Part-VIII assurance subject has effective disposition `VERIFIED` or explicitly `OVERRIDDEN`.

Disposition:
- `READY` when assurance is verified;
- `READY_WITH_ASSURANCE_OVERRIDE` when Central explicitly overrode Part-VIII blocking state;
- `BLOCKED` otherwise.

`READY_WITH_ASSURANCE_OVERRIDE` must preserve the assurance override semantics and never surface as verified.

## 11. Direct Chief work

Data Chief must personally construct and validate a bounded migration with rollback/compatibility evidence.

Infrastructure Chief must personally produce a reproducible build/release/observability chain.

Reliability Chief must personally execute a bounded adverse-condition scenario and produce a recovery/performance receipt.

Each completes through ordinary `chief_direct_work` with concrete artifact ids.

## 12. Context, memory, learning and snapshot

Runtime adds `runtime.operations: OperationsControlPlane`.

Context exposure is region-scoped:
- Data identities receive `data-state`;
- Infrastructure identities receive `infrastructure-state`;
- Reliability identities receive `reliability-state`;
- unrelated regions do not receive full private operational ledgers.

Verified operational lessons may be proposed as personal skill candidates; promotion remains governed. Incident-specific assumptions remain evidence-scoped and are not automatically globalized.

Organization snapshots round-trip profiles, migrations, invariants, consistency exercises, builds, reproduction receipts, observability bundles, releases, failure exercises, reliability matrices, performance claims and operational readiness receipts exactly.

## 13. Fail-closed rules

- Unknown operational identities cannot author region records.
- Migration readiness without rollback/compatibility/validation evidence rejects.
- Reproducibility with mismatched build basis rejects.
- Release without rollback or observability rejects.
- Missing mandatory failure scenarios reject reliability readiness.
- Data loss or duplicate side effects reject clean recovery.
- Performance claims from unmatched conditions reject.
- Part-VIII rejected/pending assurance blocks operational readiness.
- Assurance override is preserved as override, not verification.
- No operational decision auto-merges code or bypasses Part VIII.

## 14. Acceptance evidence

Part IX is accepted only after RED contracts fail for absent production modules, then GREEN exact-head tests pass on Python 3.11 and 3.13 together with Parts I–VIII organization regressions and independent prior-Part workflows on the same head.
