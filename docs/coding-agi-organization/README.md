# Nolane Coding AGI Organization — Master Index

> Status: architecture program proposal. This document does not assert that any proposed agent is already AGI or that the organization has been implemented. Capability claims must remain bounded by measured evidence.

## Purpose

This documentation line defines the long-horizon organization architecture for evolving Nolane-AI from one compact cognitive system into a persistent, hierarchical **Coding-AGI organization** composed of many independently capable, continuously improving AI systems.

The core idea is not a swarm of prompt personas. It is a structured software-engineering organization in which every permanent AI has:

- a shared general cognitive substrate;
- its own neural specialization;
- its own long-term memory and experience history;
- its own private and regional skill libraries;
- its own external cognitive core and tool interfaces;
- its own learning, self-evaluation, skill-synthesis and promotion loop;
- a persistent identity, responsibility boundary and authority scope;
- the ability to perform real work directly rather than existing only as a router.

The organization is coordinated by **Nolane Central**, but intelligence and improvement are intentionally distributed. Regional Chiefs must remain high-capability working agents: a Coding Chief can code, a Debug Chief can investigate failures, a Planning Chief can construct or repair plans, and so on. Delegation is optional optimization, not the definition of a Chief.

## Baseline organization target

The initial architectural target is:

- **1 Nolane Central**;
- **15 functional regions**;
- **15 Regional Chiefs**;
- **51 permanent specialist AIs**;
- **67 permanent AI identities total**;
- optional ephemeral specialists spawned when a task requires temporary depth.

All initial neural systems are constrained to **less than 100 million physical trainable parameters per AI**. The Central and Regional Chiefs may approach the ceiling, while smaller specialists may occupy lower budgets. Future versions may exceed the ceiling only after compute/economic constraints change and only under fresh capability and efficiency justification.

The parameter ceiling is a budget constraint, not an AGI claim. The intended generality comes from the complete cognitive system — neural policy, memory, retrieval, planning, causal reasoning, tools, skill synthesis, verification, external cores and lifelong experience — and must be validated empirically.

## The 15 regions

1. Requirements / Product Intelligence
2. Planning / Program Intelligence
3. Architecture / System Design
4. Core Coding
5. Frontend / UI Engineering
6. UX / Product Design
7. Debugging / Failure Intelligence
8. Verification / Testing
9. Security / Adversarial Engineering
10. Data / Storage / Migration
11. Infrastructure / DevOps / Release
12. Performance / Reliability
13. Research / External Intelligence
14. Integration / Change Control
15. Memory / Context / Knowledge

## Foundational laws

1. **Every permanent AI must be a worker.** A Chief is never a pure dispatcher.
2. **Every permanent AI must be able to learn.** Central improvement without specialist improvement is a failed architecture.
3. **Specialization must not destroy general cognition.** A debugger remains capable of planning, research, tool use, learning and communication; it merely has stronger debugging priors, tools and experience.
4. **Central has global authority.** It may observe, interrupt, question, redirect or stop any AI directly without routing through the Regional Chief.
5. **Direct intervention is always logged.** The Regional Chief is notified through the event fabric so regional state cannot silently diverge.
6. **Ownership is explicit.** Agents may propose changes across regions, but authoritative artifacts have named owners.
7. **Context is compiled, not dumped.** No agent receives the whole project history by default.
8. **Memory is persistent outside the context window.** Context is working memory, not long-term memory.
9. **Learning is evidence-gated.** New skills, strategies or neural deltas are candidates until verified.
10. **Promotion is reversible.** Every self-improvement path must support champion/challenger evaluation and rollback.
11. **No single result can silently rewrite global truth.** Important state changes flow through typed events, evidence and authority gates.
12. **Physical parameter accounting is authoritative.** Shared parameters, local parameters, active parameters and logical footprint must never be conflated.

## Document map

- [`MASTER_ARCHITECTURE_REPORT.md`](MASTER_ARCHITECTURE_REPORT.md) — complete organization report: hierarchy, agent allocation, parameter budgets, external cores, authority, memory, communication and evolution.
- [`PART_I_FOUNDATION.md`](PART_I_FOUNDATION.md) — first implementation-oriented planning part: the common substrate and organizational laws that must exist before the 67-agent system is expanded.

### Planned future parts

The long-horizon plan is intentionally decomposed so each part can receive its own design, falsification gates and implementation plan.

- **Part I — Foundation:** universal cognitive substrate, identities, authority, events, memory and context.
- **Part II — Central AGI:** global cognition, direct intervention, resource arbitration and world/project state.
- **Part III — Planning & Requirements:** living plan graph, requirement authority, task DAG and drift reconciliation.
- **Part IV — Architecture & Integration:** architecture graph, ADR authority, interface contracts and change-control fabric.
- **Part V — Coding Organization:** Coding Chief plus specialized coding intelligences and coding external cores.
- **Part VI — Debugging Organization:** reproduction, trace, static root cause, concurrency/state and regression intelligence.
- **Part VII — UI / UX Organization:** browser-grounded interface engineering, visual verification and product interaction intelligence.
- **Part VIII — Verification & Security:** independent checking authority, adversarial validation, fuzzing and acceptance gates.
- **Part IX — Data / Infrastructure / Reliability:** persistence, migration, deployment, CI, observability, failure recovery and performance.
- **Part X — Research Intelligence:** evidence-grounded external research, documentation, repositories, papers and prior art.
- **Part XI — Memory & Context Intelligence:** shared/private memory, context compiler, semantic delta and long-horizon continuity.
- **Part XII — Individual Evolution:** personal skill synthesis, regional/global skill transfer, self-models and neural consolidation.
- **Part XIII — Multi-Agent Coordination:** typed cognitive events, conflict packets, work leasing, wake/sleep scheduling and resource governance.
- **Part XIV — Ephemeral Specialist Foundry:** dynamic temporary agents, lifecycle, distillation and retirement.
- **Part XV — Evaluation & Scaling:** external benchmarks, organization-level reliability, parameter/compute scaling and future >100M evolution.

## Success criterion for the overall program

The target is not merely that 67 agents can exist. The target is that the organization can operate over very long software projects while preserving continuity:

- agents can sleep and wake without losing mission state;
- specialists improve from their own experience;
- Chiefs directly work while also maintaining regional coherence;
- Central can understand and intervene anywhere without becoming a context bottleneck;
- plan, code, architecture, bugs and evidence remain synchronized;
- independent verification can reject incorrect work regardless of who produced it;
- lessons can remain private, become regional, or become global through governed promotion;
- the system can scale the number of agents without turning coordination overhead into the dominant workload.

This is the organizational target that the subsequent parts must make executable and falsifiable.