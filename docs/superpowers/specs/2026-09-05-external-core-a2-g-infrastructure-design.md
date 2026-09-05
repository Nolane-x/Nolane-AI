# Nolane AI A2 — External Core Coherence Fabric + G Infrastructure Upgrade

Status: DESIGN FOR REVIEW  
Date: 2026-09-05  
Target: post-Epoch-0 architecture expansion  
Repository authority: Nolane AI `CURRENT/` remains authoritative. Nolane World 0.12.0 is design/research provenance only and does not gain runtime authority in Nolane AI.

## 1. Goal

Upgrade Nolane AI's External Core from a collection of individually strong A–F families plus a comparatively shallow G family into one coherent, self-describing, replayable, provenance-closed external cognition substrate.

The change has two coupled goals:

1. strengthen **G. Infrastructure** substantially, especially Artifacts, Operations, and Research;
2. add a narrow **External Core Coherence Fabric (ECF)** that lets A–G exchange typed, content-addressed, authority-bounded handoffs without creating a new monolithic governor.

The design must preserve the existing post-Refoundation philosophy:

- proposal is not authority;
- evidence is not self-validating;
- historical green is not current validity;
- restore/replay must reconstruct authority, not merely deserialize labels;
- content-addressed identity prevents semantic rebinding;
- no family may gain hidden write authority by composing another family;
- failure, staleness, uncertainty, revocation, and incomplete observation remain explicit states;
- every cross-family strengthening must be machine-checkable.

## 2. Why this work is needed

External Core families A–F were upgraded through different programs and now contain strong local authority boundaries, evidence receipts, restore checks, and fail-closed behavior. G remains much closer to the original migrated baseline.

Current G already has useful primitives:

- `external.artifacts` owns a content-addressed in-memory artifact store;
- `external.operations` composes data, infrastructure, reliability, Assurance, and skill proposal;
- `external.infrastructure_operations` records build manifests, reproducibility, observability bundles, release candidates, and release readiness;
- `external.research` owns synthesis and engineering handoff;
- `external.research_provenance` owns sources, findings, contradiction resolution, freshness, and provenance.

The baseline is valuable but insufficient for the current architecture because it does not yet provide:

- artifact currentness / invalidation / revocation closure;
- graph-level provenance poisoning and descendant invalidation;
- a durable operational journal and recovery certificate model;
- cross-family handoff envelopes with exact producer/consumer contract binding;
- a unified component manifest and authority graph;
- research question certification, rival-hypothesis discipline, finite research budgets, explicit closure, trial disclosure, and negative-result retention;
- global coherence audit over A–G;
- cross-family restore preflight;
- adversarial integration tests that detect authority laundering between independently evolved families.

## 3. Provenance from Nolane World 0.12.0

Nolane World is used only as a research/design source. The following ideas are selected because they fit Nolane AI's existing authority model:

### Selected concepts

- **Artifact contracts**: progress/authority must be tied to contract-valid observable artifacts rather than prose assertions.
- **Provenance closure**: a revoked source poisons descendants; cycles are rejected; revocation propagates through explicit dependency edges.
- **Recovery certificates**: restore must prove a deterministic authenticated history and verify journal/snapshot lineage.
- **Research budgets**: finite work allocation with explicit room for exploration, falsification, verification, replication, and integration.
- **Research evidence receipts**: evidence identity, lineage, role, current task/stage binding, independent-verifier checks, and explicit revocation.
- **Research trial disclosure**: trials are append-only; negative and failed trials remain visible.
- **Research closure certificates**: completion is gated by required research obligations, not by “enough links found.”
- **Handoff packages**: do not transfer a task or conclusion as an ambiguous summary string.
- **Recovery manager / checkpoint / rollback / leases**: long-running work must survive context resets and prevent multiple actors from silently mutating the same protected state.
- **Source hierarchy**: source authority/quality must be explicit, but source count cannot substitute for epistemic independence.

### Rejected or deliberately not copied

- Nolane World's global runtime or Trust Kernel as an authority source inside Nolane AI;
- generic “world state” as a new canonical state plane;
- World-specific colony/mission/distributed-cluster semantics;
- any mechanism that duplicates A Truth/Knowledge, C Causal/Experimentation, D Planning/Architecture, or E Acting authority;
- any scalar “quality score” that can silently override categorical truth/Assurance rules.

## 4. Architectural choice

The selected architecture is a **federated coherence fabric**, not a central External Core orchestrator.

The fabric has no autonomous strategy, planning, execution, verification, promotion, release, or learning authority. It only owns:

- component declarations;
- cross-family contract schemas;
- immutable handoff/provenance identities;
- graph validation;
- coherence audit;
- restore preflight evidence;
- descriptive cross-family trace assembly.

This means the fabric can say:

> “This handoff is structurally valid, current, provenance-complete, and permitted by the declared authority graph.”

It cannot say:

> “Therefore the plan is correct,” “therefore Assurance passes,” “therefore execute,” “therefore promote,” or “therefore release.”

Those decisions stay with the existing families.

## 5. New External Core Coherence Fabric

### 5.1 Component Manifest

Add `nolane/external_core/component_contracts.py`.

Each canonical component publishes an immutable `ExternalComponentManifest` containing at minimum:

- `component_id`;
- `component_version`;
- `family` (`A`..`G`);
- `protocol_versions`;
- `consumes_contracts`;
- `produces_contracts`;
- `authority_capabilities`;
- `forbidden_authorities`;
- `mutable_resources`;
- `evidence_inputs`;
- `evidence_outputs`;
- `restore_protocol`;
- `compatibility_floor`;
- `compatibility_ceiling`;
- `manifest_digest`.

The manifest is descriptive and constraining. It cannot grant authority not already implemented by the canonical component.

All fields that affect authority are canonicalized and digest-bound.

### 5.2 Authority Graph

Add `nolane/external_core/authority_graph.py`.

The graph contains declared edges such as:

- `PROPOSES_TO`;
- `EVIDENCE_FOR`;
- `VERIFIES`;
- `ASSURES`;
- `AUTHORIZES_INPUT_TO`;
- `EXECUTES_FOR`;
- `OBSERVES`;
- `LEARNING_INPUT_TO`;
- `PUBLISHES_ARTIFACT_TO`;
- `REVOKES_DESCENDANTS_OF`.

The graph must reject:

- undeclared canonical writers;
- cycles in authority-escalating edges;
- an edge that makes a descriptive component authoritative;
- an edge that allows a component to self-verify or self-Assure when independence is required;
- duplicate ownership of the same canonical mutable resource;
- protocol ranges with no compatible intersection;
- forbidden authority appearing through transitive composition.

The graph answers structural questions only; it never creates a runtime decision.

### 5.3 Cross-Family Handoff Envelope

Add `nolane/external_core/handoff.py`.

`ExternalHandoffEnvelope` contains:

- `handoff_id` derived from canonical digest;
- `producer_component_id` and exact version;
- `producer_agent_id` where applicable;
- `consumer_component_id` and accepted protocol range;
- `subject_id`;
- `subject_digest`;
- `contract_kind` and version;
- `authority_class`;
- `source_state_digest`;
- `predecessor_handoff_ids`;
- `evidence_refs` plus evidence digests where available;
- `artifact_refs` plus artifact digests;
- `freshness_fence`;
- `epoch/fence` when the producer protocol owns one;
- `limitations` / `known_unknowns`;
- `payload_digest`;
- `envelope_digest`.

Consumer-side validation must recompute or re-resolve all authoritative bindings it has the ability to verify. Deserialization alone is never sufficient.

A handoff may be `INFORMATIVE`, `CANDIDATE`, `VERIFIED_INPUT`, or another explicit family-defined authority class, but the fabric cannot upgrade one class into another.

### 5.4 Cognitive Work Trace

Add `nolane/external_core/work_trace.py`.

A `CognitiveWorkTrace` records immutable cross-family lineage for one objective or task:

`A truth/evidence -> C reasoning/invention -> D goal/design -> E acting -> F engineering -> A verification -> B learning -> G durable artifacts/research/operations`

The trace is descriptive provenance only.

It supports:

- exact predecessor/successor relations;
- forks and competing branches;
- negative/aborted paths;
- supersession without deletion;
- link validation by digest;
- missing-link reporting;
- source revocation propagation status.

The trace must not become a universal workflow requirement. Families may operate independently when no cross-family task exists.

### 5.5 Capability Discovery

Add `nolane/external_core/capability_discovery.py`.

This exposes read-only introspection over manifests and authority graph so Planning/Reasoning can discover:

- which component supports a contract;
- required evidence/Assurance prerequisites;
- allowed authority class;
- side-effect/recovery semantics;
- version compatibility;
- whether a capability is currently unavailable due to drift, revocation, or incompatibility.

Discovery never executes, authorizes, promotes, or verifies.

### 5.6 Coherence Audit

Add `nolane/external_core/coherence_audit.py` and CLI entrypoint support:

`python -m nolane.external_core.audit --check`

Audit categories:

1. manifest validity;
2. authority ownership uniqueness;
3. forbidden authority composition;
4. protocol compatibility;
5. undeclared dependency detection;
6. orphan or stale handoffs;
7. provenance cycles;
8. revoked ancestor with live descendant;
9. stale evidence currentness;
10. restore-contract coverage;
11. duplicated semantic authority;
12. cross-family self-verification loops;
13. mutable dependency cycles;
14. missing negative/failure lineage;
15. component version drift against serialized state.

Audit output is machine-readable and deterministic. A clean audit is evidence of structural coherence only, not evidence that a task is correct.

## 6. G1 — Artifact Authority Upgrade

Upgrade `external.artifacts` from a basic content-addressed store to a governed artifact substrate.

### 6.1 Artifact Envelope v2

`ArtifactRecord` evolves into or is wrapped by an immutable `ArtifactEnvelope` with:

- artifact identity/digest;
- kind and schema version;
- producer component + producer agent;
- source state digest;
- payload/content digest;
- evidence refs and digests;
- predecessor artifact ids;
- dependency artifact ids;
- contract id/version;
- created logical epoch;
- currentness policy;
- confidentiality/export class if later required by an existing authority (descriptive only in A2);
- metadata digest.

Existing v0.0.1 records remain readable through a compatibility bridge but do not silently gain v2 authority properties.

### 6.2 Artifact Contract Registry

Add typed artifact contracts for:

- research synthesis;
- build/package;
- rollback/recovery material;
- evaluation report;
- execution output;
- engineering patch evidence;
- learning/experience export;
- generic informational artifact.

Contracts define required structural fields and evidence requirements. They do not assert truth.

### 6.3 Provenance Graph + Revocation Closure

Add `artifact_provenance.py`.

Properties:

- dependencies form an acyclic directed graph;
- registering an artifact against a revoked dependency fails closed;
- revoking a source/artifact creates an append-only revocation receipt;
- descendant currentness becomes invalid/requires reassessment according to dependency semantics;
- revocation does not delete history;
- supersession and revocation are distinct;
- the root cause/reason is preserved;
- revocation cannot be undone by reloading an old snapshot.

This concept is inspired by Nolane World's provenance closure but implemented under Nolane AI authority and Truth/Assurance semantics.

### 6.4 Current Artifact Assessment

Add categorical currentness states:

- `CURRENT`;
- `STALE`;
- `REVOKED`;
- `DEPENDENCY_INVALID`;
- `UNKNOWN`.

No scalar confidence is introduced.

The assessment revalidates:

- digest identity;
- dependency status;
- evidence availability/currentness when the owning family exposes it;
- contract version compatibility;
- predecessor baseline;
- revocation closure.

## 7. G2 — Operations / Runtime Infrastructure Upgrade

Operations becomes a durable control/evidence substrate for build/release/reliability operations, not a release governor.

### 7.1 Operational Journal

Add `operations_journal.py`.

All authority-significant operational transitions append canonical events to a hash chain:

- build registration;
- build reproduction;
- observability binding;
- release candidate registration;
- readiness assessment;
- operational incident;
- rollback/compensation observation;
- recovery checkpoint;
- revocation/supersession.

Properties:

- append-only;
- sequence monotonicity;
- previous digest binding;
- event digest binding;
- state-root binding where relevant;
- no duplicate semantic transition id with different content;
- exact replay must reconstruct equivalent operational state.

### 7.2 Operations Snapshot + Recovery Certificate

Add `operations_recovery.py`.

A snapshot binds:

- component versions;
- journal root/head;
- artifact graph digest;
- authority graph digest;
- active operation identifiers;
- release/readiness state root;
- current registry digest where relevant.

Recovery supports only:

- `EXACT` when snapshot/head matches;
- `FAST_FORWARD` when the snapshot history is a proven prefix of the journal;
- `QUARANTINED` for divergent/non-prefix/tampered histories.

Recovery never silently merges divergent authority histories.

A `RecoveryCertificate` proves the replay result and is content-addressed.

### 7.3 Operational Lease / Ownership Fence

For stateful infrastructure operations that can conflict, add a narrow lease/fence primitive:

- owner id;
- resource id;
- monotonically increasing fence epoch;
- issued logical time/epoch;
- expiry semantics where meaningful;
- predecessor owner/fence;
- release/terminal receipt.

This lease is only for G-owned operational resources. It does not replace E Acting workspace leases or F engineering claim leases.

Cross-family duplicate leases over the same conceptual resource are forbidden by the authority graph.

### 7.4 Observability v2

Upgrade `ObservabilityBundle` into a contract that binds:

- log schema;
- metric schema;
- trace schema;
- SLO/SLA refs where applicable;
- sampling policy;
- clock/time-source assumptions;
- source environment/build/release digest;
- data-loss/coverage declaration;
- evidence refs;
- currentness.

Observation availability is not equivalent to observation fitness. A Truth-family consumer must still apply A-family observation fitness rules.

### 7.5 Release Readiness Revalidation

Current readiness must not be permanently frozen by a historical receipt.

Add `assess_current_release_readiness()` that revalidates:

- artifact/package currentness;
- build reproduction receipt currentness;
- rollback artifact currentness;
- observability binding currentness;
- reliability evidence currentness;
- relevant Assurance disposition/currentness;
- component/contract compatibility;
- source/build baseline drift.

Possible result:

- `READY`;
- `READY_WITH_EXPLICIT_OVERRIDE` only when existing Assurance policy permits it;
- `BLOCKED`;
- `UNKNOWN` when required current evidence cannot be established.

## 8. G3 — Research Upgrade

Research becomes a full evidence-bounded research workflow while remaining subordinate to A Truth/Knowledge and C Experimentation/Causal.

### 8.1 Research Question Certificate

Add `research_protocol.py`.

A research program starts with a content-addressed certificate containing:

- question;
- decision/objective the research can change;
- scope;
- explicit unknowns;
- assumptions;
- at least one hypothesis;
- rival hypotheses for high-stakes/high-uncertainty cases;
- falsifiers;
- decisive tests/observations where available;
- stop/closure criteria;
- source hierarchy constraints;
- budget class;
- required independent stages.

The certificate is descriptive/planning evidence. It cannot itself authorize execution or settle truth.

### 8.2 Research Budget

Add `research_budget.py`.

Budget is finite and partitioned into explicit categories such as:

- explore;
- falsify;
- verify;
- replicate;
- integrate.

The allocator may use categorical stakes/uncertainty inputs or bounded numeric values only for resource allocation. Budget scores never become epistemic confidence.

Invariants:

- zero total budget means abstain/no research actions;
- non-zero budget cannot starve falsification for a high-stakes research question unless a documented exception contract applies;
- independent verification budget cannot be silently reallocated to self-confirmation;
- exhausted budget does not imply truth or successful closure.

### 8.3 Research Evidence Receipt

Add `research_evidence.py` or evolve `research_provenance.py` with a distinct receipt layer.

Each receipt binds:

- research question id;
- stage id;
- evidence kind;
- source id/version;
- content digest, not necessarily raw content;
- principal/producer;
- role;
- lineage;
- context/freshness;
- independence relation;
- observation completeness/fitness references when supplied by A;
- revocation status.

Research cannot declare an evidence item independent solely because it has a different receipt id.

### 8.4 Hypothesis Ecology

Research maintains explicit live/refuted/unsupported/superseded hypothesis state without deleting contradictory evidence.

Rules:

- rival hypotheses stay visible;
- supporting evidence for one hypothesis does not automatically refute rivals;
- decisive evidence semantics must be explicit;
- source correlation/dependence must be preserved;
- contradiction resolution is an append-only decision with evidence, not destructive replacement;
- high-stakes closure requires appropriate independent/challenge evidence.

### 8.5 Trial Ledger and Negative Results

Add append-only research trial records:

- planned hypothesis/test;
- method/protocol digest;
- environment/context;
- expected discriminating result;
- observed result refs;
- success/failure/invalid/inconclusive classification;
- reasons;
- causal/experimental authority refs when provided by C;
- evidence refs.

Failed and negative trials are first-class outputs and remain discoverable.

### 8.6 Research Closure Certificate

Add categorical closure:

- `CLOSED_SUPPORTED`;
- `CLOSED_REFUTED`;
- `CLOSED_BOUNDED_UNCERTAINTY`;
- `ABSTAIN_UNRESOLVED`;
- `OPEN`.

Closure requires the declared gates in the Research Question Certificate to be satisfied.

Examples of possible gates:

- provenance coverage;
- rival-hypothesis treatment;
- falsification attempt;
- independent evidence stage;
- contradiction treatment;
- freshness/currentness;
- limitation disclosure;
- research budget accounting;
- relevant A Verification/Assurance reference for authority-significant downstream use.

“Enough links were found” is never a closure criterion.

### 8.7 Research Handoff v2

Replace ambiguous synthesis transfer with a cross-family ECF handoff bound to:

- synthesis artifact;
- research closure certificate;
- current source/finding digests;
- limitations;
- target component and contract;
- authority class;
- Assurance reference when an authorizing handoff requires it.

An informative research handoff remains informative even if downstream code serializes it differently.

## 9. G4 — Infrastructure Research/Artifact Integration

G's three subfamilies should compose without collapsing into one authority.

### Allowed composition

Research may publish contract-valid artifacts.  
Operations may consume artifact identities and research outputs as evidence inputs.  
Artifact provenance may point to operations/research receipts.  
Operations recovery may bind artifact graph state.  
Research closure may reference current artifacts and operational observations.

### Forbidden composition

- artifact existence cannot make a research claim true;
- research closure cannot release software;
- release readiness cannot make a truth claim VERIFIED;
- an Operations receipt cannot substitute for Assurance;
- a Research receipt cannot substitute for C Experimentation/Causal authority;
- G cannot promote Skills or capabilities directly;
- G cannot execute E actions or mutate F patches.

## 10. Cross-Family Integration Contracts

The first A2 contract set should include:

### A -> G

A exposes current evidence/verification/Assurance references that G may bind but not reinterpret.

### G -> A

G exposes artifacts, observations, source provenance, research receipts, operational outcomes, and revocation lineage for A to evaluate.

### B -> G

B may publish experience/skill-learning artifacts and provenance snapshots.

### G -> B

Only verified/current operational or research outcomes can be nominated as learning inputs; G cannot promote them.

### C -> G

C may provide hypothesis, causal program, experiment design/result, capability-candidate, and transfer references.

### G -> C

G may provide research evidence, reproducible artifacts, observations, prior trials, and negative-result lineage.

### D -> G

D may provide requirements/planning/architecture contracts and expected operational/research obligations.

### G -> D

G returns current feasibility evidence, research closure, build/release state, and provenance—not strategic authorization.

### E -> G

E emits execution receipts/outcomes that G can preserve and operationally observe.

### G -> E

G may provide build/release/artifact/recovery inputs but cannot authorize execution.

### F -> G

F emits patch/claim/debug/UI evidence artifacts and engineering baselines.

### G -> F

G provides research, build, release, observability, incident, and artifact lineage inputs. F retains engineering mutation authority.

## 11. Global Restore Preflight

Add `nolane/external_core/restore_preflight.py`.

Before a cross-family state becomes current authority after restore, preflight checks:

- component manifest digests;
- authority graph digest;
- component versions and compatibility ranges;
- artifact provenance graph/root;
- live handoff lineage;
- revocation closure;
- per-family state digests supplied by their canonical restore APIs;
- active lease/fence epochs for G-owned resources;
- current registry/core contract references where applicable.

Preflight output:

- `CURRENT_COMPATIBLE`;
- `READ_ONLY_LEGACY`;
- `REQUIRES_REVALIDATION`;
- `QUARANTINED`.

The preflight cannot upgrade legacy state to current authority; it may only constrain usability.

## 12. Compatibility Strategy

A2 must not break Epoch-0 serialized data unnecessarily.

Rules:

1. old v0.0.1 G state can be inspected/restored through compatibility loaders;
2. old state does not gain new currentness, closure, independence, or authority semantics merely by loading;
3. new authority-significant APIs emit v2/A2 records only;
4. if an old record lacks required provenance, current assessment returns `UNKNOWN`, `REQUIRES_REVALIDATION`, or a family-specific blocked state rather than inventing evidence;
5. migrated compatibility code is isolated and cannot mint new canonical authority;
6. component versions are advanced only when public semantic boundaries actually change.

## 13. Security / Integrity Invariants

A2 adds no new network security claim, but all serialized authority-bearing structures must defend against:

- bool-as-int confusion;
- NaN/Infinity and non-canonical numeric values;
- duplicate ids with different payloads;
- duplicate JSON keys where parsing path can expose them;
- unknown authority-significant fields;
- digest truncation collisions where full digest is required;
- forged predecessor ids;
- reordered evidence lists when order is semantically irrelevant;
- order tampering when order is semantically relevant;
- stale/future logical epochs;
- version downgrade;
- incompatible protocol substitution;
- partial-state restore;
- missing revocation history;
- source/artifact rebinding;
- self-issued independence labels;
- self-Assurance loops;
- cross-family authority escalation through a generic handoff.

## 14. Testing Strategy

Implementation is TDD-first. Each semantic increment begins with RED tests.

### 14.1 G artifact tests

- content-addressed id rebinding rejection;
- artifact contract required-field rejection;
- provenance cycle rejection;
- revoked ancestor poisons descendant currentness;
- supersession is not deletion;
- v0.0.1 compatibility does not mint v2 authority;
- restore recomputes digest/currentness.

### 14.2 G operations tests

- journal append/hash-chain integrity;
- exact replay;
- fast-forward replay;
- divergent history quarantine;
- stale lease/fence cannot mutate G resource;
- historical READY becomes blocked after artifact/reliability/Assurance drift;
- observability presence does not equal observation fitness;
- rollback artifact drift blocks current readiness.

### 14.3 G research tests

- high-stakes question without rivals rejected;
- budget exhaustion does not imply closure;
- falsification budget cannot be silently starved;
- source freshness drift reopens/blocks current closure;
- correlated evidence cannot self-label independent;
- negative trials remain after restore;
- contradiction is preserved;
- authorizing handoff requires exact applicable Assurance/current closure;
- informative handoff cannot be deserialized as authorizing;
- revoked evidence poisons dependent research closure.

### 14.4 ECF tests

- manifest digest tampering;
- duplicate canonical writer detection;
- forbidden transitive authority escalation;
- self-verification/Assurance loop detection;
- incompatible protocol range;
- stale handoff rejection;
- producer version drift;
- predecessor chain tampering;
- artifact/evidence digest mismatch;
- restore preflight partial state;
- read-only legacy behavior;
- audit deterministic output.

### 14.5 Cross-family adversarial matrix

Permanent contract tests cover at least:

- A -> C;
- C -> D;
- D -> E;
- E -> F;
- F -> A;
- A -> B;
- B -> C;
- C -> G;
- G -> A;
- G -> D;
- G -> E;
- G -> F.

Each edge receives tests for:

- stale evidence;
- revoked source;
- version drift;
- forged authority class;
- restore/replay;
- missing predecessor;
- duplicate id;
- failure/negative path preservation.

## 15. CI / Acceptance Gates

A2 is not accepted merely because new tests pass.

Required gates:

1. all existing Epoch-0 suites remain green;
2. all existing A–F family-specific suites remain green;
3. new G suites pass on the repository-supported Python matrix;
4. ECF cross-family matrix passes;
5. `nolane.repository.audit --check` remains green;
6. new External Core coherence audit passes;
7. compatibility restore tests prove old G state cannot gain authority silently;
8. serialization round-trip tests prove exact digest stability;
9. mutation/tamper tests fail closed;
10. CURRENT architecture docs are updated only after implementation evidence exists.

## 16. Implementation Decomposition

This architecture is too large for one unsafe mega-patch. It will be implemented as a sequence of evidence-closed waves, each independently testable and reviewable.

### Wave G1 — Artifact Integrity

- artifact v2 envelope/contract;
- provenance graph;
- revocation closure;
- currentness;
- compatibility bridge;
- focused tests.

### Wave G2 — Research Integrity

- question certificate;
- budget;
- evidence receipt;
- hypothesis/trial lifecycle;
- closure certificate;
- handoff v2;
- focused tests.

### Wave G3 — Operations Integrity

- operational journal;
- snapshot/recovery certificate;
- G-local lease/fence;
- observability v2;
- current release readiness;
- focused tests.

### Wave X1 — External Core Component Contracts

- manifests;
- authority graph;
- capability discovery;
- audit skeleton;
- no cross-family runtime mutation.

### Wave X2 — Cross-Family Handoff + Work Trace

- envelope;
- validators;
- provenance trace;
- cross-family contract adapters;
- adversarial tests.

### Wave X3 — Restore Preflight + Full Coherence Audit

- global preflight;
- legacy/read-only classifications;
- full audit;
- deterministic machine-readable report;
- final A2 acceptance matrix.

Ordering rationale: G is the weakest current family and becomes the first proving ground for the common contracts. The generic fabric is introduced only after G has concrete, tested semantics to describe; this avoids inventing abstract framework code without real consumers.

## 17. Explicit Non-Goals

A2 does not:

- create an eighth External Core family;
- centralize A–G under one autonomous orchestrator;
- replace Assurance;
- replace Truth/Knowledge currentness rules;
- replace C Experimentation/Causal;
- replace D Planning/Architecture;
- replace E Acting leases/executor;
- replace F engineering claims/patches/control;
- introduce distributed consensus or Byzantine fault tolerance;
- claim AGI or universal reasoning gains;
- treat Nolane World as runtime authority;
- automatically modify Neural Core;
- automatically promote Skills, capabilities, policies, or transfer objects.

## 18. Success Criteria

A2 is successful when all of the following are true:

1. every canonical A–G component can declare a machine-readable contract without granting itself extra authority;
2. cross-family handoffs are exact, content-addressed, version-bound, provenance-bound, and consumer-revalidated;
3. G artifacts can be invalidated/revoked transitively without deleting history;
4. G operational state can be replayed and recovered with authenticated deterministic lineage;
5. historical operational readiness cannot remain authoritative after relevant current state drifts;
6. G research has explicit questions, rivals, falsifiers, budgets, negative trials, closure, and independent-stage semantics;
7. G research cannot substitute its own receipts for A/C authority;
8. restore cannot silently combine locally valid but globally inconsistent family states;
9. the coherence audit detects duplicate writers, self-verification loops, stale handoffs, revocation leaks, compatibility drift, and forbidden authority composition;
10. all existing A–F invariants and Epoch-0 acceptance remain green.

## 19. Architectural Law

The core A2 law is:

> **External Core strength comes from composable verified boundaries, not from accumulating unchecked authority.**

A family may become more capable, but every new capability must make its inputs, outputs, authority, provenance, currentness, failure semantics, and restore semantics more explicit—not less.
