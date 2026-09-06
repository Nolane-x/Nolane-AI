# External Core A5 — Canonical Admission & Protocol Integrity Firewall

## Status

Approved architectural direction for implementation.

## Governing law

> Historical compatibility may preserve prior serialization semantics; current admission must never silently coerce type or identity before canonical integrity is proved.

A5 is a post-Epoch-0 structural integrity program. It is not a new External Core family, not a global governor, not an orchestrator, and not a source of Truth, Verification, Assurance, authorization, promotion, execution, learning, release, deployment, repair, or migration authority.

## Problem

A2 established immutable/content-addressed manifests, authority edges/graphs, handoffs, and work traces. Some v1 construction and restore paths intentionally predate the stricter state discipline introduced later by A3/A4 and still normalize raw values with Python coercions such as `str(...)` before digest/canonical comparison.

That behavior is historically accepted and must remain restorable. It is not strong enough for current/live admission because a wrong-typed value can be converted into a syntactically valid string before the integrity boundary observes the original type. A custom object with a benign-looking `__str__`, a boolean in an integer-shaped position, or a non-string mapping key can therefore lose its original type before a v1 canonical-state comparison.

A4 `ScopedEvidenceRecord` demonstrates the desired current discipline: exact raw types and shapes are checked before semantic reconstruction, direct-constructor forgery is rejected at consumers, and state identity is content-addressed only after those checks.

## Compatibility posture

A5 adopts two explicit lanes:

1. **Historical v1 lane.** Existing A2 v1 APIs and serialized state remain byte-semantically compatible. A5 does not rewrite their legacy coercion behavior and does not refreeze historical evidence.
2. **Current/live v2 admission lane.** A current semantic consumer may not treat arbitrary v1 objects or arbitrary raw v1 state as admitted merely because a legacy restore succeeds. Raw state must first pass strict type/shape validation, then legacy semantic restore, then exact current-context qualification, and finally receive a content-addressed admission receipt.

There is no automatic v1-to-v2 migration. Admission is an explicit structural qualification step.

## Ownership and versioning

A5 is owned by `external.integration`, because it governs cross-component structural integration and currentness qualification without owning the underlying A–G semantic authorities.

A5 adds a public secondary surface `nolane.external_core.integration_admission` with the same component identity as the canonical `nolane.external_core.integration` surface. The canonical integration root remains the identity anchor.

Only one component revision advances:

- `external.integration`: `0.0.3 -> 0.0.4`

No manifest producer, evidence producer, authority owner, handoff producer, trace producer, or downstream consumer is bumped merely because it participates in A5 admission.

No global External Core version is introduced.

## Protocol

A5 introduces `external-integration-admission-v2`.

### Strict admission context

`CanonicalAdmissionContext` is immutable/content-addressed and contains only structural-currentness inputs already owned elsewhere:

- canonical registry digest;
- canonical authority-graph digest;
- source-state frontier digest;
- evidence frontier digest;
- artifact frontier digest;
- freshness-fence frontier digest;
- known handoff frontier digest;
- work-trace frontier digest;
- explicit observation epoch.

Every scalar identity/digest must be an actual non-empty `str`. Epoch must satisfy `type(value) is int` and be non-negative. Frontier entries are exact sorted `(identity, digest)` pairs with duplicate-key rejection. No `str(...)`, `int(...)`, `bool(...)`, or permissive collection conversion is allowed on raw admission state.

The context is descriptive currentness evidence only. It grants no semantic authority.

### Admission subject kinds

A5 admits four A2 subject families into the current lane:

- `component-manifest-v1`;
- `authority-graph-v1`;
- `external-handoff-v1`;
- `cognitive-work-trace-v1`.

The historical object remains the semantic payload. A5 does not create a second manifest model or a second authority graph model. Instead it validates the raw serialized state strictly before invoking the existing v1 restore, then binds the exact restored state to the exact current admission context.

### Raw-state firewall

Each subject kind has a schema-specific raw validator. The validator runs before any v1 `from_state` method and enforces:

- the outer state is a mapping with exact required keys and no unknown keys;
- string fields are real non-empty strings where the protocol requires explicit values;
- enum state is an exact string value, never an arbitrary object convertible to a string;
- integer fields reject booleans and non-integers;
- booleans are exact booleans;
- arrays are exact lists in serialized state;
- tuple-like rows represented in state have exact arity and string members;
- mappings use exact string keys and exact string values where required;
- digest/identity fields are exact strings;
- nested manifest/edge/handoff/trace states are recursively strict-validated before legacy restoration;
- duplicate set-like entries are rejected before canonical sorting can erase evidence of duplication.

A custom object whose `__str__` returns a valid component ID must be rejected before the legacy API sees it.

### Admission receipt

`ProtocolAdmissionReceipt` is immutable/content-addressed and binds:

- admission protocol;
- subject kind;
- subject protocol;
- subject identity;
- subject canonical state digest;
- legacy semantic digest/identity where the subject exposes one;
- exact admission-context digest;
- integration owner identity/version;
- categorical disposition;
- reason codes and explicit limitations.

Allowed dispositions are `ADMITTED`, `BLOCKED`, and `UNKNOWN`.

`ADMITTED` is a structural-currentness result only. It cannot mean verified, assured, authorized, promoted, executable, deployable, releasable, or correct.

A receipt must validate its own content identity on every semantic consumption path.

### Typed admitted wrappers

A5 exposes immutable wrappers for the four subject kinds. Each wrapper stores:

- the exact canonical v1 serialized state after strict validation;
- the admission receipt;
- its own wrapper digest.

`from_state` re-runs the raw firewall before legacy restoration and recomputes the receipt/wrapper identity. Direct-constructor forged wrappers fail when consumed.

No API accepts a preconstructed v1 object and silently labels it admitted. Current admission starts from raw serialized state plus explicit current context.

## Subject qualification

### Manifest admission

A manifest can be `ADMITTED` only when:

1. its raw state passes the strict manifest firewall;
2. legacy `ExternalComponentManifest.from_state` restores exactly;
3. its component identity exists in the current canonical registry;
4. the restored state is exactly equal to the registry manifest state for that identity;
5. the admission context registry digest matches the supplied current registry.

Identity/version substitution is `BLOCKED`. Missing current registry evidence is `UNKNOWN` only when the current-context input itself is absent by API contract; A5 canonical builders will provide it and fail closed otherwise.

### Authority-graph admission

A graph can be `ADMITTED` only when:

1. every nested manifest and edge state passes strict raw validation;
2. legacy graph restore succeeds;
3. graph validation is clean;
4. graph digest exactly matches the supplied current canonical authority graph;
5. its manifest population exactly matches the current registry manifests;
6. context registry/graph digests match those current objects.

A self-consistent caller-recomputed graph digest cannot substitute for the canonical current graph.

### Handoff admission

A handoff can be `ADMITTED` only when:

1. raw state passes the strict handoff firewall before legacy restore;
2. legacy restore recomputes handoff identity/payload digest exactly;
3. producer and consumer manifests are themselves obtainable from the exact current registry;
4. A2 consumer validation is re-run using strictly validated current source/evidence/artifact/predecessor/freshness inputs;
5. A2 validation returns `ACCEPTED`;
6. the current context digest binds those exact frontiers.

A2 `UNKNOWN` maps to A5 `UNKNOWN`; A2 `BLOCKED` maps to A5 `BLOCKED`.

The handoff authority class is descriptive of authority already produced elsewhere and gains no authority from A5 admission.

### Work-trace admission

A work trace can be `ADMITTED` only when:

1. raw trace, node, and supersession state passes strict shape/type validation;
2. legacy restore proves node IDs, predecessor closure, supersession references, cycle freedom, and trace digest;
3. every referenced handoff ID required for current qualification is present in the exact admitted/current handoff frontier;
4. trace diagnostics contain no structural finding;
5. context handoff/work-trace frontier digests match the exact supplied current frontier.

Negative/blocked/aborted lineage continues to require retained evidence references under the existing A2 semantics.

## Cross-protocol integrity firewall

`CanonicalAdmissionBundle` groups one exact context with a deterministic set of admitted manifests, one admitted authority graph, admitted handoffs, and admitted work traces.

Bundle construction revalidates every child receipt/wrapper, rejects duplicate subject identities, and recomputes cross-protocol invariants:

- all admitted manifests belong to the same registry/context;
- the admitted graph belongs to that exact registry/context;
- every admitted handoff producer/consumer is in the admitted manifest population;
- every admitted trace handoff reference is in the admitted handoff population when a reference is present;
- no child receipt belongs to another context;
- no missing or extra subject can be hidden by caller-provided bundle metadata.

The bundle is content-addressed. It is a structural admission snapshot, not a runtime permission set.

## Canonical current builder

A5 adds a read-only canonical builder that derives the admission context and bundle from A3 current registry/fabric objects and exact current frontiers. It must use exact string values already present in canonical source state; it does not coerce source constants with `str(...)`.

If a canonical source exposes a non-string `COMPONENT_ID` or `COMPONENT_VERSION`, the builder fails closed instead of laundering it into a registry identity.

This also hardens the A3 current construction path without rewriting historical A3/v1 restore semantics.

## Audit integration

The existing A2+A3 audit remains backward-compatible. A5 adds a separate current-admission audit surface that reports categorical findings for:

- raw type/shape violations;
- current registry mismatch;
- canonical graph mismatch;
- cross-context receipt replay;
- handoff currentness failure;
- trace frontier/reference failure;
- forged receipt/wrapper/bundle state;
- duplicate/rebound subject identities.

The audit is read-only and has no repair mode.

## Adversarial matrix

Permanent tests must include at least:

- custom object with `__str__` returning a valid component ID/version/digest;
- integer, boolean, bytes, enum object, or list smuggled into string fields;
- `True`/`False` smuggled into integer epoch/counter fields;
- tuple supplied where serialized state requires list and vice versa;
- non-string mapping keys/values;
- duplicate bindings/rows hidden by canonical sorting;
- unknown and missing state keys;
- caller-recomputed digest over forged but self-consistent manifest/graph/handoff/trace state;
- manifest from another registry;
- graph from another canonical profile;
- handoff replay under another source/evidence/artifact/freshness frontier;
- trace replay under another handoff frontier;
- admission receipt replay under another context;
- direct-constructor forged receipt/wrapper/bundle;
- raw v1 state cannot become current-admitted without explicit A5 admission;
- historical v1 fixtures still restore through legacy APIs unchanged.

## CI and closure

External Core CI must include all A5 tests on feature pushes, pull requests, and main pushes. Acceptance requires Python 3.11 and 3.13 success, exact component-local version discipline with zero findings, component-version projection, canonical External Core coherence audit, prior G/Assurance regressions, Truth/Knowledge, and full Refoundation acceptance on the exact PR merge-ref.

Frozen historical release witnesses remain frozen and may continue to report historical boundary failures; A5 must not refreeze them merely for green CI.

## Success criteria

A5 is complete when current/live cross-protocol admission cannot erase an invalid raw type through implicit coercion, cannot replay a structurally valid subject into a different current context, cannot substitute a self-consistent caller graph/manifest for the canonical current fabric, and cannot mint or widen any A–G authority while all accepted v1 historical state remains backward-compatible.
