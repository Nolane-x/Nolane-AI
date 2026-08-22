# Part I — Foundation of the Nolane Coding AGI Organization

> Status: architecture part opening. This part defines the common substrate required before the organization is expanded into 67 permanent AI identities. It is intentionally implementation-oriented but does not yet authorize production implementation or capability claims.

## 1. Why Part I comes first

The planned Nolane Coding AGI organization is large: one Central intelligence, 15 working Regional Chiefs, 51 permanent specialists, and later temporary specialists. The primary early risk is not that an individual model is too weak. The primary risk is organizational incoherence:

- two agents believe different plans are current;
- a sleeping agent wakes with stale assumptions;
- a coder silently changes architecture;
- Central corrects a worker but the Chief never learns that the task changed;
- private hypotheses leak into shared truth;
- skill learning spreads an incorrect rule to every agent;
- context becomes dominated by old conversation rather than current evidence;
- a Chief becomes only a dispatcher and loses direct technical capability;
- specialists become identical prompt personas instead of distinct learning systems;
- neural self-improvement causes regression without rollback.

Part I therefore builds the **organizational substrate** before building the full organization.

The central principle is:

> More agents should be added only after identity, authority, memory, communication, context and evolution are machine-readable and testable.

## 2. Part I target

Part I should establish a small but complete vertical slice that proves the architecture can support persistent intelligent identities.

The initial test organization does not need all 67 agents. A recommended first executable slice is:

- Nolane Central;
- one Regional Chief, preferably Planning Chief or Coding Chief;
- two specialists in that region;
- one independent Verification agent;
- one Context/Memory agent.

This six-agent slice must demonstrate the same laws that will later govern all 67 agents.

## 3. Foundation subsystems

Part I contains ten foundational subsystems:

1. Universal Cognitive Substrate Contract
2. Agent Identity Registry
3. Authority and Ownership Graph
4. Typed Cognitive Event Fabric
5. Persistent Memory Fabric
6. Context Compiler and Context Delta
7. Task / Plan / Artifact Object Model
8. Wake-Sleep Scheduler
9. Personal Skill and Evolution Substrate
10. Verification, Promotion and Rollback Authority

None should be treated as optional infrastructure.

---

# 4. Universal Cognitive Substrate Contract

Every permanent AI is required to implement a common cognitive interface, regardless of specialization.

The contract should define capabilities rather than a single neural architecture.

Minimum operations should include concepts equivalent to:

```text
understand_mission
inspect_current_state
form_hypotheses
plan_local_work
request_context
retrieve_memory
use_tools
emit_evidence
propose_change
challenge_claim
report_uncertainty
reflect_on_outcome
synthesize_skill
checkpoint
resume_from_checkpoint
```

A specialist may implement these with different models or external cores, but the organization must be able to rely on the interface.

## 4.1 Chief extension

Every Regional Chief additionally satisfies:

```text
perform_specialist_work
maintain_regional_state
review_specialist_work
assign_or_reassign_work
resolve_regional_conflict
escalate_cross_region_change
reconcile_region_after_central_intervention
```

The first Part-I Chief benchmark must explicitly include a hard task that the Chief solves directly without delegating. This prevents the architecture from accidentally evolving Chiefs into routers.

## 4.2 Central extension

Central additionally satisfies:

```text
observe_global_state
query_any_agent
intervene_any_agent
change_global_priority
request_global_replan
force_verification
pause_or_abort_work
reassign_work
inspect_cross_region_conflict
```

Every Central intervention is ledgered.

---

# 5. Agent Identity Registry

The organization needs persistent identities independent of any one process invocation or context window.

Each identity record should contain:

```text
agent_id
human_readable_name
region
role
rank
neural_version
parameter_accounting
specialization_version
memory_namespace
skill_namespace
external_core_bindings
tool_permissions
authority_scope
subscriptions
current_task
checkpoint_id
status
self_model_version
```

Example:

```text
agent_id: coding.backend.01
region: core-coding
role: Backend Coder
rank: specialist
status: sleeping
neural_version: NUC-0.1 + backend-delta-0.3
current_task: T-184
memory_namespace: agent/coding.backend.01
skill_namespace: skills/personal/coding.backend.01
```

Identity must survive restart. A process is disposable; identity is persistent.

## 5.1 Identity invariants

- An agent cannot silently change its own identity.
- A task lease names exactly one responsible identity at a time unless explicitly shared.
- Memory written as personal memory is namespaced to the identity.
- Skill credit is attributed to the identity that produced the verified lesson.
- Neural versions are immutable once accepted; a new candidate receives a new version.

---

# 6. Authority and Ownership Graph

A hierarchy written only in prompts is not sufficient. Authority must be represented as data.

The graph should encode:

- global authority;
- regional authority;
- artifact ownership;
- intervention rights;
- approval rights;
- blocking rights;
- read/write permissions;
- escalation paths.

## 6.1 Core rule

Agents may observe and propose across boundaries when allowed, but authoritative state changes are performed through the owning authority or an explicit Central override.

Example:

```text
Backend Coder
    can_propose -> Master Plan
    cannot_authoritatively_write -> Master Plan

Planning Chief
    owns -> Master Plan

Central
    may_override -> Master Plan
    override_requires -> event + reason + evidence
```

## 6.2 Independent checking authority

Verification and Security must possess blocking authority on configured classes of promotion even when the work originated from a Chief or Central.

Central can overrule a block only through an explicit higher-order override record. Such an override is itself auditable and must never be represented as ordinary successful verification.

---

# 7. Typed Cognitive Event Fabric

Free-form chat may exist for local reasoning, but organization-level state changes require typed events.

## 7.1 Event envelope

Every event should contain:

```text
event_id
event_type
source_agent
targets
region
scope
created_at
causal_parent_ids
object_refs
evidence_refs
priority
requires_ack
status
```

## 7.2 Initial event vocabulary

Part I should implement at least:

```text
TASK_ASSIGNED
TASK_STARTED
TASK_PROGRESS
TASK_BLOCKED
TASK_COMPLETED
PLAN_GAP
PLAN_CHANGE_PROPOSED
PLAN_CHANGED
ARCHITECTURE_CONCERN
BUG_DISCOVERED
HYPOTHESIS_PROPOSED
EVIDENCE_ADDED
TEST_FAILED
TEST_PASSED
VERIFICATION_REJECTED
SKILL_CANDIDATE
SKILL_PROMOTED
SKILL_REJECTED
MEMORY_CONFLICT
CENTRAL_QUESTION
CENTRAL_CORRECTION
CENTRAL_REDIRECT
AGENT_CHECKPOINTED
AGENT_WOKE
AGENT_SLEPT
```

## 7.3 Subscription model

Agents subscribe to event types rather than reading every event.

Example:

```text
Planning Chief:
  PLAN_GAP
  TASK_BLOCKED
  ARCHITECTURE_CONCERN
  REQUIREMENT_CHANGE

Verification:
  PATCH_CANDIDATE
  TASK_COMPLETED
  SKILL_CANDIDATE

Memory/Context:
  all authoritative state-transition events
```

Central can inspect all promoted events but should receive only high-value interrupts by default.

## 7.4 Central direct intervention semantics

Central can emit directly to any agent:

```text
CENTRAL_CORRECTION
CENTRAL_REDIRECT
CENTRAL_PAUSE
CENTRAL_ABORT
CENTRAL_REQUEST_EVIDENCE
```

The event is delivered to the target immediately and mirrored to the Regional Chief's event view.

This implements the requirement that Central does not need to route corrections through a Chief while preserving regional consistency.

---

# 8. Persistent Memory Fabric

Memory must not be synonymous with one vector database.

Part I should define multiple memory forms because they answer different questions.

## 8.1 Memory stores

### Event Store

Answers: **what happened and in what order?**

### Knowledge Graph

Answers: **what entities and concepts relate to each other?**

### Repository Graph

Answers: **what code symbols, modules, tests and dependencies connect?**

### Semantic Retrieval Index

Answers: **what prior memory resembles this situation?**

### Decision Ledger

Answers: **what decision was made, why, by whom and under what evidence?**

### Skill Store

Answers: **what reusable procedure has been learned and where is it authorized?**

### Artifact / Evidence Store

Answers: **where is the concrete trace, test, patch, benchmark or document?**

No single store is authoritative for all questions.

## 8.2 Memory scopes

```text
GLOBAL
REGION
PERSONAL
TASK
PRIVATE_SCRATCH
```

A write must specify scope.

A specialist's speculative hypothesis defaults to private/task scope. It becomes regional/global only through promotion.

## 8.3 Memory provenance

Every promoted memory should preserve:

- producer;
- source evidence;
- time/version;
- scope;
- confidence/status;
- dependencies;
- supersession history.

## 8.4 Forgetting and invalidation

Long-lived memory requires controlled forgetting.

Memory entries may become:

```text
ACTIVE
STALE
SUPERSEDED
CONTRADICTED
QUARANTINED
ARCHIVED
```

Retrieval should penalize stale or contradicted knowledge unless explicitly requested for historical analysis.

---

# 9. Context Compiler

The Context Compiler converts persistent organization state into limited working context.

It must be treated as a cognitive system component, not a string concatenator.

## 9.1 Inputs

The compiler receives:

- agent identity;
- role;
- current task;
- last checkpoint;
- events since checkpoint;
- relevant requirements;
- relevant plan nodes;
- relevant architecture decisions;
- relevant code/symbol graph neighborhood;
- region memory;
- personal memory;
- failed attempts;
- accepted skills;
- verification state;
- tool availability.

## 9.2 Output — Context Capsule

A capsule should contain sections equivalent to:

```text
MISSION
IDENTITY
CURRENT TASK
WHY THIS TASK EXISTS
CURRENT AUTHORITATIVE PLAN
DEPENDENCIES
RECENT CHANGES
RELEVANT CODE
RELEVANT EVIDENCE
KNOWN FAILURES
APPLICABLE SKILLS
RISKS
ACCEPTANCE CRITERIA
TOOLS
AUTHORITY BOUNDARY
WHAT MUST BE REPORTED
```

## 9.3 Semantic Context Delta

When an agent wakes, the compiler first computes what changed since its checkpoint.

The delta is semantic, not merely a diff of chat messages.

Example:

```text
Since checkpoint CP-193:

PLAN
+ P41 split into P41a and P41b
+ T184 now depends on migration T211

ARCHITECTURE
+ ADR-92 introduced cache interface C7

CODE
+ auth API changed in commit abc123

FAILURES
+ integration test I18 now failing
- hypothesis H4 rejected by trace E83

CENTRAL
+ Central corrected assumption about mutable state
```

## 9.4 Context quality metrics

Part I should measure:

- task-relevant recall;
- stale information rate;
- missing dependency rate;
- context token cost;
- duplicated information;
- contradiction detection;
- successful resume rate after sleep.

---

# 10. Task, Plan and Artifact Object Model

The project state must be machine-readable.

## 10.1 Task object

Minimum fields:

```text
task_id
title
owner_agent
owner_region
plan_node
requirements
architecture_refs
dependencies
status
priority
inputs
expected_outputs
acceptance_criteria
verification_requirements
risk
created_by
history
```

## 10.2 Plan graph

Plan nodes form a versioned DAG rather than one mutable Markdown checklist.

Markdown can be rendered from the graph for humans, but the graph is the operational state.

The Planning Chief owns authoritative changes.

## 10.3 Artifact references

Tasks and events refer to immutable or content-addressed artifacts where practical:

- commits;
- patches;
- test runs;
- traces;
- screenshots;
- research evidence;
- benchmark receipts;
- design documents.

This avoids copying large evidence into every agent context.

---

# 11. Wake-Sleep Scheduler

Permanent intelligence does not require permanent execution.

Each identity can be:

```text
SLEEPING
WAKING
ACTIVE
WAITING
BLOCKED
CHECKPOINTING
PAUSED
QUARANTINED
```

## 11.1 Wake triggers

- task assigned;
- dependency completes;
- subscribed event fires;
- checkpoint audit due;
- Central intervention;
- verification rejects work;
- region reconciliation begins.

## 11.2 Sleep requirements

Before sleeping, an agent must checkpoint:

- current task state;
- unresolved hypotheses;
- evidence refs;
- intended next action;
- open dependencies;
- private memory candidates;
- skill candidates;
- important communications awaiting response.

A sleeping agent should not depend on hidden ephemeral context to resume.

---

# 12. Personal Skill Substrate

Every permanent AI owns a personal skill library.

A skill is not merely a text note. It should contain structured applicability and evidence.

Suggested fields:

```text
skill_id
owner_scope
producer_agent
trigger_conditions
preconditions
procedure
tool_requirements
expected_evidence
known_failure_modes
validation_history
confidence
version
status
```

## 12.1 Promotion levels

```text
PERSONAL
   |
   v
REGIONAL_CANDIDATE
   |
   v
REGIONAL
   |
   v
GLOBAL_CANDIDATE
   |
   v
GLOBAL
```

Promotion requires evidence at each boundary.

## 12.2 Rejection and quarantine

Incorrect skills should remain visible in historical evidence but excluded from ordinary retrieval.

This is necessary to prevent repeated relearning of known-bad strategies while also preserving falsification history.

---

# 13. Personal Evolution Engine

Every permanent AI uses an evolution loop.

## 13.1 Episode closure

After meaningful task completion or failure:

```text
observe outcome
compare prediction vs reality
attribute success/failure
extract candidate lesson
search for prior related lesson
create or update skill candidate
run local falsification
submit for required verification
update self-model
```

## 13.2 Self-model update

The agent records evidence-backed changes in:

- domain competence;
- tool competence;
- failure modes;
- calibration;
- trusted skills;
- blind spots.

No self-rating should increase merely because the agent claims it improved.

## 13.3 Neural candidate path

When sufficient experience accumulates, a training/consolidation process may create a candidate neural delta.

The active model remains immutable until promotion.

Required evaluation categories:

- specialization gain;
- general cognition retention;
- prior-task retention;
- fresh heldout tasks;
- calibration;
- tool-use correctness;
- false-accept rate;
- parameter budget;
- reproducibility.

All candidates remain below the initial 100M physical ceiling.

---

# 14. Verification and Promotion Authority

Verification should be external to the producer whenever the claim matters.

Examples:

- coder proposes patch -> Verification tests it;
- planner proposes major plan rewrite -> Plan Auditor and impacted regions check it;
- agent proposes regional skill -> another agent or Verification checks transfer;
- neural candidate claims improvement -> frozen benchmark + regression + independent receipt.

A successful unit test alone is not sufficient evidence of global correctness.

## 14.1 Fail-closed principle

If required evidence is absent, status remains candidate/pending rather than silently becoming accepted.

## 14.2 Rollback

Promoted skills, policies and neural versions maintain ancestry and rollback references.

---

# 15. External Core Interface

Part I should not implement every specialized tool, but it must define how external cores attach to agents.

Each external core declares:

```text
core_id
owner_agent_or_region
capabilities
input_schema
output_schema
side_effects
required_permissions
cost_model
failure_modes
verification_hooks
version
```

This lets Central know that a specialist capability exists without giving Central direct ownership of every specialist tool.

---

# 16. First vertical-slice scenario

Part I should end with an executable scenario that exercises the whole substrate.

Recommended scenario:

1. Central assigns a coding objective.
2. Planning Chief creates a small plan.
3. Coding specialist begins implementation.
4. Coder discovers a missing plan dependency and emits `PLAN_GAP`.
5. Planning Chief directly investigates, updates the plan and emits a versioned change.
6. Context Compiler updates the coder's capsule.
7. Coder continues and produces a patch.
8. Verification rejects the first patch with evidence.
9. Coder sleeps after checkpoint.
10. Central notices a wrong debugging assumption and sends a direct correction to the coder or verifier.
11. Agent wakes later with semantic delta, not old chat replay.
12. Corrected patch passes verification.
13. Coder extracts a personal skill candidate from the failure.
14. Skill is tested and promoted to personal scope only.
15. Planning Chief performs a periodic reconciliation and confirms task/plan/repository agreement.
16. All six agents persist identity and state across a simulated restart.

If this scenario cannot run reliably, the architecture is not ready for 67 permanent agents.

---

# 17. Part I acceptance gates

Part I should not be declared complete until all of the following are demonstrated.

## Identity

- persistent identity survives restart;
- correct personal memory namespace restored;
- no task ownership ambiguity.

## Chief-as-worker

- Regional Chief solves at least one difficult direct task without delegation;
- Chief can still maintain regional state while doing direct work.

## Central intervention

- Central corrects a specialist directly;
- specialist receives correction;
- Regional Chief automatically sees the intervention;
- no divergent task state remains.

## Event fabric

- typed events preserve causal relationships;
- subscribed agents receive relevant events;
- unrelated agents do not receive full event spam.

## Memory

- personal, regional and global scopes remain separated;
- stale knowledge can be superseded;
- evidence provenance is retained.

## Context

- sleeping agent resumes from context capsule;
- semantic delta includes critical changes;
- obsolete assumptions do not dominate restored context.

## Plan coherence

- PlanGap causes controlled plan amendment;
- task graph and rendered plan remain synchronized.

## Verification

- incorrect patch is rejected;
- producer cannot mark itself globally verified.

## Learning

- a specialist extracts a skill from experience;
- skill remains personal unless promotion criteria pass;
- rejected skill cannot silently re-enter active retrieval.

## Neural evolution

- candidate version can be evaluated without modifying champion;
- regression failure blocks promotion;
- rollback metadata is complete.

## Parameter accounting

- every model reports physical parameters truthfully;
- no accepted permanent model exceeds 100M.

---

# 18. Part I non-goals

Part I does not need to:

- instantiate all 67 agents;
- train all 15 Chiefs;
- solve arbitrary real-world repositories;
- prove AGI;
- implement every specialized external core;
- exceed 100M parameters;
- implement large-scale ephemeral swarms.

Its purpose is to make the organization **possible to scale safely and coherently**.

---

# 19. Transition into later parts

Once Part I passes its gates, later parts can build on stable primitives instead of inventing communication and memory independently.

Part II expands Nolane Central.

Parts III–XI construct each major organizational region and external core.

Part XII deepens individual evolution and cross-agent skill transfer.

Part XIII scales coordination.

Part XIV introduces ephemeral specialist creation.

Part XV validates the organization on unseen repositories, long-horizon tasks and scaling experiments.

The intended progression is:

```text
single compact cognitive system
        |
        v
persistent identities
        |
        v
typed organization substrate
        |
        v
small multi-agent vertical slice
        |
        v
15 working regions
        |
        v
67 independently improving permanent AIs
        |
        v
dynamic specialist ecosystem
        |
        v
externally evaluated long-horizon Coding-AGI organization
```

Part I is therefore not ancillary infrastructure. It is the foundation that determines whether every later AI can remain coherent, independently capable and genuinely capable of becoming stronger over time.