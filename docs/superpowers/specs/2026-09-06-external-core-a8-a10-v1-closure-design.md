# External Core A8–A10 v1 Closure Design

Date: 2026-09-06
Base production commit: `63f3d3a89e93fc92868dc0829b6a15777283e74d`
Scope: External Core common boundary only
Status: design for final A8–A10 architectural closure

## 1. Purpose

A7 closed split-observation and time-of-check/time-of-use failure inside one canonical admission build or audit transaction. The remaining trust-boundary questions are different:

1. **A8 — Completeness:** did the observation cover every surface it was required to cover, including negative space?
2. **A9 — Provenance:** can every observed surface be tied to an explicit provider/source identity and exact content commitment?
3. **A10 — Continuity:** can a new observation be proven to extend the intended prior observation rather than silently rolling back, substituting history, or forking?

A8–A10 complete those properties without turning External Core into an orchestrator, authorization service, stateful ledger, runtime registry, learning system, release authority, or central governor.

The final architectural claim is deliberately narrow:

> External Core can describe and audit one complete, provenance-bound, atomically captured external observation and can verify its continuity against explicitly supplied predecessor evidence.

This is structural trust-boundary evidence only. It does not prove task correctness, Truth, Verification, Assurance, authorization, promotion, execution success, learning acceptance, release readiness, deployment approval, repair permission, or migration authority.

## 2. Architectural classification

This is an architectural continuation, not a bounded patch. A8, A9, and A10 alter the meaning of the current observation/audit surface and introduce a reusable observation representation shared by all External Core integrations.

The frozen A5 artifact lane remains outside this change:

- `external-integration-admission-v2` stays unchanged.
- `external-integration-admission-bundle-v2` stays unchanged.
- `nolane.external_core.integration_admission.COMPONENT_VERSION` stays `0.0.4`.
- historical A2–A7 states and frozen release witnesses are not rewritten or refrozen.

## 3. Considered approaches

### Approach A — one new protocol/version per milestone

A8 would add one audit protocol, A9 another, and A10 another, with repeated component-version bumps.

Advantages:
- each milestone has a distinct serialized identity;
- historical debugging can point at a protocol for each phase.

Disadvantages:
- unnecessary protocol churn for three parts of one final observation model;
- creates intermediate public artifacts that immediately become historical;
- raises compatibility and version-discipline cost without improving the final trust model.

### Approach B — one final observation envelope, staged TDD milestones

Introduce one reusable `CanonicalObservationEnvelope` protocol owned by the current Integration lane. Implement and prove A8, then A9, then A10 through separate RED/GREEN test groups, but ship one cumulative current observation protocol and one audit protocol revision.

Advantages:
- one coherent object represents the final five trust properties: authenticity/currentness, atomicity, completeness, provenance, continuity;
- preserves frozen admission/bundle artifacts;
- allows A8/A9/A10 to remain independently tested without manufacturing disposable serialized protocols;
- keeps the final public surface small.

Disadvantages:
- A8/A9 are test/document milestones rather than independent production protocol generations.

### Approach C — stateful External Core observation ledger

Persist chain heads and provider attestations inside External Core so A10 can autonomously reject forks.

Advantages:
- strongest autonomous fork detection.

Disadvantages:
- creates state ownership, mutation, lifecycle, recovery, and authorization questions;
- moves External Core toward a governor/ledger subsystem;
- violates the existing read-only/descriptive boundary.

### Decision

Use **Approach B**.

A8–A10 are one final architectural closure implemented as three test-driven milestones. External Core remains read-only and caller-evidence-driven. It validates continuity but does not own or mutate the canonical chain head.

## 4. Final architecture

Add a focused module:

`nolane/external_core/observation.py`

This module owns the reusable current observation representation. It must not import execution, authorization, promotion, learning, deployment, repair, or migration control paths.

`integration_admission_bundle.py` remains the admission/audit adapter and consumes the observation object rather than growing a second observation implementation inside the already-large bundle module.

### 4.1 Canonical observation surface contract

Introduce immutable `CanonicalObservationSurfaceContract` with protocol:

`external-canonical-observation-surface-v1`

Canonical state contains:

- `required_component_ids`: exact sorted tuple of canonical component IDs expected in the registry/profile observation;
- `required_surface_kinds`: exact sorted tuple of observation surface kinds;
- `digest`.

The required surface kinds for v1 are exactly:

- `registry`
- `authority-graph`
- `source-state`
- `evidence`
- `artifact`
- `freshness`
- `handoff`
- `work-trace`

The contract is an expectation commitment, not an observation. Its purpose is to make negative space explicit. A snapshot cannot prove completeness by merely hashing whatever happened to be returned.

For the canonical common External Core, `required_component_ids` is built independently from the expected canonical adapter population and is compared to the registry/profile population during capture. The registry/profile must contain exactly that population: missing, duplicate, or unexpected component identities fail closed.

No cardinality assumption is imposed on dynamic frontier entries. An empty dynamic frontier may be legitimate. Completeness for a dynamic frontier means the provider explicitly reports that enumeration of the declared surface is complete, not that the frontier is non-empty.

### 4.2 Surface observation receipt

Introduce immutable `SurfaceObservationReceipt` with protocol:

`external-surface-observation-receipt-v1`

Fields:

- `surface_kind`
- `provider_id`
- `provider_version`
- `source_locator`
- `scope_digest`
- `observed_state_digest`
- `enumeration_complete`
- `observed_epoch`
- `digest`

Rules:

- all identity/version/locator fields are exact non-empty strings;
- `enumeration_complete` is exact `bool`;
- `observed_epoch` is exact non-negative `int`; `bool` is invalid;
- `scope_digest` commits to what the provider claims it enumerated;
- `observed_state_digest` commits to the exact detached snapshot used downstream;
- receipt digest is content-addressed over all fields except itself;
- a receipt is evidence of provider declaration and content binding, not an authority grant.

For registry and authority graph, provider identity is generated from the canonical in-process adapter/profile builder path. For dynamic frontiers, the current public path must create or receive an explicit receipt for the exact mapping snapshot. A raw mapping alone must never silently prove `enumeration_complete=True` unless it is wrapped by the current canonical caller-provider adapter that explicitly declares its scope.

### 4.3 Canonical observation envelope

Introduce immutable `CanonicalObservationEnvelope` with protocol:

`external-canonical-observation-v1`

Fields:

- `surface_contract`
- `observed_epoch`
- `registry_digest`
- `authority_graph_digest`
- six frontier digests already used by `CanonicalAdmissionContext`
- exactly one canonical `SurfaceObservationReceipt` per required surface kind
- `chain_id`
- `previous_observation_digest` (`None` only for a declared genesis observation)
- `digest`

The envelope does **not** contain mutable live provider objects. It contains only detached canonical commitments and receipts. Any replay uses the detached snapshots captured in the same transaction, as required by A7.

The envelope digest is content-addressed over the complete state excluding `digest`.

### 4.4 Relationship to `CanonicalAdmissionContext`

Do not replace or mutate frozen A5 admission receipt identity.

The existing `CanonicalAdmissionContext` remains the exact context bound into admission-v2 receipts and bundle-v2. The new observation envelope is a current-lane witness whose committed registry/graph/frontier/epoch fields must exactly equal the fields represented by `CanonicalAdmissionContext`.

Current audit therefore proves both:

1. frozen admission/bundle integrity under the existing context;
2. current observation completeness/provenance/continuity under the new envelope.

No admission-v2 receipt digest changes.

## 5. A8 — Observation Completeness

### Governing invariant

> A canonical observation is current only if every required observation surface is explicitly represented and every required surface proves complete enumeration of its declared scope.

### A8 checks

A8 capture/audit must fail closed for:

- missing required component identity;
- unexpected component identity in the canonical registry/profile population;
- registry/profile population disagreement;
- missing required surface receipt;
- duplicate surface receipt;
- unknown/unexpected surface kind;
- `enumeration_complete=False` for a required current surface;
- receipt epoch different from the envelope/context epoch;
- receipt observed-state digest different from the detached snapshot digest;
- receipt scope digest different from the canonical declared scope.

Dynamic frontier `None` and `{}` remain semantically distinct:

- `None` = surface unavailable/not observed, therefore cannot prove completeness for a required current observation;
- `{}` = explicitly observed empty frontier, allowed only with a complete surface receipt for that empty declared scope.

This is the principal negative-space closure missing after A7.

## 6. A9 — Observation Provenance

### Governing invariant

> Every surface in a canonical observation must be traceable to an exact provider identity, provider version, source locator, declared scope, epoch, and observed content digest.

A9 does not claim that a provider is truthful merely because it signed its own structural receipt. It proves that the final observation is not provenance-anonymous and that source substitution cannot happen without changing the observation identity.

### A9 checks

Fail closed for:

- empty/coercible provider identity/version/locator;
- receipt provider substitution between build and persisted audit;
- receipt scope substitution;
- receipt content substitution;
- cross-epoch receipt reuse;
- two receipts claiming the same required surface kind;
- receipt digest forgery/non-canonical serialization;
- provider identity inconsistent with the canonical provider expected for registry/authority-graph surfaces.

The v1 design deliberately does not require two independent providers for every surface. Multi-provider corroboration may be supplied by future callers as evidence, but mandatory consensus is outside A1–A10 and would create a new architecture rather than close this one.

## 7. A10 — Observation Continuity and Fork Detection

### Governing invariant

> A non-genesis canonical observation is current only when it explicitly extends the exact predecessor observation supplied as continuity evidence; continuity may be validated but External Core does not own or mutate the chain head.

### Chain fields

`chain_id` is an exact non-empty string identifying the observation history domain.

For genesis:

- `previous_observation_digest is None`;
- genesis must be explicitly declared by the constructor/API;
- genesis cannot be silently inferred from missing predecessor evidence.

For a successor:

- `previous_observation_digest == predecessor.digest`;
- `chain_id == predecessor.chain_id`;
- `observed_epoch > predecessor.observed_epoch`;
- current observation integrity/completeness/provenance must independently pass.

### Pure continuity APIs

`validate_observation_transition(previous, current)` returns categorical findings and performs no mutation.

`detect_observation_forks(successors)` groups valid successor envelopes by `(chain_id, previous_observation_digest)` and reports `OBSERVATION_FORK_DETECTED` when more than one distinct canonical successor digest extends the same predecessor.

This detects forks when competing evidence is supplied. External Core does not store sibling observations and therefore does not pretend to detect evidence it has never been shown.

### Continuity findings

At minimum:

- `OBSERVATION_PREDECESSOR_UNAVAILABLE`
- `OBSERVATION_PREDECESSOR_DIGEST_MISMATCH`
- `OBSERVATION_CHAIN_ID_MISMATCH`
- `OBSERVATION_EPOCH_NOT_MONOTONIC`
- `OBSERVATION_FORK_DETECTED`
- `OBSERVATION_GENESIS_CONTEXT_INVALID`

A10 does not replace A6 exact same-transaction epoch equality. A6 asks whether current re-attestation is for exactly the epoch bound into a snapshot. A10 asks whether a new observation extends an older observation under a strictly later epoch.

## 8. Audit integration

Advance only the current audit lane. Recommended final identities:

- `external.integration` current component version: `0.0.7`
- compatibility semantic surface: `0.0.7`
- metadata revision for `external.integration`: `7`
- current bundle/audit owner version: `0.0.7`
- `ADMISSION_BUNDLE_PROTOCOL`: remains `external-integration-admission-bundle-v2`
- frozen `ADMISSION_PROTOCOL`: remains `external-integration-admission-v2`
- new observation protocol: `external-canonical-observation-v1`
- audit protocol: `external-integration-admission-audit-v4`
- audit digest namespace: `admission-audit-v4-*`

A8/A9/A10 are cumulative milestones inside one final observation protocol rather than three disposable protocol revisions.

`CanonicalAdmissionAuditReport` v4 should bind the exact observation envelope digest in addition to findings. A report for persisted state must not claim currentness without an explicitly supplied current observation envelope or enough inputs to build one under the same transaction.

Fresh in-process audit may build the envelope and bundle from one capture operation. Persisted audit must never rebuild a substitute envelope from partial data and treat it as equivalent to the persisted witness.

## 9. Public compatibility

Existing admission-v2 and bundle-v2 restore must remain byte-semantically unchanged.

Current builder/audit compatibility should be preserved where it does not contradict A8. Where the old API used `None` as a convenient default that became an implicit empty observed frontier, the current A8+ lane must no longer describe that as complete current observation evidence. Compatibility may still construct historical/bounded structures, but a clean current v4 audit requires explicit complete-surface evidence.

No automatic migration from old audit reports to v4 is provided. Old audit reports remain historical evidence under their own protocol identities.

## 10. Error handling and fail-closed rules

All new observation state parsers must use strict raw validation before any coercive restore behavior.

Reject:

- unknown/missing keys;
- non-string mapping keys where strings are required;
- bool-as-int epochs;
- tuples where serialized lists are required;
- custom objects accepted only through `str(...)` coercion;
- duplicate receipts/surfaces/components;
- non-canonical ordering/state;
- forged digest fields.

Audit findings are categorical and deterministic. A structural parser failure is not silently converted into an empty surface, genesis observation, or unavailable predecessor.

## 11. Test strategy

Implementation is strictly test-driven and proceeds in three independent RED/GREEN milestone groups on one feature branch.

### A8 RED/GREEN

Tests must first demonstrate that current A7 can accept or cannot distinguish:

- a canonical registry/profile observation whose expected provider population is incomplete;
- an omitted required frontier versus an explicitly observed empty frontier;
- missing/duplicate/unexpected surface receipts;
- incomplete enumeration receipt;
- receipt/snapshot digest mismatch.

GREEN adds the surface contract, receipt strictness, and completeness validation.

### A9 RED/GREEN

Tests must first demonstrate provenance anonymity/substitution under the A8 representation.

GREEN binds provider identity/version/locator/scope/content/epoch and verifies persisted replay against the exact receipts.

### A10 RED/GREEN

Tests must first demonstrate that two individually valid observations can currently be presented with no structural predecessor relationship and that sibling successors cannot be classified as a fork.

GREEN adds genesis/successor transition validation, strict epoch monotonicity across observations, chain-id binding, and pure fork detection.

### Regression gates

Before merge, require at minimum:

- compile canonical namespaces;
- all External Core contracts on Python 3.11 and 3.13;
- A5/A6/A7 regression tests unchanged except current projection assertions where required;
- component-local version discipline clean;
- component-version projection clean;
- canonical A2+A3 coherence audit clean;
- final A10 current audit clean;
- prior G/Assurance regressions clean;
- `git diff --check` clean;
- exact merge-ref topology and GitHub signature verification;
- post-merge External Core run on production `main` clean on Python 3.11 and 3.13.

Frozen historical release failures remain classified rather than rewritten.

## 12. Files and boundaries

Expected new file:

- `nolane/external_core/observation.py`

Expected focused modifications:

- `nolane/external_core/integration_admission_bundle.py`
- `nolane/external_core/integration.py`
- `nolane/external_core/compatibility.py`
- `nolane/metadata/component_versions.py`
- `.github/workflows/external-core-a2.yml`
- `CURRENT/EXTERNAL_CORE.md`
- current projection/revalidation tests

Expected new milestone tests:

- `tests/test_external_core_a8_observation_completeness.py`
- `tests/test_external_core_a9_observation_provenance.py`
- `tests/test_external_core_a10_observation_continuity.py`

Do not edit frozen `nolane/external_core/integration_admission.py` unless a new RED proves an unavoidable defect in the frozen protocol implementation itself. The default expectation is zero changes to that file.

## 13. Completion condition

External Core v1 architectural generation is considered complete after A10 only when production proves all of the following:

1. **Authenticity/currentness:** canonical registry/authority/frontier state matches the current structural context.
2. **Temporal validity:** currentness is re-attested for the exact transaction epoch.
3. **Atomicity:** one transaction uses one detached canonical observation.
4. **Completeness:** every required observation surface is explicitly present and completely enumerated for its declared scope.
5. **Provenance:** every surface is bound to exact provider/source/scope/content/epoch identity.
6. **Continuity:** successor observations explicitly extend supplied predecessor evidence and competing successors can be classified as a fork.

After this condition is met, A1–A10 is frozen as the first complete External Core architecture generation. No A11+ work is planned. A future change is justified only by a genuinely new trust-boundary failure class that cannot be represented by the A1–A10 model; feature expansion alone is not sufficient reason to reopen the architecture.
