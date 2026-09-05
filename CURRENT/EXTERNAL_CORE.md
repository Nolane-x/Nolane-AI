# External Core

External Core is the complete non-neural capability substrate. Tools are one subtype inside it, not a peer architecture layer.

`shared/external-core/manifest.json` owns the general capability/tool floor. Each region manifest owns accepted regional External Core bindings. Each AI profile has independent private External Core and private tool-permission slots.

Wave 3 does not fabricate private capabilities. Central's already-accepted Central-only tools and three Central External Core bindings are represented as Central-private source. Chiefs and Specialists begin with empty private External Core/tool lists where accepted evidence contained only regional capabilities; their private slots are explicit and can evolve later.

Effective capabilities are computed by the resolver from shared + regional + private source. Compatibility projections preserve accepted runtime tool permissions and External Core bindings exactly.

Canonical External Core cognitive authorities are independently versioned semantic boundaries rather than one monolithic tool layer. `nolane.external_core.causal` owns bounded causal intervention/program structure, while `nolane.external_core.experimentation` owns finite behavioral version spaces, deterministic informative-probe selection, budgeted pure shadow experiments, independent verification receipts, and evidence-bound experiment ledger state. Experimentation does not own candidate generation or capability acquisition, promotion authority, or cross-domain transfer/meta reuse; those remain separate component boundaries so later extraction cannot silently widen Experimentation's authority.

Experiment receipts persist the canonical version-space hypothesis IDs, selection-probe IDs, verification-probe IDs and selection budget that define their semantic experiment identity. Restore recomputes the content-addressed experiment ID from that envelope before a receipt can be admitted to deterministic ledger state, so changing a serialized experiment ID cannot silently create a new accepted identity.

## Candidate synthesis

`external.candidate_synthesis` is canonical-native at v0.0.4 as the stateless proposal-generation boundary upstream of Capability Acquisition. The original v0.0.1 composition mode remains backward-compatible: it composes two or more existing unary learned abstractions in semantic source order. Composition is built as transient canonical `AbstractionCall` IR, expanded against the exact Cognitive Library vocabulary, and emitted as a standalone one-parameter `LearnedAbstraction` before conversion through the existing `CapabilityCandidate` contract. This keeps candidate decoding self-contained and does not widen Capability Acquisition to carry hidden source dependencies.

The v0.0.2 bounded-search mode also remains backward-compatible. It canonicalizes an unordered source pool by abstraction identity, enumerates ordered pairs without replacement, applies `generation_budget` as a hard hypothesis cap, and ranks observed novel candidates by lower expanded template cost, then broader support-task coverage, then canonical candidate identity. Its established within-budget selection and `no_novel_candidate_within_budget` abstention semantics are unchanged.

v0.0.3 adds `PROGRESSIVE_MULTI_DEPTH_SEARCH`. This mode enumerates ordered source permutations without replacement from depth 2 through the size of the canonical source pool and advances only after a shallower frontier has been searched completely and produced no novel candidate. The first fully searched depth containing novel proposals is ranked with the existing structural tuple and supplies the winner. A budget cut through a frontier never authorizes a partial winner or descent to a deeper frontier: synthesis instead abstains with `generation_budget_exhausted`. Only complete exhaustion of every permitted depth with no novel proposal yields `no_novel_candidate`. Generated intermediate compositions never enter Cognitive Library or same-call vocabulary; a deeper proposal such as `A -> B -> C` is built directly as transient synthesis IR and fully expanded into one standalone candidate.

v0.0.4 adds `STRUCTURAL_COMPOSITION_PROGRAM`, an explicit general structural-composition mode for installed learned abstractions of arbitrary arity. Its protocol is intentionally separate as `candidate-synthesis-v2`; the three legacy modes and their exact request/receipt state remain on `candidate-synthesis-v1`. A structural request carries a canonical finite tree made only from indexed input placeholders and calls to exact installed learned abstractions. Source IDs are derived from the tree rather than trusted from caller metadata, used input indices must be contiguous from zero, and the protocol is bounded to 256 structural nodes and depth 64. Library-bound validation separately checks exact source existence, source arity and the reserved temporary-field namespace.

Structural compilation lowers the canonical tree to transient `AbstractionCall` IR, expands it against the exact current Cognitive Library vocabulary under the existing 10,000-node expansion ceiling, binds temporary input fields to `TemplateParam` indices, and emits one standalone `LearnedAbstraction`. This supports nullary, unary, binary and higher-arity wiring such as combining two independently transformed inputs or nesting multi-input calls. Repeated use of a source or input is legal. Generated intermediates never enter Cognitive Library or a same-call shadow vocabulary, and no unresolved abstraction call or synthesis-reserved field may survive candidate emission.

An explicit structural program is exactly one hypothesis: zero generation budget abstains before an attempt, while any positive budget authorizes exactly one attempt and never creates hidden search. Structural receipts bind the full canonical wiring tree in their semantic identity, so two different programs may legitimately produce the same final candidate identity while retaining distinct synthesis receipt identities and provenance. Restoration recomputes derived source IDs and rejects non-canonical or tampered state, including boolean values smuggled into integer budget fields.

Candidate Synthesis accepts discovery-phase evidence only. Independent-challenge and final-Assurance evidence are forbidden from generation, while experiment-receipt and causal-program IDs are provenance references without authority. Legacy requests and receipts remain immutable/content-addressed under `candidate-synthesis-v1`; structural requests and receipts are independently immutable/content-addressed under `candidate-synthesis-v2`. The component stores no ledger, verifies that Cognitive Library digest is unchanged across synthesis, and has no API that can admit, probation, promote, quarantine, self-assure, mutate the library, or mutate the frozen neural asset. Search ranking or structural wiring does not execute Assurance or consume final-verification evidence. A proposal enters lifecycle state only when a caller separately invokes Capability Acquisition.

## Reasoning / invention protocol

`external.reasoning_invention` is canonical-native at **v0.0.5** as the immutable protocol family for C. Reasoning / Invention. Existing C1–C10 schemas are retained, while v0.0.5 adds the independently content-addressed `reasoning-policy-qualification-v1` evidence protocol. It does not replace Cognitive Library, Candidate Synthesis, Capability Acquisition, Causal, Experimentation, Transfer/Meta, D Goal/Design, E Acting or Assurance, and it owns no write-through lifecycle authority.

The C1 spine separates discovery, independent challenge and final Assurance evidence. `InventionHypothesis` carries explicit assumptions, generalized variables, invariants, predicted metric deltas and an executable `VerificationPlan`; `InventionAssessment` keeps evidence alignment, anomaly coverage, expected gain, robustness, transferability, uncertainty, complexity and verification cost as separate dimensions. Candidate and reasoning-action selection use deterministic Pareto dominance rather than a hidden global utility score. `CapabilityGap` and `TransferIntent` remain downstream intent envelopes only.

v0.0.5 retains the bounded **Reasoning Ecology** introduced by C8 around that spine. `reasoning_frontier-v1` records decision-relevant unknowns, structurally distinct rival hypotheses, assumptions, hard constraints and an explicit branch budget, and supports frontier-bound assumption inversion and representation shift without turning either operation into truth authority. `reasoning-metacontrol-v1` evaluates proposed reasoning moves using separate expected decision value, information gain, uncertainty reduction, cost and residual-risk dimensions. Its terminal states distinguish `CONTINUE`, `HALT_NO_FURTHER_VALUE` and fail-closed `ABSTAIN_UNRESOLVED`, so exhausted compute cannot be misrepresented as confidence while a decision-overturning unknown remains.

`reasoning-review-v1` provides fresh-context adversarial review envelopes with producer/reviewer and session separation, auditable withheld-rationale boundaries, required checks, reproduced evidence and explicit specification-gaming findings. A scope-supported review cannot contain objections, counterexamples or blocking gaming findings and does not mint Assurance. `reasoning-meta-learning-v1` compiles C7-linked reasoning-action outcomes into descriptive learning evidence such as decision correctness, information efficiency, regressions, generalization and robustness; it exposes no policy-update, model-write, Cognitive Library registration, promotion or transfer-acceptance path.

C10 adds governed metareasoning policy evolution without creating self-modification authority. `reasoning-policy-evolution-v1` binds immutable one-step policy lineage, constraint-only budget/action-kind tightening, disjoint development/holdout evidence, Pareto shadow evaluation, self-contained fresh-context review provenance, and exact externally authorized adoption/rollback. Reasoning/Invention cannot self-authorize, maintain a mutable current-policy governor, relax caller safety bounds, or treat policy adoption as Assurance.

C11 adds exact-context counterfactual policy qualification: matched holdout trials, derived effect vectors, exact regime scope, tail-regression blocking and fail-closed `ABSTAIN_OUT_OF_SCOPE` applicability evidence. It requires an already externally adopted C10 policy and grants no routing, execution or Assurance authority.

C9 adds replayable reasoning episodes above those immutable C8 objects. `reasoning-episode-v1` binds an exact root/current frontier, monotonic generation, Pareto-authorized selected actions, evidence-carrying semantic frontier deltas and transition-derived action/cost budgets. It rejects stale frontier/control authority, duplicate action consumption, context drift and forged replay snapshots. Observed cost overruns are recorded rather than clipped and terminalize as fail-closed budget-overrun abstention; exact exhaustion still requires an explicit C8 halt/abstain decision. Episode status never means acceptance, promotion or successful execution.

`nolane.external_core.reasoning_evaluation` closes the fixed-budget evaluation loop for Reasoning/Invention v0.0.5. Together these protocols produce an auditable chain from evidence and hypotheses through unknown/rival management, causal or experimental challenge, fresh review, acquisition/transfer intent and outcome evidence, while every mutable authority remains with its existing canonical owner. All derived identities are recomputed on restore, set-like provenance is canonicalized, non-finite/invalid numeric inputs fail closed, and forged or non-canonical state is rejected.

## Capability acquisition

`external.capability_acquisition` is canonical-native in Wave 5AX. It is a control-plane governor over `external.cognitive_library` and `external.assurance`: candidate generation happens upstream; admitted candidates enter probation against an exact library baseline; independent/challenge/reliability evidence must pass; promotion requires the exact persisted native Assurance receipt bound to the same candidate, evidence set and predecessor baseline. Failed gates quarantine without library mutation. Only promoted records cross the acquisition retrieval firewall, and a post-promotion live failure revokes that visibility even though the Cognitive Library itself remains append-only.

## Transfer/meta reuse

`external.transfer_meta` is canonical-native in Wave 5AY. It consumes only externally verified successful canonical Experience attribution, emits an identity-free portable semantic payload plus a separate content-addressed source-authority receipt, optionally binds an accepted canonical Causal program, and deterministically adapts the portable lesson to a distinct destination domain. Accepted reuse is not caller-authorized: it requires the exact persisted native Assurance promotion receipt bound to the transfer subject, evidence set, predecessor/source authority and verifier identities. Negative-transfer evidence quarantines and revokes reuse. Snapshot restoration re-compiles native source authority and therefore rejects same-ID source rebinding or drift instead of trusting serialized authority claims.

## Post-Epoch-0 A2 — External Core Coherence Fabric

A2 is an explicit post-Epoch-0 interoperability and integrity program. It is **not** a new External Core family, not an H-layer governor, and not a replacement for any A–G canonical authority. Its job is to make independently governed components understand exact contracts, lineage, currentness, restore boundaries and authority limits across family boundaries without creating a central super-authority.

### G infrastructure progression

A2 strengthens G first because cross-family cognition cannot be reliable when its artifacts, research records or operational recovery semantics are weaker than the authorities they carry between.

`external.artifacts` retains its legacy v0.0.1 API and adds the separate `ArtifactEnvelope` protocol version 2. V2 envelopes are content-addressed over producer/component identity, source-state digest, exact evidence-digest bindings, dependency/predecessor lineage, contract identity, epoch/currentness limits and canonical metadata. Restore recomputes the envelope identity and rejects semantic rebinding. `ArtifactProvenanceGraph` is append-only, rejects cycles, carries revocation/supersession receipts, and propagates dependency invalidity. Legacy/empty artifact-store serialization remains byte-semantically compatible and does not materialize empty A2 fields into the canonical organization runtime state.

Research adds explicit content-addressed question/hypothesis contracts, rival hypotheses and falsifiers for high-stakes work, an exactly partitioned finite research budget, append-only positive/negative/failed/inconclusive trials, and categorical research closure. Research closure is `CLOSED`, `BLOCKED` or `UNKNOWN`; it is never Truth, Verification, Assurance, promotion or execution authority. `ResearchControlPlane.assess_current_handoff` revalidates current finding/provenance/artifact/Assurance state so a historically `AUTHORIZED` handoff cannot remain authoritative after stale, rejected or incomplete current evidence.

Operations adds a replay-verifiable hash-chained journal, exact snapshots, `EXACT`/`FAST_FORWARD`/`QUARANTINED` recovery, monotonic G-only operational lease fencing, and current release-readiness assessment. Divergent history, registry drift, authority-graph drift or incompatible state is quarantined instead of auto-merged. G operational leases do not replace E workspace leases or F engineering claim leases.

### Federated component contracts and authority graph

`ExternalComponentManifest` declares component/family/version, protocol versions, produced/consumed contracts, allowed and forbidden authority capabilities, mutable resources, evidence I/O, restore protocol and exact compatibility range. Manifests are immutable and self-digesting.

`ExternalAuthorityGraph` is descriptive/constraining. It detects duplicate canonical writers, undeclared producer/consumer contract edges, forbidden authority composition, self-verification/self-Assurance loops and directed authority-escalation cycles. The graph can refuse an incoherent composition but cannot authorize a task, execute an action, verify a claim, issue Assurance, promote a capability or mutate a canonical resource.

### Typed cross-family handoff

`external-handoff-v1` is the common content-addressed envelope for cross-family transfer. It binds producer component/version/agent, consumer and contract range, subject digest, authority class already obtained from an external canonical owner, exact source-state digest, evidence and artifact digest bindings, predecessor handoffs, freshness fence, limitations, known unknowns and canonical payload digest.

Consumer validation always rechecks the current producer/consumer manifests, exact contract/version range, source state, evidence/artifact digests, predecessor existence and freshness fence. Missing required current proof yields `UNKNOWN`; semantic drift or authority overreach yields `BLOCKED`; only exact current compatibility yields `ACCEPTED`. An envelope's authority-class field describes the authority supplied by its canonical producer; it never creates that authority by itself.

### Cognitive work trace

`cognitive-work-trace-v1` is an append-only, content-addressed descriptive DAG. It retains forks, counterexamples, blocked/aborted/negative nodes and separate supersession receipts. Trace restoration recomputes node identity, verifies predecessor closure and rejects cycles. The trace exposes no authorize, promote or execute API; provenance visibility must never be confused with control authority.

### Capability discovery, restore preflight and coherence audit

`CapabilityDiscoveryIndex` is read-only. It can answer which components declare a contract or authority, their evidence prerequisites and restore semantics, but it exposes no invocation path.

`external-core-restore-preflight-v1` binds registry digest, authority-graph digest, artifact-graph digest, handoff-frontier digest and exact component versions. Any drift is a fail-closed restore rejection; a locally valid component state cannot silently become globally authoritative under a different fabric state.

`external-core-coherence-audit-v1` deterministically surfaces authority-graph findings, manifest/graph drift, duplicate identities, orphan or stale/unknown handoffs, missing trace links and negative lineage without retained evidence. `python -m nolane.external_core.audit --check` is read-only and exits non-zero on findings; `--json` emits the canonical report. There is intentionally no audit write/repair mode.

### Structural coherence is not correctness or authority

**ECF structural coherence does not mean task correctness, Truth, Verification, Assurance, authorization, promotion, successful execution, release readiness or deployment approval.** A clean authority graph means only that declared authority ownership and contract composition are structurally coherent. An `ACCEPTED` handoff means only that the envelope is currently compatible with its declared producer/consumer contract and current evidence bindings. A clean work trace means only that provenance is internally well-formed. All semantic correctness and mutable authority remain with their existing A–G canonical owners.

The permanent adversarial matrix covers A→C, C→D, D→E, E→F, F→A, A→B, B→C and C→G plus a full-loop trace. It rejects digest tampering, stale evidence, contract downgrade, producer upgrade during handoff, registry/source-state drift, boolean-as-integer and non-finite scalar smuggling, partial restore snapshots, replay forks, duplicate writers and self-verification laundering. No arrow in that matrix grants write authority.

## Post-Epoch-0 A3 — Canonical Registry & Live Coherence

A3 binds the A2 coherence protocols to the canonical External Core component population and to an explicit live fabric frontier. Its governing law is: **Registration proves identity and declared compatibility; registration never creates authority.** A3 is not family H, a global governor, an orchestrator, an invoker, a repair service, or a runtime authorization plane.

### Canonical component registry

`ManifestAdapter` is an immutable, content-addressed binding between a canonical source locator, the source component's exact `COMPONENT_ID`/`COMPONENT_VERSION`, and its A2 `ExternalComponentManifest`. Adapter creation rejects identity or version substitution; exact restore recomputes the digest and rejects non-canonical state. The pre-existing `nolane.external_core.registry` organization-identity compatibility bridge remains intact.

`CanonicalComponentRegistry` is a deterministic, content-addressed registry of those adapters. It rejects duplicate component identities, adapter identities and source locators, supports categorical coverage findings for missing/orphan adapters and identity/version drift, and provides read-only manifest/adapter lookup. The canonical builder reads component identity and version from the live canonical modules on every build rather than duplicating those values in an A3 version table.

The canonical A–G interoperability profile and authority graph are now derived from this registry. A registered manifest may describe authority already owned by its component, but registry presence cannot manufacture Verification, Assurance, authorization, promotion, execution, learning, release, deployment or mutation authority.

### Live fabric snapshot and restore currentness

`external-core-live-fabric-v1` binds registry digest, authority-graph digest, artifact-currentness view digest, domain-separated handoff frontier, work-trace frontier, source-state frontier and exact component versions into a content-addressed `LiveExternalCoreSnapshot`. Frontier construction is deterministic and rejects non-finite state, duplicate semantic entries and ambiguous/non-canonical identity fields.

A3 restore assessment is categorical. `CURRENT` means the historical snapshot exactly matches every supplied current structural proof and is the only structurally authoritative restore disposition. `REQUIRES_REVALIDATION` means a valid historical snapshot has registry, graph, frontier or component-version drift. `QUARANTINED` means serialized snapshot integrity is invalid. `UNKNOWN` means required current proof is absent. None of these dispositions is Truth, Verification, Assurance, task authorization, execution success or release approval.

### Registry-bound discovery and live audit

`RegistryCapabilityDiscoveryIndex` binds the existing read-only capability discovery surface to both an exact registry digest and exact authority-graph digest. Restore revalidates the embedded registry, legacy discovery state and graph digest. It exposes description and lookup only; it has no invoke, execute, authorize, promote, repair or runtime-registration API.

`audit_live_external_core` layers live registry/snapshot validation over the A2 coherence auditor. It detects registry/graph population drift, registry substitution, authority-graph substitution, artifact-currentness drift, handoff/work-trace/source-state frontier substitution and mixed component versions, while retaining A2's handoff, trace and authority-graph adversarial checks. The canonical CLI now runs this registry-backed live audit while preserving `run_canonical_audit()` as a compatibility entry point.

### Capability metadata binding remains descriptive

`CapabilityCatalogBindingReceipt` content-addresses the organization External Core capability-catalog digest together with the registry digest and hard-binds `descriptive_only=True`. It exists for provenance/reconciliation only. Agent capability metadata, regional bindings or catalog membership cannot be translated by A3 into component authority, invocation rights or authorization.

### A3 authority boundary

A3 may identify the current canonical topology, prove exact registry/snapshot identity, describe declared capabilities, and fail closed on structural drift. It may not invoke a component, select or authorize a task, verify a claim, issue Assurance, promote learning, mutate canonical A–G state, repair an incoherent fabric, release software or deploy anything. **Live coherence is a stronger structural precondition, not a new source of semantic authority.**