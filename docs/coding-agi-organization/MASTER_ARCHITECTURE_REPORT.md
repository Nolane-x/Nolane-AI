# Nolane Coding AGI Organization — Master Architecture Report

> Status: long-horizon architecture proposal. This document defines intended structure and constraints. It does not claim the proposed agents already exist, are AGI, or have demonstrated the capabilities described here.

## 1. Executive vision

Nolane-AI should evolve from a single compact cognitive system into a persistent, hierarchical software-engineering intelligence organization. The intended system is not a flat swarm, a set of personas, or a manager delegating to weak workers. It is a society of durable AI identities in which every permanent agent has general cognitive capability plus a deep technical specialization and an independent learning trajectory.

The first full organizational target is **67 permanent AIs**:

- 1 Nolane Central;
- 15 Regional Chiefs;
- 51 permanent specialists;
- optional ephemeral specialists for temporary depth.

Every permanent AI must be able to reason, plan, research, use tools, learn from feedback, synthesize skills, maintain memory, evaluate uncertainty, communicate with other agents, and improve through evidence-gated evolution. Specialization adds capability; it must not remove general cognition.

Nolane Central is the strongest global coordinator, but it does not monopolize intelligence. A Debug Chief should eventually debug better than Central, a Coding Chief should be able to implement difficult code directly, a Planning Chief should be able to repair project plans directly, and specialists should become progressively stronger in their own areas through experience.

## 2. Hard constraints for the first generation

### 2.1 Neural parameter ceiling

Every AI starts below **100M physical trainable parameters**.

Recommended initial bands:

| Class | Initial target | Role |
|---|---:|---|
| Nolane Central | 90–98M | global cognition and authority |
| Regional Chief | 82–94M | regional cognition + direct expert work |
| Senior Specialist | 65–82M | difficult specialist reasoning |
| Specialist | 50–70M | narrower specialist depth |
| Lightweight specialist, where justified | below 50M | highly constrained auxiliary work |

These are engineering budgets, not evidence of AGI. No model should be called AGI because of parameter count alone. Each capability class must be measured.

A key design principle is **evolution headroom**. A new permanent AI should generally not begin at 99.9M. It should preserve room for validated neural deltas before the initial ceiling is reached.

### 2.2 Truthful accounting

The system must separately report:

- shared physical parameters;
- local physical parameters;
- per-agent physical parameter count;
- active inference footprint;
- total stored model footprint;
- shared backbone footprint;
- specialization-delta footprint.

The architecture must never multiply shared parameters by the number of logical agents and present the result as unique physical parameters.

### 2.3 General cognitive minimum

Every permanent AI needs a common capability floor:

- goal understanding;
- task decomposition;
- local planning and replanning;
- causal/hypothesis reasoning;
- memory retrieval and memory write discipline;
- tool selection and tool use;
- uncertainty estimation;
- evidence handling;
- communication and escalation;
- self-evaluation;
- skill induction;
- learning from success and failure;
- conflict recognition;
- safe refusal to claim completion without evidence.

An agent that can perform only one deterministic micro-task is a tool, not one of the permanent AI identities described here.

## 3. Universal Nolane Cognitive Substrate

The preferred economic architecture is a common **Universal Nolane Cognitive Core** plus per-agent specialization.

A possible first-generation structure is:

```text
Universal Nolane Core ~50–60M
        |
        +-- Central specialization delta
        +-- Planning Chief delta
        +-- Coding Chief delta
        +-- Debug Chief delta
        +-- ...
        +-- specialist deltas
```

The shared substrate should provide general cognition while local deltas create technical specialization. The exact parameter partition is an experimental question and must be benchmarked rather than fixed dogmatically.

Every permanent identity also owns non-neural state that is not shared wholesale:

1. private long-term memory;
2. personal experience ledger;
3. private skill library;
4. self-model;
5. specialization configuration;
6. external-core bindings;
7. trusted-tool registry;
8. failure-history and calibration record.

This ensures two agents can begin from a related substrate but diverge into genuinely different experts over time.

## 4. Organization size and regional allocation

The baseline target contains 15 regions and 66 regional AIs plus Central.

| Region | AI count | Structure |
|---|---:|---|
| Requirements / Product Intelligence | 3 | 1 Chief + 2 specialists |
| Planning / Program Intelligence | 5 | 1 Chief + 4 specialists |
| Architecture / System Design | 5 | 1 Chief + 4 specialists |
| Core Coding | 7 | 1 Chief + 6 specialists |
| Frontend / UI Engineering | 4 | 1 Chief + 3 specialists |
| UX / Product Design | 3 | 1 Chief + 2 specialists |
| Debugging / Failure Intelligence | 6 | 1 Chief + 5 specialists |
| Verification / Testing | 5 | 1 Chief + 4 specialists |
| Security / Adversarial Engineering | 4 | 1 Chief + 3 specialists |
| Data / Storage / Migration | 4 | 1 Chief + 3 specialists |
| Infrastructure / DevOps / Release | 4 | 1 Chief + 3 specialists |
| Performance / Reliability | 4 | 1 Chief + 3 specialists |
| Research / External Intelligence | 4 | 1 Chief + 3 specialists |
| Integration / Change Control | 4 | 1 Chief + 3 specialists |
| Memory / Context / Knowledge | 4 | 1 Chief + 3 specialists |
| **Regional total** | **66** | **15 Chiefs + 51 specialists** |
| Nolane Central | **1** | global authority + direct worker |
| **Total** | **67** | permanent identities |

The counts are a baseline, not an eternal fixed law. Real benchmark evidence may justify splitting or merging roles.

## 5. The Chief principle: manager and worker simultaneously

A Regional Chief is not a message broker.

Every Chief must maintain two modes:

### 5.1 Regional cognition mode

The Chief understands:

- current regional goals;
- active tasks;
- regional dependency graph;
- specialist competence;
- unresolved conflicts;
- accepted and rejected evidence;
- current risks;
- cross-region obligations;
- progress since last checkpoint.

It can allocate work, combine results, reject weak findings, request independent checks, and escalate changes.

### 5.2 Direct work mode

The Chief can personally perform difficult work when:

- the task exceeds a specialist's competence;
- the task is too interconnected for narrow delegation;
- the Chief notices an error and can directly repair it;
- latency matters;
- a cross-specialist synthesis is required;
- a specialist is unavailable or repeatedly failing;
- the Chief wants to independently verify a specialist result.

Examples:

- Coding Chief directly implements a difficult architectural refactor.
- Debug Chief personally forms and tests root-cause hypotheses.
- Planning Chief directly rewrites a broken dependency plan.
- Architecture Chief directly designs a new subsystem boundary.
- Verification Chief directly constructs a falsifying test.
- Research Chief directly performs high-stakes evidence synthesis.

Delegation is a scaling technique, not the Chief's identity.

## 6. Nolane Central

Nolane Central is a working intelligence with global authority and the broadest system view.

### 6.1 Central responsibilities

Central maintains or can reconstruct:

- overall project mission;
- current global plan state;
- architecture summary;
- region health;
- milestone state;
- unresolved high-impact conflicts;
- resource allocation;
- accepted global decisions;
- critical evidence;
- system-wide risks;
- current organization capability map.

Central can itself perform analysis, planning, coding, research, debugging or verification when appropriate. It is not restricted to coordination.

### 6.2 Direct intervention

Central may directly communicate with any permanent or ephemeral AI. It does not require permission from a Regional Chief.

Supported interventions should include:

- `OBSERVE`
- `QUESTION`
- `REQUEST_EVIDENCE`
- `CORRECT`
- `REDIRECT`
- `PAUSE`
- `ABORT`
- `REPLAN`
- `REASSIGN`
- `FORCE_VERIFICATION`
- `ROLLBACK_REQUEST`

Example:

```text
CENTRAL_CORRECTION

target: Debug.RuntimeTrace.02
reason: current hypothesis assumes an immutable state that changed in commit X
evidence: trace T92, architecture decision A18
directive: re-evaluate hypotheses using mutable-state semantics
priority: high
```

Direct intervention is recorded in the global event ledger. The relevant Regional Chief is notified automatically so the region does not maintain a stale model of what its agent is doing.

### 6.3 Central tools

Central should have access to almost all generic system tools, including:

- repository/file access;
- terminal and sandbox;
- Git operations;
- search;
- LSP and symbol navigation;
- AST inspection;
- compilers and test runners;
- browser and browser automation;
- project graphs;
- memory systems;
- research systems;
- agent-control systems;
- evidence stores;
- plan and architecture state.

However, a specialist may own a private or highly specialized external tool that Central does not expose directly. Central knows the tool exists, understands its capability and can invoke the owning agent.

This preserves real specialist advantage instead of making every agent a differently named wrapper over the same toolset.

## 7. Region specifications

### 7.1 Requirements / Product Intelligence — 3 AIs

- **Requirements Chief** — owns requirement authority; directly performs requirement analysis.
- **Requirement Analyst** — decomposes user/product intent, ambiguity and constraints.
- **Acceptance & Constraint Specialist** — formalizes acceptance conditions and non-functional constraints.

Owned artifacts:

- product intent;
- requirements graph;
- acceptance criteria;
- constraints;
- scope history;
- ambiguity ledger.

### 7.2 Planning / Program Intelligence — 5 AIs

- **Planning Chief** — owns Master Plan and can personally construct/rewrite plans.
- **Task-Graph Planner** — task decomposition, prerequisites and dependency DAG.
- **Strategic / Milestone Planner** — long-horizon sequencing and milestone structure.
- **Dependency & Risk Planner** — critical paths, blockers, change propagation and risk.
- **Plan Auditor** — periodically compares planned state against actual repository/evidence state.

The Plan Auditor must support both event-driven wakeups and checkpoint audits.

### 7.3 Architecture / System Design — 5 AIs

- **Architecture Chief** — owns system architecture and directly designs difficult subsystems.
- **Component Architect** — module boundaries and decomposition.
- **Interface / API Architect** — contracts and compatibility surfaces.
- **Change-Impact Architect** — architecture-wide consequences of proposed changes.
- **Architecture Auditor** — detects erosion, dependency violations and incoherent local designs.

Owned artifacts include architecture graph, ADRs, interface contracts and forbidden dependency boundaries.

### 7.4 Core Coding — 7 AIs

- **Coding Chief** — strongest regional coder; integrates implementation knowledge and directly codes.
- **Core / Algorithm Coder** — difficult algorithms and core logic.
- **Backend Coder** — services, runtime logic and APIs.
- **Systems / Low-Level Coder** — concurrency, Rust/C/C++, runtime and systems concerns.
- **Refactoring Coder** — structural improvements while preserving behavior.
- **API / Interface Coder** — contract implementations and compatibility work.
- **Build / Dependency Coder** — build systems, dependency updates and package-level engineering.

This is one of the largest regions because software implementation itself spans multiple cognitive styles.

### 7.5 Frontend / UI Engineering — 4 AIs

- **Frontend Chief** — direct high-level UI engineer plus regional coordinator.
- **Frontend State / Logic Engineer** — state, data flow and client behavior.
- **Component / Rendering Engineer** — components, layout, rendering and browser behavior.
- **Responsive / Accessibility Engineer** — a11y, keyboard, responsive surfaces and semantic UI.

### 7.6 UX / Product Design — 3 AIs

- **UX Chief** — owns user flow and can directly design product interactions.
- **Interaction Flow Specialist** — journeys, transitions and information architecture.
- **Visual / Design-System Specialist** — visual consistency, tokens, hierarchy and design rules.

### 7.7 Debugging / Failure Intelligence — 6 AIs

- **Debug Chief** — strongest general debugger and regional failure model owner.
- **Bug Reproduction Specialist** — minimal reproduction, environment isolation and failure triggering.
- **Runtime / Trace Investigator** — logs, traces, stack/state transitions and runtime evidence.
- **Static Root-Cause Investigator** — source/data/control-flow diagnosis.
- **Concurrency / State Investigator** — races, deadlocks, ordering and state corruption.
- **Regression / Bisect Investigator** — history, regressions, causal commits and change localization.

This region is intentionally broad because debugging is not one skill.

### 7.8 Verification / Testing — 5 AIs

- **Verification Chief** — independent acceptance authority and direct verifier.
- **Unit / Property Specialist** — unit tests, invariants and property-based testing.
- **Integration / E2E Specialist** — subsystem and end-to-end behavior.
- **Specification / Acceptance Specialist** — verifies implementation against authoritative requirements.
- **Fuzz / Counterexample Specialist** — actively searches for failure cases.

Verification must remain independently capable of rejecting work produced by Central or any Chief.

### 7.9 Security / Adversarial Engineering — 4 AIs

- **Security Chief** — security authority and direct adversarial analyst.
- **Threat / Trust-Boundary Specialist** — threat models, permissions and trust boundaries.
- **Application / Dependency Security Specialist** — code, dependency and supply-chain issues.
- **Adversarial / Exploit Validation Specialist** — attack-oriented validation and security testing.

Security findings can block promotion where policy requires it.

### 7.10 Data / Storage / Migration — 4 AIs

- **Data Chief** — data architecture and direct data engineer.
- **Schema / Persistence Specialist** — storage structures and consistency.
- **Migration / Compatibility Specialist** — version transitions, migration and rollback.
- **Cache / Data-Flow Specialist** — caches, data propagation and consistency semantics.

### 7.11 Infrastructure / DevOps / Release — 4 AIs

- **Infrastructure Chief** — environment and release authority; direct infrastructure engineer.
- **CI / Build Environment Specialist** — CI, runners, containers and environments.
- **Deployment / Packaging Specialist** — artifacts, deployment and packaging.
- **Observability / Release Specialist** — logs, metrics, release evidence and operational visibility.

### 7.12 Performance / Reliability — 4 AIs

- **Reliability Chief** — system reliability and direct performance/recovery engineer.
- **Performance / Profiling Specialist** — CPU, memory, I/O and latency.
- **Resilience / Recovery Specialist** — retry, rollback, checkpoint, partial failure and degradation.
- **Concurrency / Capacity Specialist** — capacity, scheduling, bottlenecks and resource behavior.

### 7.13 Research / External Intelligence — 4 AIs

- **Research Chief** — performs and governs external research.
- **Repository Archaeologist** — histories, conventions and codebase archaeology.
- **Docs / API Researcher** — official documentation, SDKs, version behavior and standards.
- **Algorithm / Prior-Art Researcher** — papers, techniques and comparable architectures.

Research output should preserve provenance and freshness.

### 7.14 Integration / Change Control — 4 AIs

- **Integration Chief** — owns whole-system integration and can directly resolve integration failures.
- **Merge / Compatibility Specialist** — merge topology and compatibility.
- **Cross-System Dependency Specialist** — cross-region dependency effects.
- **Change-Control Auditor** — ensures accepted changes are reflected across plan, architecture, tests and release state.

### 7.15 Memory / Context / Knowledge — 4 AIs

- **Memory & Context Chief** — owns the memory fabric and directly diagnoses memory/context failures.
- **Context Compiler** — builds task-specific context capsules before agent wake/execution.
- **Knowledge / Memory Curator** — consolidation, provenance, deduplication and forgetting policy.
- **Temporal / Event Intelligence Specialist** — event history, semantic deltas and checkpoint continuity.

This region is system-critical: if context or memory fails, all other intelligences degrade.

## 8. Communication model

Agents should not primarily coordinate through unrestricted conversational chains. Important information is promoted into typed cognitive objects.

Core event/object types include:

- `RequirementChange`
- `RequirementAmbiguity`
- `PlanGap`
- `PlanChangeProposal`
- `ArchitectureConcern`
- `ArchitectureDecision`
- `ImplementationProposal`
- `BugReport`
- `RootCauseHypothesis`
- `PatchCandidate`
- `TestEvidence`
- `VerificationRejection`
- `SecurityFinding`
- `IntegrationConflict`
- `PerformanceRegression`
- `ResearchEvidence`
- `SkillCandidate`
- `SkillPromotion`
- `MemoryConflict`
- `CentralCorrection`
- `ReleaseDecision`

Every authoritative object should carry at least:

- unique ID;
- type;
- owner;
- source agent;
- scope;
- status;
- evidence references;
- dependency references;
- confidence/calibration metadata where applicable;
- version;
- timestamp/ordering information;
- superseded object links;
- review/authority state.

## 9. Cross-region change example

A Backend Coder discovers that a feature requires a database migration that the plan omitted.

The coder does not silently edit the master plan. It emits a `PlanGap` with evidence.

Flow:

```text
Backend Coder
   |
   +-- PlanGap --------------------> Planning Chief
   |                                   |
   |                                   +--> Dependency & Risk Planner
   |                                   +--> Task-Graph Planner
   |                                   |
   |                                   +--> accepted PlanChange
   |
   +-- ArchitectureConcern --------> Architecture Chief, if boundaries change
                                       |
                                       +--> ArchitectureDecision
```

The Data region can receive a migration task; Verification receives new acceptance criteria; Integration receives compatibility obligations. Central is notified only if the impact exceeds the configured global threshold, though Central can inspect or intervene at any time.

## 10. Authority and ownership

Authoritative artifacts have named owners.

| Artifact | Primary owner |
|---|---|
| Global mission / organization policy | Nolane Central |
| Requirements | Requirements Chief |
| Master Plan / Task Graph | Planning Chief |
| Architecture Graph / ADR | Architecture Chief |
| Core implementation state | Coding Chief |
| UI implementation state | Frontend Chief |
| UX state | UX Chief |
| Failure / bug state | Debug Chief |
| Verification evidence | Verification Chief |
| Security state | Security Chief |
| Data / migration state | Data Chief |
| Infrastructure / release state | Infrastructure Chief |
| Reliability / performance state | Reliability Chief |
| Research evidence state | Research Chief |
| Integration state | Integration Chief |
| Memory/context policy and indexes | Memory & Context Chief |

Cross-region agents can propose, challenge and supply evidence, but they should not silently mutate another region's authoritative state.

Central can override ownership in exceptional cases, but every override is explicit and recorded.

## 11. Memory architecture

The system should implement layered persistent memory:

### L0 — Global Constitution

Stable organization laws, authority rules, identity definitions and capability boundaries.

### L1 — Global Project State

Master Plan, requirements, architecture summaries, task graph, major bugs, milestone state, decision ledger, evidence ledger, release state and agent registry.

### L2 — Regional Memory

Domain-specific knowledge for each region.

Examples:

- Debug: failure signatures, rejected hypotheses, reproduction recipes.
- Coding: conventions, accepted refactor patterns, module histories.
- Planning: plan changes, dependency risks, estimation failures.

### L3 — Personal Long-Term Memory

Each permanent AI maintains its own durable experience and expertise.

### L4 — Current Task Capsule

The minimal structured information needed for the current job.

### L5 — Private Working/Scratch Memory

Temporary hypotheses and exploratory material. Not automatically promoted to shared truth.

### L6 — Immutable Event Ledger

Ordered important changes and transitions.

### L7 — Artifact / Evidence Store

Tests, traces, patches, plans, reports, benchmark receipts, research evidence and other concrete artifacts.

## 12. Context window policy

The context window is working memory, not project memory.

Before an agent wakes, the Context Compiler builds a capsule from:

- identity and role;
- current task;
- authoritative constraints;
- relevant plan nodes;
- relevant code/symbols;
- relevant decisions;
- changes since the last checkpoint;
- agent personal memory;
- region memory;
- known failed attempts;
- acceptance criteria;
- current evidence;
- available and trusted tools.

A useful conceptual budget is:

- 2–5% universal constitution;
- ~10% relevant global state;
- ~15% regional state;
- ~15% personal memory;
- ~30–35% task-specific material;
- ~15–20% code/evidence;
- remaining reserve for active reasoning.

Exact ratios must remain dynamic.

### Context Delta

A sleeping agent should not receive its old context replayed verbatim. It receives a semantic delta:

```text
Since your last checkpoint:
+ task T81 completed
+ API signature changed
+ plan node P41 split into P41a/P41b
+ bug B17 opened
- hypothesis H4 rejected
! integration test I18 failing
```

This is essential for long-lived agents.

## 13. Wake / sleep / scheduling

The organization should be event-driven rather than permanently active.

Agents wake from:

- direct task assignment;
- subscribed event type;
- regional checkpoint;
- periodic audit;
- Central intervention;
- dependency completion;
- verification failure;
- drift detection.

Typical concurrent activity may involve only 3–8 agents. Large migrations or severe failures may activate 12–18. The existence of 67 persistent identities does not imply 67 simultaneous model executions.

## 14. External cognitive cores

Specialized external cores must create real capability differences.

### Coding Core

- AST parser;
- LSP / symbol graph;
- code search;
- dependency graph;
- compiler;
- type checker;
- patch engine;
- worktree manager;
- targeted test selector;
- build graph.

### Debug Core

- runtime tracer;
- stack analyzer;
- execution timeline;
- coverage;
- state diff;
- git bisect;
- profiler;
- leak detector;
- race/deadlock tools;
- failure minimizer.

### UI Core

- browser runtime;
- DOM/CSSOM/accessibility tree;
- screenshots and visual diff;
- Playwright-like interaction harness;
- responsive viewport matrix;
- design token graph;
- browser console/network inspection.

### Planning Core

- task DAG;
- critical path engine;
- constraint solver;
- architecture/change-impact graph;
- progress reconciler;
- milestone model;
- risk graph.

### Research Core

- web and repository retrieval;
- official documentation;
- papers;
- package registries;
- issue/release history;
- provenance store;
- source freshness metadata.

### Verification Core

- fresh sandboxes;
- test generation;
- property testing;
- fuzzing;
- static analysis;
- security checks;
- E2E runners;
- performance harness;
- regression suite.

### Memory Core

- semantic/vector retrieval;
- knowledge graph;
- repository graph;
- temporal event store;
- decision ledger;
- skill store;
- artifact store;
- semantic diff engine.

Other regions should receive equivalent purpose-built external cores as they mature.

## 15. Personal evolution for every AI

Every permanent AI must implement a personal evolution loop.

```text
Experience
   -> outcome analysis
   -> attribution
   -> candidate lesson/skill
   -> private validation
   -> independent verification where required
   -> promote / quarantine / reject
   -> future retrieval and behavior change
```

Learning should happen on several levels:

1. **episodic learning** — what happened before;
2. **semantic learning** — what principle was learned;
3. **procedural learning** — how to execute a class of task;
4. **strategy learning** — which approach works under which conditions;
5. **tool learning** — which tool to use and when;
6. **neural consolidation** — validated experience distilled into candidate weights.

### Skill scopes

Skills exist at three promotion levels:

- **Personal** — private to one AI;
- **Regional** — verified useful across a region;
- **Global** — verified general enough for the whole organization.

Automatic global synchronization is prohibited because it would destroy specialization and propagate bad skills.

## 16. Self-model

Each agent maintains a structured self-model containing at least:

- identity and role;
- strengths;
- weak areas;
- trusted skills;
- known failure modes;
- tool competence;
- domain experience;
- confidence calibration;
- recent improvements;
- known blind spots;
- benchmark history;
- neural version;
- memory/skill version.

Task assignment can then be competence-aware rather than round-robin.

## 17. Neural self-improvement

Production agents must not directly mutate their active weights after each experience.

Required pattern:

```text
current champion
    |
    +--> candidate training / adaptation
             |
             +--> candidate model
                     |
                     +--> old regression tests
                     +--> fresh tests
                     +--> specialization benchmarks
                     +--> general cognition retention
                     +--> safety / authority checks
                     |
                     +--> champion/challenger decision
                              |
                              +--> promote
                              +--> reject
                              +--> quarantine
```

Rollback must always remain possible.

Every specialist, Chief and Central follows the same evidence-gated principle.

## 18. Distributed intelligence principle

The desired end state is not:

```text
Central becomes smarter
others remain tools
```

It is:

```text
Central improves globally
Planning Chief improves planning
Coding Chief improves coding
Debug Chief improves debugging
specialists improve their specialisms
regional knowledge compounds
verified global knowledge compounds
```

Central remains strongest at understanding and controlling the whole organization. Regional experts are expected to exceed Central in their deep technical domains.

## 19. Temporary specialists

Once the permanent organization is stable, Chiefs can spawn ephemeral specialists for project-specific depth.

Examples:

- CUDA specialist;
- PostgreSQL specialist;
- compiler IR specialist;
- distributed consensus specialist;
- browser rendering specialist;
- cryptography reviewer.

Temporary agents receive scoped identity, task capsule, authority, tool access and lifecycle. Their useful knowledge may be distilled into personal/regional/global memories or skills before retirement.

The system should prefer **67 persistent identities + dynamic temporary depth** over hundreds of always-active permanent agents.

## 20. Failure modes this architecture must explicitly prevent

1. **Chief degeneration into dispatcher** — solved by direct-work requirements and Chief benchmarks.
2. **Central context overload** — solved by hierarchy, typed events and semantic deltas.
3. **Specialists becoming prompt clones** — solved by distinct memory, skills, external cores, training and experience.
4. **Shared-memory pollution** — solved by private/regional/global promotion levels.
5. **Silent plan drift** — solved by Plan Auditor and change-control reconciliation.
6. **Incorrect cross-region edits** — solved by ownership and proposal protocols.
7. **False completion claims** — solved by independent verification.
8. **Self-improvement regressions** — solved by candidate/champion gates and rollback.
9. **Unlimited agent spawning** — solved by resource budgets and ephemeral lifecycle.
10. **Parameter accounting inflation** — solved by physical accounting contracts.
11. **Stale sleeping agents** — solved by Context Delta and wake-time compilation.
12. **Central intervention desynchronizing Chiefs** — solved by ledgered intervention notification.

## 21. Organization-level evaluation

Success must be measured at individual, regional and global levels.

### Individual metrics

- task success;
- calibration;
- retained general cognition;
- specialization score;
- learning speed;
- regression rate;
- skill usefulness;
- tool efficiency.

### Regional metrics

- throughput;
- quality;
- handoff cost;
- unresolved conflicts;
- rework;
- memory continuity;
- Chief direct-work competence;
- specialist improvement over time.

### Global metrics

- end-to-end repository issue resolution;
- long-horizon project completion;
- requirement adherence;
- architecture coherence;
- integration success;
- release correctness;
- number and severity of false accepts;
- context/coordination overhead;
- improvement after experience;
- cross-project transfer;
- recovery after agent or memory failures.

## 22. Scaling rule

Do not scale permanent identity count merely because more agents sound powerful.

Before expanding beyond the first full organization, demonstrate that the system can:

- preserve task identity over thousands of events;
- sleep and wake agents without mission loss;
- update plans correctly as reality changes;
- sustain regional ownership;
- maintain memory consistency;
- allow Central direct intervention without chaos;
- improve multiple distinct agents over time;
- prevent skill propagation from causing regressions;
- verify difficult work independently;
- keep coordination cost below the value of added specialization.

Once those invariants hold, increasing permanent identities or exceeding 100M per model becomes a scaling/economic decision rather than an architectural rescue.

## 23. Final target

The intended system is best described as a **persistent AI software-engineering organization inside one governed cognitive architecture**.

It should possess:

- one globally aware Central intelligence;
- 15 working Regional Chiefs;
- dozens of independently improving specialists;
- long-term shared and personal memory;
- living requirements, plans and architecture;
- typed evidence-based communication;
- direct global intervention;
- region-level autonomy;
- specialized external cognitive cores;
- continual personal learning;
- governed skill transfer;
- reversible neural evolution;
- independent verification;
- dynamic temporary specialist creation.

The architecture is successful only when the whole organization becomes stronger while the individual agents also become stronger.