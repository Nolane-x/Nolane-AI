# Architecture & Integration Intelligence Part IV — Design Specification

## Status and authority

This specification implements GitHub Issue #132 on top of accepted Parts I–III. It preserves existing authority boundaries: `architecture.chief` owns the canonical architecture state; `integration.chief` owns canonical integration/change-control state. Nolane Central may observe, challenge, prioritize, or issue an audited override through existing Part-II authority, but it does not silently convert proposals into accepted architecture.

No AGI/frontier-equivalence claim is introduced. Part IV establishes bounded, machine-auditable architecture and integration governance.

## Goal

Prevent a locally-correct patch, feature, API change, migration or refactor from silently damaging global system structure.

Part IV introduces four cooperating authorities:

1. **ArchitectureGraph** — canonical modules, components, interfaces, dependency/trust boundaries and versions.
2. **Architecture Decision Ledger (ADR Ledger)** — immutable evidence-bearing architectural decisions and supersession history.
3. **ChangeImpact Engine** — deterministic blast-radius analysis from a proposed structural/API/schema change.
4. **IntegrationGraph** — candidate changes, dependency/order constraints, compatibility gates and merge/integration decisions.

Architecture Chief and Integration Chief remain direct technical workers. They may personally design/review/repair difficult system changes; delegation is optional scale, not their only function.

## Approaches considered

### A. Put architecture metadata into MasterPlanGraph

Rejected. Plans answer *what work should happen*; architecture answers *what structural invariants and contracts the system must preserve*. Combining them would blur ownership and make a plan edit equivalent to an architecture mutation.

### B. Infer architecture only from repository source on demand

Rejected as the sole authority. Static/source inference is valuable evidence but cannot represent intended boundaries, compatibility commitments, trust zones or accepted exceptions that are not mechanically obvious from code.

### C. Separate versioned ArchitectureGraph + IntegrationGraph, linked to Requirements/Planning/TaskGraph — chosen

This keeps structural intent, delivery intent and execution state independently versioned and testable. Source/repository analysis becomes evidence used to reconcile the graph rather than the graph being a transient inference.

## 1. ArchitectureGraph

### 1.1 Architecture component

Each component record contains:
- `component_id`;
- name/title;
- component kind (`SERVICE`, `MODULE`, `LIBRARY`, `UI`, `DATA_STORE`, `RUNTIME`, `EXTERNAL`, `BUILD`);
- owning region/agent;
- lifecycle state (`ACTIVE`, `DEPRECATED`, `SUPERSEDED`, `REMOVED`);
- public interface ids;
- dependency component ids;
- trust zone;
- requirement refs;
- plan refs;
- source/artifact refs;
- evidence refs.

### 1.2 Interface contract

Each interface has:
- `interface_id`;
- producer component;
- consumer scope;
- interface class (`API`, `EVENT`, `SCHEMA`, `FILE`, `CLI`, `LIBRARY`, `UI_CONTRACT`);
- semantic version;
- canonical signature/schema digest;
- compatibility policy;
- stability (`PRIVATE`, `INTERNAL`, `PUBLIC`);
- trust/security classification;
- evidence refs.

### 1.3 Architecture edges

Edges are typed rather than generic strings:
- `DEPENDS_ON`;
- `CALLS`;
- `READS`;
- `WRITES`;
- `EMITS`;
- `CONSUMES`;
- `IMPLEMENTS`;
- `HOSTS`;
- `TRUSTS`.

The graph rejects unknown endpoints and declared forbidden dependency cycles. Cycles are not universally illegal: a policy layer defines which edge kinds may participate in cycles. `DEPENDS_ON` must be acyclic for first-generation Part IV.

## 2. Architecture revisions

Every accepted architecture mutation creates an immutable revision with:
- monotonically increasing version;
- parent version;
- actor;
- reason;
- evidence refs;
- proposal/event refs;
- changed components/interfaces/edges;
- affected requirement/plan refs;
- canonical graph digest.

Mutation rules:
- `architecture.chief` is normal owner;
- non-owner agents may only emit proposals/concerns;
- empty reason/evidence fails closed;
- invalid references/cycles fail atomically with byte-for-byte state preservation;
- rollback creates a new revision sourced from a prior accepted revision; no history deletion.

## 3. ADR Ledger

An ADR is not free-form documentation only. It is a structured immutable decision:
- `adr_id`;
- title/question;
- context;
- considered alternatives;
- chosen decision;
- rejected alternatives with rationale;
- constraints/invariants introduced;
- requirement/plan/component/interface refs;
- evidence refs;
- author/reviewers;
- status (`PROPOSED`, `ACCEPTED`, `SUPERSEDED`, `REJECTED`);
- supersedes/superseded-by;
- canonical digest.

Only an accepted ADR may authorize a deliberate exception to an architecture policy. A coder cannot create an exception by commenting it in source.

## 4. Architecture concern/proposal flow

Any agent may observe a structural issue and emit an `ARCHITECTURE_CONCERN` containing:
- source agent;
- task/plan refs;
- affected components/interfaces;
- observation;
- proposed alternatives;
- evidence refs;
- confidence/severity.

The event does not mutate ArchitectureGraph.

Architecture Chief may:
- reject the concern with evidence;
- ask Research/Debug/Verification for more evidence;
- author an ADR;
- accept an architecture revision;
- generate downstream change requirements for Planning/Integration/Security/Verification.

## 5. ChangeImpact Engine

A proposed architecture change is compiled into a deterministic **ImpactPacket**.

Inputs:
- current ArchitectureGraph revision;
- proposed component/interface/edge delta;
- current RequirementGraph/MasterPlanGraph refs;
- IntegrationGraph candidate state;
- optional repository/symbol observations from future Coding/Research parts.

Output fields:
- directly changed components/interfaces;
- transitive dependent components;
- requirement refs at risk;
- plan nodes/tasks potentially affected;
- compatibility obligations;
- security/trust-boundary impact;
- data/schema migration impact;
- test/verification classes required;
- severity/risk score derived from declared factors;
- deterministic digest.

The engine provides evidence and impact scope. It does not itself authorize the architecture change.

## 6. Compatibility contracts

Part IV introduces explicit compatibility assessment rather than a Boolean guessed by an agent.

Compatibility classes:
- `COMPATIBLE`;
- `BACKWARD_COMPATIBLE_ONLY`;
- `FORWARD_COMPATIBLE_ONLY`;
- `BREAKING`;
- `UNKNOWN`.

Assessment inputs include:
- old/new interface signature/schema digest;
- semantic version policy;
- declared consumers;
- migration/adapter availability;
- required compatibility direction;
- verifier evidence.

Fail-closed rule: `UNKNOWN` cannot be promoted as compatible.

## 7. IntegrationGraph

Integration state is separate from Git branches. It models whether individually-valid changes can safely coexist.

Each **ChangeCandidate** contains:
- candidate id;
- producer agent/region;
- task/plan/requirement refs;
- source/artifact refs;
- architecture revision expected;
- changed component/interface refs;
- dependency candidate ids;
- conflicts/incompatibilities;
- verification evidence refs;
- status (`PROPOSED`, `READY`, `BLOCKED`, `INTEGRATED`, `REJECTED`, `SUPERSEDED`).

IntegrationGraph provides:
- candidate dependency DAG;
- deterministic integration ordering;
- conflict detection;
- architecture-revision freshness check;
- compatibility gate;
- evidence completeness gate;
- accepted integration receipts;
- rollback/supersession history.

## 8. Governed change control

Integration Chief is the normal owner of `integration-state`.

A candidate can become `INTEGRATED` only if:
1. dependencies are already integrated or included in the same valid batch;
2. architecture revision is current or an explicit compatibility proof covers drift;
3. all impacted public/internal interfaces have non-UNKNOWN compatibility assessments;
4. required verification evidence exists;
5. no active independent Security/Verification block applies;
6. conflicts are resolved through an evidence-bearing decision.

Central override remains an explicit override receipt; it never changes a failed verifier/security result into “passed”.

## 9. Cross-region propagation

Accepted architecture changes produce typed downstream deltas, not chat messages:
- Planning: new/changed work nodes and affected task refs;
- Integration: expected architecture revision and compatibility obligations;
- Verification: required test classes and acceptance evidence;
- Security: trust-boundary changes;
- Data: schema/storage migration obligations;
- UI/UX: public interaction contract changes where applicable.

Part IV emits the structured obligations. Future Parts consume them through the shared EventLedger/context system.

## 10. Architecture reconciliation

`ArchitectureReconciler` compares authoritative ArchitectureGraph with observations such as:
- repository/module dependency observations;
- runtime service topology;
- interface/schema snapshots;
- integration candidate declarations.

Drift classes:
- `UNDECLARED_COMPONENT`;
- `MISSING_COMPONENT`;
- `UNDECLARED_DEPENDENCY`;
- `FORBIDDEN_DEPENDENCY`;
- `INTERFACE_SIGNATURE_DRIFT`;
- `TRUST_BOUNDARY_DRIFT`;
- `STALE_ARCHITECTURE_REF`.

Findings do not auto-mutate authority.

## 11. Direct Chief work

Acceptance scenarios must prove both Chiefs are workers:
- Architecture Chief personally diagnoses and authors a corrected cross-module boundary/ADR/revision;
- Integration Chief personally adjudicates a multi-candidate compatibility conflict and produces an integration receipt.

Both use ordinary Part-I task leasing/artifacts/events rather than a manager-only shortcut.

## 12. Runtime integration

Part IV adds:
- `runtime.architecture: ArchitectureControlPlane`;
- `runtime.integration: IntegrationControlPlane`;
- `runtime.architecture_reconciler` or a stateless constructor over current stores;
- ContextCompiler authoritative versions for architecture/integration;
- exact serialization/restart.

Existing Part I–III state stores remain canonical. Part IV references their ids rather than copying requirements/plans/tasks into architecture state.

## 13. Event vocabulary

Use precise typed events where possible:
- `ARCHITECTURE_CHANGE_PROPOSED`;
- `ARCHITECTURE_CHANGED`;
- `ADR_ACCEPTED`;
- `ARCHITECTURE_IMPACT_COMPUTED`;
- `COMPATIBILITY_ASSESSED`;
- `INTEGRATION_CANDIDATE_ADDED`;
- `INTEGRATION_BLOCKED`;
- `INTEGRATION_ACCEPTED`;
- `INTEGRATION_REJECTED`;
- `ARCHITECTURE_RECONCILIATION_FINDING`.

To preserve snapshot schema compatibility in this generation, additional names may be represented as documented subtypes over existing canonical EventKind values until a dedicated event-schema migration is introduced.

## 14. Fail-closed rules

- non-owner architecture/integration mutation -> reject;
- empty mutation reason/evidence -> reject;
- unknown refs -> reject;
- forbidden dependency cycle -> reject atomically;
- stale expected architecture version -> block integration;
- `UNKNOWN` compatibility -> block integration;
- missing required verification -> block integration;
- verifier/security block -> remain blocked unless an explicit Central override receipt exists, which remains labeled override;
- rollback/supersession never deletes history;
- non-canonical snapshot/revision/digest -> reject restore.

## 15. Test strategy

Contract suites cover:
- ArchitectureGraph ownership, revisions, cycles and atomicity;
- interface/version/compatibility semantics;
- ADR provenance and supersession;
- worker architecture concerns without mutation;
- deterministic blast-radius impact packets;
- candidate DAG and integration ordering;
- individually-green but mutually-incompatible candidates rejected;
- stale architecture version rejected;
- independent block preservation;
- Architecture/Integration Chief direct work;
- drift reconciliation;
- exact snapshot/restore and context authoritative deltas;
- all Part I–III organization regressions.

## Acceptance boundary

Part IV proves only the bounded architecture/integration mechanisms and their contract tests. It does not prove unrestricted software architecture expertise, autonomous production deployment, general AGI, or superiority to frontier coding systems. Those claims remain disabled pending later real-repository and independent evaluation.